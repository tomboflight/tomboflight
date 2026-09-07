import unittest
from unittest.mock import patch

from app.services import link_key_service, package_acquisition_service
from app.services.package_acquisition_service import ProjectAcquisitionError


class VerifiedPackageAcquisitionTests(unittest.TestCase):
    def _entitlement(self, code="family_estate_concierge", lane="network"):
        return {
            "status": "active",
            "package_code": code,
            "package_lane": lane,
            "active_addons": [],
        }

    def test_paid_order_plus_active_entitlement_is_verified(self):
        with (
            patch.object(
                package_acquisition_service,
                "_get_active_entitlement",
                return_value=self._entitlement(),
            ),
            patch.object(
                package_acquisition_service,
                "_get_paid_package_order",
                return_value={
                    "_id": "order-1",
                    "item_type": "package",
                    "status": "paid",
                    "package_code": "family_estate_concierge",
                    "package_lane": "network",
                },
            ),
            patch.object(
                package_acquisition_service,
                "_get_active_governed_package_assignment",
                return_value=None,
            ),
        ):
            result = package_acquisition_service.resolve_verified_project_acquisition(
                "69c0402387082765345cff8c"
            )

        self.assertEqual(result["acquisition_source"], "paid_order")
        self.assertTrue(result["payment_required"])
        self.assertEqual(result["package_code"], "family_estate_concierge")
        self.assertTrue(result["resolved_entitlements"]["can_link_households"])

    def test_governed_grant_plus_active_entitlement_is_verified(self):
        with (
            patch.object(
                package_acquisition_service,
                "_get_active_entitlement",
                return_value=self._entitlement(),
            ),
            patch.object(
                package_acquisition_service,
                "_get_paid_package_order",
                return_value=None,
            ),
            patch.object(
                package_acquisition_service,
                "_get_active_governed_package_assignment",
                return_value={
                    "_id": "assignment-1",
                    "status": "active",
                    "new_package": "family_estate_concierge",
                    "source": "ceo_admin_assignment",
                    "authorization_source": "ceo_master_admin",
                    "billing_classification": "complimentary_package",
                    "payment_required": False,
                },
            ),
        ):
            result = package_acquisition_service.resolve_verified_project_acquisition(
                "69c0402387082765345cff8c"
            )

        self.assertEqual(result["acquisition_source"], "governed_grant")
        self.assertFalse(result["payment_required"])
        self.assertIsNone(result["paid_order"])
        self.assertEqual(
            result["governed_assignment"]["authorization_source"],
            "ceo_master_admin",
        )

    def test_entitlement_without_verified_acquisition_fails_closed(self):
        with (
            patch.object(
                package_acquisition_service,
                "_get_active_entitlement",
                return_value=self._entitlement(),
            ),
            patch.object(
                package_acquisition_service,
                "_get_paid_package_order",
                return_value=None,
            ),
            patch.object(
                package_acquisition_service,
                "_get_active_governed_package_assignment",
                return_value=None,
            ),
            patch.object(package_acquisition_service, "_audit_drift"),
        ):
            with self.assertRaises(ProjectAcquisitionError) as captured:
                package_acquisition_service.resolve_verified_project_acquisition(
                    "69c0402387082765345cff8c"
                )

        self.assertEqual(captured.exception.reason, "missing_acquisition_source")

    def test_missing_active_entitlement_fails_even_with_paid_order(self):
        with (
            patch.object(
                package_acquisition_service,
                "_get_active_entitlement",
                return_value=None,
            ),
            patch.object(package_acquisition_service, "_audit_drift"),
        ):
            with self.assertRaises(ProjectAcquisitionError) as captured:
                package_acquisition_service.resolve_verified_project_acquisition(
                    "69c0402387082765345cff8c"
                )

        self.assertEqual(captured.exception.reason, "missing_active_entitlement")

    def test_package_mismatch_between_entitlement_and_acquisition_fails(self):
        with (
            patch.object(
                package_acquisition_service,
                "_get_active_entitlement",
                return_value=self._entitlement("legacy_plus", "household"),
            ),
            patch.object(
                package_acquisition_service,
                "_get_paid_package_order",
                return_value={
                    "item_type": "package",
                    "status": "paid",
                    "package_code": "family_estate_concierge",
                    "package_lane": "network",
                },
            ),
            patch.object(
                package_acquisition_service,
                "_get_active_governed_package_assignment",
                return_value=None,
            ),
            patch.object(package_acquisition_service, "_audit_drift"),
        ):
            with self.assertRaises(ProjectAcquisitionError) as captured:
                package_acquisition_service.resolve_verified_project_acquisition(
                    "69c0402387082765345cff8c"
                )

        self.assertEqual(captured.exception.reason, "package_code_mismatch")

    def test_lane_mismatch_fails_closed(self):
        with (
            patch.object(
                package_acquisition_service,
                "_get_active_entitlement",
                return_value=self._entitlement("family_estate_concierge", "household"),
            ),
            patch.object(
                package_acquisition_service,
                "_get_paid_package_order",
                return_value={
                    "item_type": "package",
                    "status": "paid",
                    "package_code": "family_estate_concierge",
                    "package_lane": "network",
                },
            ),
            patch.object(
                package_acquisition_service,
                "_get_active_governed_package_assignment",
                return_value=None,
            ),
            patch.object(package_acquisition_service, "_audit_drift"),
        ):
            with self.assertRaises(ProjectAcquisitionError) as captured:
                package_acquisition_service.resolve_verified_project_acquisition(
                    "69c0402387082765345cff8c"
                )

        self.assertEqual(captured.exception.reason, "package_lane_mismatch")


