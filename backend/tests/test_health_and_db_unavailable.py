import asyncio
import io
import json
import tempfile
import unittest
from unittest.mock import patch

from fastapi import Response
from starlette.datastructures import Headers, UploadFile
from starlette.requests import Request

from app import main as main_module
from app import database as database_module
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

    def test_production_operational_readiness_reports_controls_only_to_ceo_surface(self):
        with tempfile.TemporaryDirectory() as mount_path:
            with (
                patch.object(database_module, "db", object()),
                patch.object(database_module.settings, "environment", "production"),
                patch.object(database_module.settings, "secret_key", "s" * 48),
                patch.object(database_module.settings, "stripe_secret_key", "sk_live_configured"),
                patch.object(database_module.settings, "stripe_publishable_key", "pk_live_configured"),
                patch.object(database_module.settings, "stripe_webhook_secret", "whsec_configured"),
                patch.object(database_module.settings, "postmark_server_token", "postmark-configured"),
                patch.object(database_module.settings, "postmark_server_token_file", ""),
                patch.object(database_module.settings, "postmark_from_email", "security@tomboflight.com"),
                patch.object(
                    database_module.settings,
                    "upload_scan_hook",
                    "app.services.clamav_upload_scanner:scan",
                ),
                patch.object(database_module.settings, "upload_clamav_host", "127.0.0.1"),
                patch.object(database_module.settings, "upload_scan_command", ""),
                patch.object(database_module.settings, "upload_scan_fail_closed", True),
                patch.object(database_module.settings, "render_disk_mount_path", mount_path),
                patch.dict(
                    database_module.os.environ,
                    {
                        "RENDER_GIT_COMMIT": "phase11commit",
                        "CONTINUITY_EXECUTION_KILL_SWITCH": "",
                    },
                ),
            ):
                public_state = database_module.get_service_state()
                detailed_state = database_module.get_service_state(
                    include_operational_details=True
                )

        self.assertTrue(public_state["operational_ready"])
        self.assertNotIn("components", public_state)
        self.assertNotIn("operational_degraded_reasons", public_state)
        self.assertNotIn("release", public_state)
        self.assertTrue(detailed_state["operational_ready"])
        self.assertEqual(detailed_state["operational_degraded_reasons"], [])
        self.assertEqual(detailed_state["release"]["commit"], "phase11commit")
        self.assertTrue(detailed_state["components"]["production_signing_key"]["configured"])
        self.assertTrue(detailed_state["components"]["stripe_webhooks"]["configured"])
        self.assertEqual(detailed_state["components"]["upload_scanner"]["mode"], "active")
        self.assertTrue(detailed_state["components"]["private_upload_storage"]["persistent"])

    def test_production_operational_readiness_fails_closed_on_missing_controls(self):
        release_env = {
            "RENDER_GIT_COMMIT": "",
            "RELEASE_SHA": "",
            "GIT_COMMIT": "",
            "COMMIT_SHA": "",
            "VERCEL_GIT_COMMIT_SHA": "",
            "CONTINUITY_EXECUTION_KILL_SWITCH": "true",
        }
        with (
            patch.object(database_module, "db", object()),
            patch.object(database_module.settings, "environment", "production"),
            patch.object(database_module.settings, "secret_key", "change-me"),
            patch.object(database_module.settings, "stripe_secret_key", ""),
            patch.object(database_module.settings, "stripe_publishable_key", ""),
            patch.object(database_module.settings, "stripe_webhook_secret", ""),
            patch.object(database_module.settings, "postmark_server_token", ""),
            patch.object(database_module.settings, "postmark_server_token_file", ""),
            patch.object(database_module.settings, "upload_scan_hook", ""),
            patch.object(database_module.settings, "upload_scan_command", "legacy-command"),
            patch.object(database_module.settings, "render_disk_mount_path", ""),
            patch.dict(database_module.os.environ, release_env),
        ):
            detailed_state = database_module.get_service_state(
                include_operational_details=True
            )

        reasons = set(detailed_state["operational_degraded_reasons"])
        self.assertFalse(detailed_state["operational_ready"])
        self.assertTrue(
            {
                "production_signing_key_invalid",
                "stripe_configuration_incomplete",
                "postmark_configuration_incomplete",
                "upload_scanner_unavailable_quarantine_only",
                "private_upload_storage_not_persistent",
                "deployment_revision_unavailable",
                "continuity_execution_disabled",
            }.issubset(reasons)
        )
        self.assertTrue(
            detailed_state["components"]["upload_scanner"][
                "legacy_command_ignored"
            ]
        )

    def test_operational_readiness_route_sets_503_for_ceo_when_degraded(self):
        state = {
            **_ready_service_state(),
            "operational_ready": False,
            "operational_degraded_reasons": ["continuity_execution_disabled"],
            "components": {},
            "release": {"version": "1.0.0", "commit": "abc123"},
        }
        with patch.object(health_routes, "get_service_state", return_value=state) as get_state:
            response = Response()
            payload = health_routes.operational_readiness_check(
                response,
                {"email": "l.robinson@tomboflight.com"},
            )

        get_state.assert_called_once_with(include_operational_details=True)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(payload["status"], "unavailable")
        self.assertEqual(
            payload["operational_degraded_reasons"],
            ["continuity_execution_disabled"],
        )

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
