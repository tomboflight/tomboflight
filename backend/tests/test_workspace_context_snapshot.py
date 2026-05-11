import unittest
from unittest.mock import patch

from app.routes import users as users_routes
from app.services import workspace_access_service


class WorkspaceContextRouteTests(unittest.TestCase):
    def test_workspace_context_route_calls_snapshot_builder(self):
        current_user = {"id": "user-1", "email": "user@example.com"}
        expected = {"status": "active"}
        with patch.object(
            users_routes,
            "build_workspace_context_snapshot",
            return_value=expected,
        ) as build_mock:
            result = users_routes.get_my_workspace_context(
                project_id="project-1",
                family_id="family-1",
                current_user=current_user,
            )

        self.assertIs(result, expected)
        build_mock.assert_called_once_with(
            current_user,
            project_id="project-1",
            family_id="family-1",
        )

    def test_access_context_alias_uses_workspace_snapshot(self):
        current_user = {"id": "user-1", "email": "user@example.com"}
        expected = {"status": "active", "blocking_reason": None}
        with patch.object(
            users_routes,
            "build_workspace_context_snapshot",
            return_value=expected,
        ) as build_mock:
            result = users_routes.get_my_access_context(
                project_id="project-1",
                family_id="family-1",
                current_user=current_user,
            )

        self.assertIs(result, expected)
        build_mock.assert_called_once_with(
            current_user,
            project_id="project-1",
            family_id="family-1",
        )


class WorkspaceEntitlementRepairTests(unittest.TestCase):
    def test_entitlement_map_attempts_repair_for_package_mismatch(self):
        project = {"_id": "69c0402387082765345cff8c"}
        current_user = {"id": "user-1", "email": "larrycr27@gmail.com"}
        strict_result = {
            "package_code": "legacy_plus",
            "active_addons": [],
            "resolved_entitlements": {"can_use_link_keys": True},
            "entitlement": {"status": "active"},
            "paid_order": {"status": "paid"},
        }
        with (
            patch.object(
                workspace_access_service,
                "resolve_strict_paid_active_project_entitlement",
                side_effect=[
                    workspace_access_service.WorkspaceEntitlementError(
                        "package_code_mismatch",
                        "mismatch",
                    ),
                    strict_result,
                ],
            ),
            patch.object(
                workspace_access_service,
                "repair_workspace_entitlements_for_user",
                return_value={"repaired": [{}]},
            ) as repair_mock,
        ):
            result = workspace_access_service._resolve_project_entitlement_map(
                project,
                current_user=current_user,
            )

        self.assertEqual(result.get("package_code"), "legacy_plus")
        repair_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
