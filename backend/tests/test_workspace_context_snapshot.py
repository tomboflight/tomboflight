import unittest
from unittest.mock import patch

from app.routes import users as users_routes
from app.services import workspace_access_service
from app.services.package_acquisition_service import ProjectAcquisitionError


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
    def test_entitlement_map_attempts_repair_for_paid_package_mismatch(self):
        project = {"_id": "69c0402387082765345cff8c"}
        current_user = {"id": "user-1", "email": "larrycr27@gmail.com"}
        strict_result = {
            "package_code": "legacy_plus",
            "package_lane": "household",
            "active_addons": [],
            "resolved_entitlements": {"can_use_link_keys": True},
            "entitlement": {"status": "active"},
            "paid_order": {"status": "paid"},
            "governed_assignment": None,
            "acquisition_source": "paid_order",
            "payment_required": True,
        }
        with (
            patch.object(
                workspace_access_service,
                "resolve_verified_project_acquisition",
                side_effect=[
                    ProjectAcquisitionError(
                        "package_code_mismatch",
                        "mismatch",
                    ),
                    strict_result,
                ],
            ),
            patch.object(
                workspace_access_service,
                "_get_paid_package_order_for_project",
                return_value={"status": "paid"},
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
        self.assertEqual(result.get("acquisition_source"), "paid_order")
        repair_mock.assert_called_once()

    def test_governed_grant_does_not_require_paid_order_repair(self):
        project = {"_id": "69c0402387082765345cff8c"}
        current_user = {"id": "user-1", "email": "customer@example.com"}
        grant_result = {
            "package_code": "family_estate_concierge",
            "package_lane": "network",
            "active_addons": [],
            "resolved_entitlements": {"can_link_households": True},
            "entitlement": {"status": "active"},
            "paid_order": None,
            "governed_assignment": {
                "status": "active",
                "authorization_source": "ceo_master_admin",
                "billing_classification": "complimentary_package",
            },
            "acquisition_source": "governed_grant",
            "payment_required": False,
        }
        with (
            patch.object(
                workspace_access_service,
                "resolve_verified_project_acquisition",
                return_value=grant_result,
            ),
            patch.object(
                workspace_access_service,
                "repair_workspace_entitlements_for_user",
            ) as repair_mock,
        ):
            result = workspace_access_service._resolve_project_entitlement_map(
                project,
                current_user=current_user,
            )

        self.assertEqual(result.get("acquisition_source"), "governed_grant")
        self.assertFalse(result.get("payment_required"))
        repair_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
