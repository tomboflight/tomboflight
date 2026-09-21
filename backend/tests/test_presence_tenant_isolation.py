from __future__ import annotations

import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.routes import presence as presence_routes
from app.services import presence_service


class PresenceTenantIsolationTests(unittest.TestCase):
    def test_customer_status_excludes_other_tenant_rooms_and_counts(self) -> None:
        current_user = {
            "_id": "user-a",
            "email": "tenant-a@example.com",
            "role": "user",
        }
        global_snapshot = {
            "project:project-a": 2,
            "family:family-a": 1,
            "project:project-b": 7,
            "family:family-b": 3,
            "experience": 9,
        }

        with patch.object(
            presence_service.websocket_manager,
            "snapshot",
            return_value=global_snapshot,
        ), patch.object(
            presence_service,
            "resolve_authorized_presence_channels",
            return_value={"project:project-a", "family:family-a"},
        ):
            result = presence_service.build_presence_status(current_user)

        self.assertEqual(
            result["channels"],
            {
                "project:project-a": 2,
                "family:family-a": 1,
            },
        )
        self.assertEqual(result["active_connections"], 3)
        self.assertNotIn("project:project-b", result["channels"])
        self.assertNotIn("family:family-b", result["channels"])
        self.assertNotIn("experience", result["channels"])

    def test_canonical_internal_admin_can_receive_global_operational_view(self) -> None:
        current_user = {
            "_id": "operations-admin",
            "email": "operations@example.com",
            "role": "operations_admin",
        }
        global_snapshot = {
            "project:project-a": 2,
            "family:family-a": 1,
            "project:project-b": 7,
            "experience": 4,
        }

        with patch.object(
            presence_service.websocket_manager,
            "snapshot",
            return_value=global_snapshot,
        ), patch.object(
            presence_service,
            "resolve_authorized_presence_channels",
            side_effect=AssertionError(
                "Administrators must use the explicit global-presence path."
            ),
        ):
            result = presence_service.build_presence_status(current_user)

        self.assertEqual(result["channels"], global_snapshot)
        self.assertEqual(result["active_connections"], 14)

    def test_authorization_resolution_rejects_unrelated_workspace_candidates(self) -> None:
        current_user = {
            "_id": "user-a",
            "email": "tenant-a@example.com",
            "role": "user",
        }

        def resolve_context(
            user: dict[str, object],
            *,
            project_id: str = "",
            family_id: str = "",
            member_id: str = "",
        ) -> dict[str, object]:
            del user, member_id
            if project_id == "project-a" or family_id == "family-a":
                return {
                    "project": {"_id": "project-a"},
                    "family": {"_id": "family-a"},
                }
            raise HTTPException(status_code=403, detail="Not authorized.")

        with patch.object(
            presence_service,
            "_candidate_presence_workspace_ids",
            return_value=(
                {"project-a", "project-b"},
                {"family-a", "family-b"},
            ),
        ), patch.object(
            presence_service,
            "resolve_workspace_context",
            side_effect=resolve_context,
        ):
            channels = presence_service.resolve_authorized_presence_channels(
                current_user
            )

        self.assertEqual(
            channels,
            {"project:project-a", "family:family-a"},
        )

    def test_route_passes_authenticated_identity_into_presence_filter(self) -> None:
        current_user = {
            "_id": "user-a",
            "email": "tenant-a@example.com",
            "role": "user",
        }
        expected = {
            "status": "live",
            "active_connections": 0,
            "channels": {},
            "websocket_paths": [],
        }

        with patch.object(
            presence_routes,
            "build_presence_status",
            return_value=expected,
        ) as build_status:
            result = presence_routes.get_presence_status_route(current_user)

        self.assertEqual(result, expected)
        build_status.assert_called_once_with(current_user)

    def test_workspace_overview_excludes_global_experience_connections(self) -> None:
        with patch.object(
            presence_service.websocket_manager,
            "snapshot",
            return_value={
                "project:project-a": 2,
                "family:family-a": 1,
                "project:project-b": 8,
                "experience": 100,
            },
        ):
            result = presence_service.build_presence_overview(
                project_id="project-a",
                family_id="family-a",
            )

        self.assertEqual(result["active_connections"], 3)


if __name__ == "__main__":
    unittest.main()
