import inspect
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.core.package_catalog import get_package, get_package_control_profile
from app.routes import family_graph, workspace_access


class LegacySnapshotPackageContractTests(unittest.TestCase):
    def test_legacy_snapshot_contract_fields(self):
        package = get_package("legacy_snapshot")
        self.assertIsNotNone(package)
        assert package is not None
        self.assertEqual(package.get("package_lane"), "portrait")
        self.assertEqual(package.get("max_uploads"), 3)
        self.assertEqual(package.get("max_members"), 1)
        self.assertEqual(package.get("max_zoom_layers"), 0)
        self.assertFalse(bool(package.get("can_use_viewer")))
        self.assertTrue(bool(package.get("can_use_secure_share_viewer")))
        self.assertTrue(bool(package.get("can_upload_portraits")))
        self.assertFalse(bool(package.get("can_build_household")))
        self.assertFalse(bool(package.get("can_build_family_tree")))
        self.assertFalse(bool(package.get("can_link_households")))
        self.assertFalse(bool(package.get("can_use_link_keys")))
        self.assertGreater(len(list(package.get("upgrade_targets") or [])), 0)

    def test_legacy_snapshot_maintenance_default_is_not_auto_enabled(self):
        profile = get_package_control_profile("legacy_snapshot")
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(str(profile.get("maintenance_default")), "none")

    def test_legacy_snapshot_verification_upload_path_is_explicitly_enabled(self):
        package = get_package("legacy_snapshot")
        self.assertIsNotNone(package)
        assert package is not None
        self.assertTrue(bool(package.get("can_upload_verification_docs")))


class LegacyPortraitIntroPackageContractTests(unittest.TestCase):
    def test_legacy_portrait_intro_contract_fields(self):
        package = get_package("legacy_portrait_intro")
        self.assertIsNotNone(package)
        assert package is not None
        self.assertEqual(package.get("package_lane"), "portrait")
        self.assertEqual(package.get("max_uploads"), 5)
        self.assertEqual(package.get("max_members"), 1)
        self.assertEqual(package.get("max_zoom_layers"), 0)
        self.assertFalse(bool(package.get("can_use_viewer")))
        self.assertTrue(bool(package.get("can_use_secure_share_viewer")))
        self.assertTrue(bool(package.get("can_upload_portraits")))
        self.assertTrue(bool(package.get("can_upload_verification_docs")))
        self.assertFalse(bool(package.get("can_build_household")))
        self.assertFalse(bool(package.get("can_build_family_tree")))
        self.assertFalse(bool(package.get("can_link_households")))
        self.assertFalse(bool(package.get("can_use_link_keys")))
        self.assertGreater(len(list(package.get("upgrade_targets") or [])), 0)

    def test_legacy_portrait_intro_maintenance_default_is_none(self):
        profile = get_package_control_profile("legacy_portrait_intro")
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(str(profile.get("maintenance_default")), "none")


class DigitalLegacyPortraitPackageContractTests(unittest.TestCase):
    def test_digital_legacy_portrait_contract_fields(self):
        package = get_package("digital_legacy_portrait")
        self.assertIsNotNone(package)
        assert package is not None
        self.assertEqual(package.get("package_lane"), "portrait")
        self.assertEqual(package.get("max_uploads"), 10)
        self.assertEqual(package.get("max_storage_gb"), 1)
        self.assertEqual(package.get("max_members"), 1)
        self.assertTrue(bool(package.get("can_use_viewer")))
        self.assertTrue(bool(package.get("can_upload_portraits")))
        self.assertTrue(bool(package.get("can_upload_verification_docs")))
        self.assertTrue(bool(package.get("can_use_link_keys")))
        self.assertTrue(bool(package.get("can_manage_link_keys")))
        self.assertFalse(bool(package.get("can_build_household")))
        self.assertFalse(bool(package.get("can_build_family_tree")))
        self.assertFalse(bool(package.get("can_link_households")))
        self.assertGreater(len(list(package.get("upgrade_targets") or [])), 0)

    def test_digital_legacy_portrait_maintenance_default_is_none(self):
        profile = get_package_control_profile("digital_legacy_portrait")
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(str(profile.get("maintenance_default")), "none")


class HouseholdFoundationPackageContractTests(unittest.TestCase):
    def test_household_foundation_contract_fields(self):
        package = get_package("household_foundation")
        self.assertIsNotNone(package)
        assert package is not None
        self.assertEqual(package.get("package_lane"), "household")
        self.assertEqual(package.get("max_members"), 6)
        self.assertEqual(package.get("max_uploads"), 20)
        self.assertEqual(package.get("max_zoom_layers"), 2)
        self.assertEqual(package.get("max_storage_gb"), 3)
        self.assertTrue(bool(package.get("can_build_household")))
        self.assertTrue(bool(package.get("can_open_family_intake")))
        self.assertTrue(bool(package.get("can_build_family_tree")))
        self.assertTrue(bool(package.get("can_use_lineage_certificate")))
        self.assertFalse(bool(package.get("can_link_households")))
        self.assertFalse(bool(package.get("can_use_link_keys")))
        self.assertFalse(bool(package.get("can_manage_link_keys")))
        self.assertFalse(bool(package.get("can_use_narration")))
        self.assertFalse(bool(package.get("maintenance_starts_on_delivery")))
        self.assertCountEqual(
            list(package.get("allowed_addons") or []),
            ["rush_delivery", "on_site_photo_scanning"],
        )

    def test_household_foundation_maintenance_default_is_none(self):
        profile = get_package_control_profile("household_foundation")
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(str(profile.get("maintenance_default")), "none")


class LegacySnapshotGatingRegressionTests(unittest.TestCase):
    def test_family_graph_route_no_longer_uses_upload_capabilities_for_tree_access(self):
        source = inspect.getsource(family_graph.get_family_graph)
        self.assertIn('"can_build_family_tree"', source)
        self.assertNotIn('"can_upload_verification_docs"', source)
        self.assertNotIn('"can_upload_portraits"', source)

    def test_workspace_access_members_blocked_without_household_management_entitlement(self):
        with (
            patch.object(workspace_access, "_assert_project_access", return_value=None),
            patch.object(
                workspace_access,
                "resolve_workspace_context",
                return_value={"resolved_entitlements": {"can_build_household": False}},
            ),
        ):
            with self.assertRaises(HTTPException):
                workspace_access.get_project_members(
                    "project-1",
                    current_user={"id": "user-1", "email": "user@example.com"},
                )

    def test_workspace_access_members_allowed_with_household_management_entitlement(self):
        with (
            patch.object(workspace_access, "_assert_project_access", return_value=None),
            patch.object(
                workspace_access,
                "resolve_workspace_context",
                return_value={"resolved_entitlements": {"can_build_household": True}},
            ),
            patch.object(workspace_access, "list_project_members", return_value=[]),
            patch.object(workspace_access, "_with_member_identity_fields", side_effect=lambda items: items),
        ):
            payload = workspace_access.get_project_members(
                "project-1",
                current_user={"id": "user-1", "email": "user@example.com"},
            )
        self.assertEqual(payload, {"items": []})


if __name__ == "__main__":
    unittest.main()
