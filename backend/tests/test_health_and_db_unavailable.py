import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

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
    def setUp(self):
        self.client = TestClient(main_module.app)

    def tearDown(self):
        self.client.app.dependency_overrides.clear()
        self.client.close()

    def test_health_endpoints_when_db_ready(self):
        with (
            patch.object(health_routes, "get_service_state", return_value=_ready_service_state()),
            patch.object(main_module, "get_service_state", return_value=_ready_service_state()),
        ):
            live = self.client.get("/health/live")
            ready = self.client.get("/health/ready")
            health = self.client.get("/health")
            root = self.client.get("/")

        self.assertEqual(live.status_code, 200)
        self.assertEqual(ready.status_code, 200)
        self.assertEqual(health.status_code, 200)
        self.assertEqual(root.status_code, 200)
        self.assertTrue(ready.json()["ready"])
        self.assertEqual(health.json()["service_mode"], "ok")
        self.assertTrue(root.json()["database_connected"])

    def test_health_endpoints_when_db_unavailable(self):
        with (
            patch.object(health_routes, "get_service_state", return_value=_degraded_service_state()),
            patch.object(main_module, "get_service_state", return_value=_degraded_service_state()),
        ):
            live = self.client.get("/health/live")
            ready = self.client.get("/health/ready")
            health = self.client.get("/health")
            root = self.client.get("/")

        self.assertEqual(live.status_code, 200)
        self.assertEqual(ready.status_code, 503)
        self.assertEqual(health.status_code, 503)
        self.assertEqual(root.status_code, 200)
        self.assertFalse(live.json()["ready"])
        self.assertEqual(ready.json()["status"], "unavailable")
        self.assertEqual(health.json()["status"], "degraded")
        self.assertEqual(root.json()["service_mode"], "degraded")
        self.assertEqual(root.json()["degraded_reasons"], ["database_unavailable"])

    def test_db_down_upload_route_returns_structured_503(self):
        self.client.app.dependency_overrides[upload_routes.get_current_user] = (
            lambda: {"id": "owner-1", "email": "owner@example.com"}
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
            response = self.client.post(
                "/uploads/private-media",
                data={
                    "family_id": "family-1",
                    "member_id": "member-1",
                    "asset_type": "private_voice_message",
                    "privacy_scope": "private_to_owner",
                },
                files={"file": ("voice.mp3", b"voice-bytes", "audio/mpeg")},
            )

        payload = response.json()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(payload["error"]["code"], "database_unavailable")
        self.assertFalse(payload["database_connected"])
        self.assertEqual(payload["service_mode"], "degraded")

    def test_db_down_protected_vault_route_returns_structured_503(self):
        self.client.app.dependency_overrides[vault_routes.get_current_user] = (
            lambda: {"id": "owner-1", "email": "owner@example.com"}
        )
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
            response = self.client.get("/vault/items", params={"project_id": "project-1"})

        payload = response.json()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(payload["error"]["code"], "database_unavailable")
        self.assertFalse(payload["ready"])


if __name__ == "__main__":
    unittest.main()
