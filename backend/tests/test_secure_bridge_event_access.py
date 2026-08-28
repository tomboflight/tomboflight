from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bson import ObjectId
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from app.dependencies.auth import require_super_admin
from app.routes import bridge_event_access as route_module
from app.services import bridge_event_access_service as service


REPO_ROOT = Path(__file__).resolve().parents[2]


class FakeCursor(list):
    def sort(self, field_name, direction):
        return FakeCursor(
            sorted(
                self,
                key=lambda item: item.get(field_name) or datetime.min.replace(tzinfo=UTC),
                reverse=direction < 0,
            )
        )

    def limit(self, value):
        return FakeCursor(self[:value])


class FakeCollection:
    def __init__(self, documents=None):
        self.documents = [deepcopy(item) for item in (documents or [])]
        self.indexes = []

    @staticmethod
    def _matches(document, query):
        for key, expected in (query or {}).items():
            actual = document.get(key)
            if isinstance(expected, dict) and "$in" in expected:
                if actual not in expected["$in"]:
                    return False
            elif actual != expected:
                return False
        return True

    @staticmethod
    def _apply(document, update):
        for key, value in (update.get("$set") or {}).items():
            document[key] = value
        for key in (update.get("$unset") or {}):
            document.pop(key, None)

    def create_index(self, *keys, **kwargs):
        self.indexes.append((keys, kwargs))
        return kwargs.get("name")

    def find_one(self, query):
        return next(
            (document for document in self.documents if self._matches(document, query)),
            None,
        )

    def find(self, query):
        return FakeCursor(
            [document for document in self.documents if self._matches(document, query)]
        )

    def insert_one(self, payload):
        active_key = payload.get("active_key")
        if active_key and any(item.get("active_key") == active_key for item in self.documents):
            raise DuplicateKeyError("duplicate active invitation")
        stored = deepcopy(payload)
        stored.setdefault("_id", ObjectId())
        self.documents.append(stored)
        return SimpleNamespace(inserted_id=stored["_id"])

    def update_one(self, query, update):
        document = self.find_one(query)
        if not document:
            return SimpleNamespace(matched_count=0, modified_count=0)
        self._apply(document, update)
        return SimpleNamespace(matched_count=1, modified_count=1)

    def update_many(self, query, update):
        modified = 0
        for document in self.documents:
            if self._matches(document, query):
                self._apply(document, update)
                modified += 1
        return SimpleNamespace(modified_count=modified)

    def find_one_and_update(self, query, update, return_document=None):
        document = self.find_one(query)
        if not document:
            return None
        before = deepcopy(document)
        self._apply(document, update)
        return document if return_document == ReturnDocument.AFTER else before


def _future_expiration():
    return datetime.now(UTC) + timedelta(days=1)


def _configured_values():
    return {
        package_code: f"rotated-fixture-{index:02d}"
        for index, package_code in enumerate(service.PACKAGE_NAMES, start=1)
    }