class LinkKeyVerifiedAcquisitionTests(unittest.TestCase):
    def test_raw_project_package_metadata_cannot_unlock_link_keys(self):
        with patch.object(
            link_key_service,
            "resolve_verified_project_acquisition",
            side_effect=ProjectAcquisitionError(
                "missing_acquisition_source",
                "no verified acquisition",
            ),
        ):
            allowed = link_key_service._project_has_access_signal(
                "69c0402387082765345cff8c",
                {
                    "package_code": "family_estate_concierge",
                    "package_slug": "family_estate_concierge",
                    "package_type": "family_estate_concierge",
                },
            )

        self.assertFalse(allowed)

    def test_governed_family_estate_grant_can_support_household_links(self):
        acquisition = {
            "acquisition_source": "governed_grant",
            "resolved_entitlements": {
                "can_use_link_keys": True,
                "can_link_households": True,
            },
        }
        with patch.object(
            link_key_service,
            "resolve_verified_project_acquisition",
            return_value=acquisition,
        ):
            self.assertTrue(
                link_key_service.project_supports_household_links(
                    "69c0402387082765345cff8c"
                )
            )
            self.assertTrue(
                link_key_service.project_supports_link_keys(
                    "69c0402387082765345cff8c"
                )
            )

    def test_legacy_plus_generic_link_entitlement_does_not_equal_branch_linking(self):
        acquisition = {
            "acquisition_source": "paid_order",
            "resolved_entitlements": {
                "can_use_link_keys": True,
                "can_manage_link_keys": True,
                "can_link_households": False,
            },
        }
        with patch.object(
            link_key_service,
            "resolve_verified_project_acquisition",
            return_value=acquisition,
        ):
            self.assertTrue(
                link_key_service.project_supports_link_keys(
                    "69c0402387082765345cff8c"
                )
            )
            self.assertFalse(
                link_key_service.project_supports_household_links(
                    "69c0402387082765345cff8c"
                )
            )

    def test_manager_role_must_be_owner_or_co_owner(self):
        project = {"_id": "69c0402387082765345cff8c"}
        acquisition = {
            "acquisition_source": "paid_order",
            "resolved_entitlements": {"can_link_households": True},
        }
        with (
            patch.object(link_key_service, "get_project_by_id", return_value=project),
            patch.object(
                link_key_service,
                "resolve_verified_project_acquisition",
                return_value=acquisition,
            ),
            patch.object(
                link_key_service,
                "get_project_access_snapshot",
                return_value={"accessible": True, "member_role": "viewer"},
            ),
        ):
            self.assertFalse(
                link_key_service.user_can_manage_project(
                    "69c0402387082765345cff8c",
                    "user-1",
                    "user@example.com",
                )
            )

        with (
            patch.object(link_key_service, "get_project_by_id", return_value=project),
            patch.object(
                link_key_service,
                "resolve_verified_project_acquisition",
                return_value=acquisition,
            ),
            patch.object(
                link_key_service,
                "get_project_access_snapshot",
                return_value={"accessible": True, "member_role": "co_owner"},
            ),
        ):
            self.assertTrue(
                link_key_service.user_can_manage_project(
                    "69c0402387082765345cff8c",
                    "user-1",
                    "user@example.com",
                )
            )


if __name__ == "__main__":
    unittest.main()
