import asyncio
import io
import json
import unittest
from unittest.mock import patch

from fastapi import Response
from starlette.datastructures import Headers, UploadFile
from starlette.requests import Request

from app import main as main_module
from app.database import DatabaseUnavailableError
from app.routes import health as health_routes
from app.routes import uploads as upload_routes
from app.routes import vault as vault_routes
from app.services import vault_service


def _degraded_service_state():
    return {
        "database_connected": False,
        "service_mode": "degraded",
        "ready": False,
        "degraded_reasons": ["database_unavailable"],
    }


def _ready_service_state():
    return {
        "database_connected": True,
        "service_mode": "ok",
        "ready": True,
        "degraded_reasons": [],
    }


def _upload_workspace_context():
    return {
        "project": {"_id": "project-1"},
        "family": {"_id": "family-1"},
        "member": {"_id": "member-1", "family_id": "family-1"},
        "resolved_entitlements": {
            "can_upload_verification_docs": True,
            "can_upload_portraits": True,
            "allowed_asset_types": ["private_voice_message", "private_video_message"],
        },
        "is_admin": False,
    }


class HealthAndDbUnavailableTests(unittest.TestCase):
    def _request(self, path: str, method: str = "GET") -> Request:
        return Request(
            {
                "type": "http",
                "http_version": "1.1",
                "method": method,
                "path": path,
                "headers": [],
                "query_string": b"",
                "client": ("testclient", 50000),
                "scheme": "http",
                "server": ("testserver", 80),
            }
        )

    def test_health_endpoints_when_db_ready(self):
        with (
            patch.object(health_routes, "get_service_state", return_value=_ready_service_state()),
            patch.object(main_module, "get_service_state", return_value=_ready_service_state()),
        ):
            live = health_routes.liveness_check()
            ready_response = Response()
            ready = health_routes.readiness_check(ready_response)
            health_response = Response()
            health = health_routes.health_check(health_response)
            root = main_module.root()

        self.assertEqual(ready_response.status_code, 200)
        self.assertEqual(health_response.status_code, 200)
        self.assertTrue(ready["ready"])
        self.assertEqual(health["service_mode"], "ok")
        self.assertEqual(live["status"], "ok")
        self.assertTrue(root["database_connected"])

    def test_health_endpoints_when_db_unavailable(self):
        with (
            patch.object(health_routes, "get_service_state", return_value=_degraded_service_state()),
            patch.object(main_module, "get_service_state", return_value=_degraded_service_state()),
        ):
            live = health_routes.liveness_check()
            ready_response = Response()
            ready = health_routes.readiness_check(ready_response)
            health_response = Response()
            health = health_routes.health_check(health_response)
            root = main_module.root()

        self.assertEqual(ready_response.status_code, 503)
        self.assertEqual(health_response.status_code, 503)
        self.assertFalse(live["ready"])
        self.assertEqual(ready["status"], "unavailable")
        self.assertEqual(health["status"], "degraded")
        self.assertEqual(root["service_mode"], "degraded")
        self.assertEqual(root["degraded_reasons"], ["database_unavailable"])

    def test_db_down_upload_route_returns_structured_503(self):
        upload = UploadFile(
            file=io.BytesIO(b"voice-bytes"),
            filename="voice.mp3",
            headers=Headers({"content-type": "audio/mpeg"}),
        )
        with (
            patch.object(upload_routes, "require_workspace_capability", return_value=_upload_workspace_context()),
            patch.object(upload_routes, "require_workspace_member_role"),
            patch.object(
                upload_routes,
                "get_database",
                side_effect=DatabaseUnavailableError("Database connection is currently unavailable."),
            ),
            patch.object(main_module, "get_service_state", return_value=_degraded_service_state()),
        ):
            with self.assertRaises(DatabaseUnavailableError) as ctx:
                asyncio.run(
                    upload_routes.upload_private_media(
                        family_id="family-1",
                        member_id="member-1",
                        asset_type="private_voice_message",
                        privacy_scope="private_to_owner",
                        file=upload,
                        current_user={"id": "owner-1", "email": "owner@example.com"},
                    )
                )
            response = asyncio.run(
                main_module.handle_database_unavailable(
                    self._request("/uploads/private-media", method="POST"),
                    ctx.exception,
                )
            )

        payload = json.loads(response.body.decode("utf-8"))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(payload["error"]["code"], "database_unavailable")
        self.assertFalse(payload["database_connected"])
        self.assertEqual(payload["service_mode"], "degraded")

    def test_db_down_protected_vault_route_returns_structured_503(self):
        with (
            patch.object(vault_routes, "require_workspace_capability", return_value={"project": {"_id": "project-1"}}),
            patch.object(vault_routes, "_require_vault_role"),
            patch.object(
                vault_service,
                "get_database",
                side_effect=DatabaseUnavailableError("Database connection is currently unavailable."),
            ),
            patch.object(main_module, "get_service_state", return_value=_degraded_service_state()),
        ):
            with self.assertRaises(DatabaseUnavailableError) as ctx:
                vault_routes.list_vault_items_route(
                    project_id="project-1",
                    current_user={"id": "owner-1", "email": "owner@example.com"},
                )
            response = asyncio.run(
                main_module.handle_database_unavailable(
                    self._request("/vault/items", method="GET"),
                    ctx.exception,
                )
            )

        payload = json.loads(response.body.decode("utf-8"))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(payload["error"]["code"], "database_unavailable")
        self.assertFalse(payload["ready"])


if __name__ == "__main__":
    unittest.main()