class TestSecureBridgeEventAccess(unittest.TestCase):
    def test_public_assets_do_not_contain_redeemable_event_values(self):
        paint_html = (REPO_ROOT / "bridge-paint.html").read_text(encoding="utf-8")
        pricing_html = (REPO_ROOT / "pricing.html").read_text(encoding="utf-8")
        paint_js = (REPO_ROOT / "bridge-paint.js").read_text(encoding="utf-8")
        combined = "\n".join((paint_html, pricing_html, paint_js))

        self.assertIsNone(re.search(r"BRIDGE-PAINT-[A-Z0-9][A-Z0-9-]{3,}", combined))
        self.assertNotIn('class="offer-code"', combined)
        self.assertNotIn("data-copy-offer", combined)
        self.assertIn("data-bridge-paint-access-form", paint_html)
        self.assertIn('http-equiv="Content-Security-Policy"', paint_html)
        self.assertIn("sessionStorage", paint_js)
        self.assertIn("history.replaceState", paint_js)

    def test_deployment_example_contains_no_promotion_value(self):
        source = (REPO_ROOT / "backend" / ".env.example").read_text(encoding="utf-8")
        self.assertIn('BRIDGE_PAINT_PROMOTION_CODES_JSON="{}"', source)
        for value in _configured_values().values():
            self.assertNotIn(value, source)

    def test_retired_campaign_prefix_is_rejected_by_runtime_configuration(self):
        payload = {
            "legacy_snapshot": f"{service.LEGACY_EXPOSED_CODE_PREFIX}RETIRED-FIXTURE"
        }
        with patch.object(
            service.settings,
            "bridge_paint_promotion_codes_json",
            json.dumps(payload),
        ):
            with self.assertRaisesRegex(RuntimeError, "revoked and replaced"):
                service._promotion_codes()

    def test_configuration_status_exposes_names_but_never_values(self):
        values = _configured_values()
        with (
            patch.object(
                service.settings,
                "bridge_paint_promotion_codes_json",
                json.dumps(values),
            ),
            patch.object(
                service.settings,
                "bridge_paint_event_expires_at",
                _future_expiration().isoformat(),
            ),
        ):
            status = service.bridge_paint_configuration_status()

        self.assertTrue(status["configured"])
        self.assertEqual(set(status["configured_packages"]), set(service.PACKAGE_NAMES))
        serialized = json.dumps(status)
        for value in values.values():
            self.assertNotIn(value, serialized)

    def test_invitation_stores_only_hash_and_deduplicates_active_delivery(self):
        collection = FakeCollection()
        deliveries = []

        def capture_delivery(**kwargs):
            deliveries.append(kwargs)
            return {"sent": True}

        with (
            patch.object(service.settings, "secret_key", "s" * 64),
            patch.object(service, "_collection", return_value=collection),
            patch.object(service, "_promotion_codes", return_value=_configured_values()),
            patch.object(service, "_event_expiration", side_effect=_future_expiration),
            patch.object(
                service,
                "send_bridge_paint_invitation_email",
                side_effect=capture_delivery,
            ),
            patch.object(service, "_safe_audit"),
        ):
            first = service.create_bridge_paint_invitation(
                current_user={"_id": "ceo-1", "email": "ceo@example.test"},
                email="Invitee@Example.test",
                package_code="legacy_snapshot",
                reason="Verified private event guest",
            )
            second = service.create_bridge_paint_invitation(
                current_user={"_id": "ceo-1", "email": "ceo@example.test"},
                email="invitee@example.test",
                package_code="legacy_snapshot",
                reason="Retry after uncertain browser response",
            )

        self.assertEqual(len(deliveries), 1)
        token = deliveries[0]["access_token"]
        self.assertTrue(token.startswith("tolbe_"))
        stored = collection.documents[0]
        self.assertNotEqual(stored["token_hash"], token)
        self.assertNotIn("access_token", stored)
        self.assertNotIn("promotion_code", stored)
        self.assertEqual(first["id"], second["id"])
        self.assertTrue(first["invitation_created"])
        self.assertFalse(second["invitation_created"])
        self.assertNotIn(token, json.dumps(first))

    def test_one_time_claim_delivers_server_value_without_returning_it(self):
        token = "tolbe_fixture_token_with_enough_entropy_123456"
        secret_value = "rotated-server-only-fixture"
        with patch.object(service.settings, "secret_key", "s" * 64):
            token_hash = service._token_hash(token)
        invitation_id = ObjectId()
        collection = FakeCollection(
            [
                {
                    "_id": invitation_id,
                    "event_code": service.EVENT_CODE,
                    "email": "invitee@example.test",
                    "package_code": "legacy_snapshot",
                    "status": "delivered",
                    "expires_at": _future_expiration(),
                    "token_hash": token_hash,
                    "active_key": "active-fixture",
                }
            ]
        )

        with (
            patch.object(service.settings, "secret_key", "s" * 64),
            patch.object(service, "_collection", return_value=collection),
            patch.object(
                service,
                "_promotion_codes",
                return_value={"legacy_snapshot": secret_value},
            ),
            patch.object(
                service,
                "send_bridge_paint_promotion_email",
                return_value={"sent": True},
            ) as send_email,
            patch.object(service, "_safe_audit"),
        ):
            first = service.request_bridge_paint_access(
                email="invitee@example.test",
                access_token=token,
            )
            second = service.request_bridge_paint_access(
                email="invitee@example.test",
                access_token=token,
            )

        self.assertEqual(first, service.PUBLIC_ACCESS_RESPONSE)
        self.assertEqual(second, service.PUBLIC_ACCESS_RESPONSE)
        self.assertNotIn(secret_value, json.dumps(first))
        self.assertEqual(send_email.call_count, 1)
        self.assertEqual(send_email.call_args.kwargs["promotion_code"], secret_value)
        stored = collection.documents[0]
        self.assertEqual(stored["status"], "fulfilled")
        self.assertNotIn("token_hash", stored)
        self.assertNotIn("active_key", stored)

    def test_public_route_is_generic_no_store_and_dual_rate_limited(self):
        app = FastAPI()
        app.include_router(route_module.router)
        client = TestClient(app)
        with (
            patch.object(
                route_module,
                "request_bridge_paint_access",
                return_value=dict(service.PUBLIC_ACCESS_RESPONSE),
            ),
            patch.object(route_module, "enforce_rate_limit") as rate_limit,
        ):
            response = client.post(
                "/bridge-events/paint/access/request",
                json={
                    "email": "invitee@example.com",
                    "access_token": "tolbe_fixture_token_with_enough_entropy_123456",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), service.PUBLIC_ACCESS_RESPONSE)
        self.assertEqual(rate_limit.call_count, 2)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.headers["pragma"], "no-cache")

    def test_every_admin_invitation_route_requires_super_admin(self):
        protected = {
            "/bridge-events/paint/invitations",
            "/bridge-events/paint/invitations/{invitation_id}/revoke",
        }
        routes = {
            route.path: route
            for route in route_module.router.routes
            if route.path in protected
        }
        self.assertEqual(set(routes), protected)
        for route in routes.values():
            dependencies = {dependency.call for dependency in route.dependant.dependencies}
            self.assertIn(require_super_admin, dependencies)

    def test_duplicate_admin_request_returns_ok_instead_of_false_created_status(self):
        app = FastAPI()
        app.include_router(route_module.router)
        app.dependency_overrides[require_super_admin] = lambda: {
            "_id": "ceo-fixture",
            "email": "ceo@example.com",
        }
        client = TestClient(app)
        with patch.object(
            route_module,
            "create_bridge_paint_invitation",
            return_value={
                "id": "invitation-fixture",
                "status": "delivered",
                "invitation_created": False,
            },
        ) as create:
            response = client.post(
                "/bridge-events/paint/invitations",
                json={
                    "email": "invitee@example.com",
                    "package_code": "legacy_snapshot",
                    "reason": "Retry after uncertain response",
                    "confirmed": True,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["invitation_created"])
        self.assertEqual(create.call_count, 1)
        self.assertEqual(response.headers["cache-control"], "no-store")


if __name__ == "__main__":
    unittest.main()
