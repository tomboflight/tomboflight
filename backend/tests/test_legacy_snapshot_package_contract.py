import inspect
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.core.package_catalog import get_package, get_package_control_profile
from app.routes import family_graph, workspace_access
from app.services.entitlement_service import can_purchase_addon, resolve_project_entitlements


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


class HeirloomLegacyTreePackageContractTests(unittest.TestCase):
    def test_heirloom_legacy_tree_contract_fields(self):
        package = get_package("heirloom_legacy_tree")
        self.assertIsNotNone(package)
        assert package is not None
        self.assertEqual(package.get("package_lane"), "household")
        self.assertEqual(package.get("max_members"), 15)
        self.assertEqual(package.get("max_uploads"), 50)
        self.assertEqual(package.get("max_zoom_layers"), 4)
        self.assertEqual(package.get("max_storage_gb"), 10)
        self.assertTrue(bool(package.get("can_build_household")))
        self.assertTrue(bool(package.get("can_open_family_intake")))
        self.assertTrue(bool(package.get("can_build_family_tree")))
        self.assertTrue(bool(package.get("can_use_viewer")))
        self.assertTrue(bool(package.get("can_use_lineage_certificate")))
        self.assertTrue(bool(package.get("narration_ready_structure")))
        self.assertFalse(bool(package.get("can_use_narration")))
        self.assertFalse(bool(package.get("can_link_households")))
        self.assertFalse(bool(package.get("can_use_link_keys")))
        self.assertFalse(bool(package.get("can_manage_link_keys")))
        self.assertFalse(bool(package.get("maintenance_starts_on_delivery")))
        self.assertCountEqual(
            list(package.get("allowed_addons") or []),
            ["rush_delivery", "on_site_photo_scanning"],
        )

    def test_heirloom_legacy_tree_maintenance_default_is_none(self):
        profile = get_package_control_profile("heirloom_legacy_tree")
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(str(profile.get("maintenance_default")), "none")


class LegacyPlusPackageContractTests(unittest.TestCase):
    def test_legacy_plus_contract_fields(self):
        package = get_package("legacy_plus")
        self.assertIsNotNone(package)
        assert package is not None
        self.assertEqual(package.get("package_lane"), "household")
        self.assertEqual(package.get("max_members"), 30)
        self.assertEqual(package.get("max_uploads"), 100)
        self.assertEqual(package.get("max_zoom_layers"), 5)
        self.assertEqual(package.get("max_storage_gb"), 25)
        self.assertTrue(bool(package.get("can_build_household")))
        self.assertTrue(bool(package.get("can_open_family_intake")))
        self.assertTrue(bool(package.get("can_build_family_tree")))
        self.assertTrue(bool(package.get("can_use_viewer")))
        self.assertTrue(bool(package.get("can_use_narration")))
        self.assertTrue(bool(package.get("narration_ready_structure")))
        self.assertTrue(bool(package.get("premium_archive_structure")))
        self.assertTrue(bool(package.get("can_use_lineage_certificate")))
        self.assertFalse(bool(package.get("can_link_households")))
        self.assertTrue(bool(package.get("can_use_link_keys")))
        self.assertTrue(bool(package.get("can_manage_link_keys")))
        self.assertCountEqual(
            list(package.get("allowed_addons") or []),
            ["rush_delivery", "on_site_photo_scanning", "additional_narration_minute"],
        )

    def test_legacy_plus_maintenance_default_is_none(self):
        profile = get_package_control_profile("legacy_plus")
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(str(profile.get("maintenance_default")), "none")


class FamilyEstateConciergePackageContractTests(unittest.TestCase):
    def test_family_estate_concierge_contract_fields(self):
        package = get_package("family_estate_concierge")
        self.assertIsNotNone(package)
        assert package is not None
        self.assertEqual(package.get("package_lane"), "network")
        self.assertEqual(package.get("max_households"), 3)
        self.assertEqual(package.get("max_family_branches"), 3)
        self.assertEqual(package.get("max_uploads"), 250)
        self.assertEqual(package.get("max_storage_gb"), 50)
        self.assertTrue(bool(package.get("can_build_household")))
        self.assertTrue(bool(package.get("can_build_family_tree")))
        self.assertTrue(bool(package.get("can_link_households")))
        self.assertTrue(bool(package.get("can_use_link_keys")))
        self.assertTrue(bool(package.get("can_manage_link_keys")))
        self.assertTrue(bool(package.get("can_use_viewer")))
        self.assertTrue(bool(package.get("can_use_narration")))
        self.assertTrue(bool(package.get("can_use_lineage_certificate")))
        self.assertTrue(bool(package.get("protected_workspace")))
        self.assertTrue(bool(package.get("guided_intake")))
        self.assertTrue(bool(package.get("premium_consultation_path")))
        self.assertTrue(bool(package.get("custom_structure_planning")))
        self.assertTrue(bool(package.get("white_glove_project_handling")))
        self.assertTrue(bool(package.get("linked_household_structure")))
        self.assertTrue(bool(package.get("network_branch_scope")))
        self.assertTrue(bool(package.get("high_capacity_archival_support")))
        self.assertTrue(bool(package.get("continuity_stewardship_options")))
        self.assertTrue(bool(package.get("lineage_experience_support")))
        self.assertFalse(bool(package.get("organization_command_scope")))
        self.assertFalse(bool(package.get("maintenance_included")))
        self.assertFalse(bool(package.get("can_build_org_chart")))
        self.assertFalse(bool(package.get("can_link_org_units")))
        self.assertCountEqual(
            list(package.get("allowed_addons") or []),
            [
                "extra_mapped_person",
                "extra_zoom_layer",
                "extra_storage",
                "rush_delivery",
                "on_site_photo_scanning",
                "additional_narration_minute",
                "white_glove_archive_support",
            ],
        )

    def test_family_estate_concierge_maintenance_default_is_none(self):
        profile = get_package_control_profile("family_estate_concierge")
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(str(profile.get("maintenance_default")), "none")


class CommandStructureNetworkPackageContractTests(unittest.TestCase):
    def test_command_structure_network_contract_fields(self):
        package = get_package("command_structure_network")
        self.assertIsNotNone(package)
        assert package is not None
        self.assertEqual(package.get("package_lane"), "organization")
        self.assertEqual(package.get("max_org_nodes"), 15)
        self.assertEqual(package.get("organization_node_limit"), 15)
        self.assertEqual(package.get("max_uploads"), 25)
        self.assertTrue(bool(package.get("organization_nodes_enabled")))
        self.assertTrue(bool(package.get("organization_profile_enabled")))
        self.assertTrue(bool(package.get("protected_workspace")))
        self.assertTrue(bool(package.get("guided_intake")))
        self.assertTrue(bool(package.get("command_role_mapping_tools")))
        self.assertTrue(bool(package.get("role_seats_enabled")))
        self.assertTrue(bool(package.get("officer_assignment_history")))
        self.assertTrue(bool(package.get("transition_events_enabled")))
        self.assertTrue(bool(package.get("structured_organization_lineage")))
        self.assertTrue(bool(package.get("verification_support_record_workflows")))
        self.assertTrue(bool(package.get("leadership_structure_viewer")))
        self.assertTrue(bool(package.get("historical_command_view")))
        self.assertTrue(bool(package.get("succession_timeline")))
        self.assertTrue(bool(package.get("linked_organization_support")))
        self.assertTrue(bool(package.get("command_officer_continuity")))
        self.assertTrue(bool(package.get("admin_seat_expansion_paths")))
        self.assertTrue(bool(package.get("organization_command_scope")))
        self.assertTrue(bool(package.get("can_build_org_chart")))
        self.assertTrue(bool(package.get("can_link_org_units")))
        self.assertTrue(bool(package.get("can_use_viewer")))
        self.assertTrue(bool(package.get("can_open_org_intake")))
        self.assertFalse(bool(package.get("can_build_household")))
        self.assertFalse(bool(package.get("can_build_family_tree")))
        self.assertFalse(bool(package.get("can_link_households")))
        self.assertFalse(bool(package.get("can_use_link_keys")))
        self.assertFalse(bool(package.get("can_manage_link_keys")))
        self.assertFalse(bool(package.get("family_household_scope")))
        self.assertFalse(bool(package.get("family_branch_network_scope")))
        self.assertFalse(bool(package.get("family_tree_builder")))
        self.assertFalse(bool(package.get("household_builder")))
        self.assertFalse(bool(package.get("relationship_editor")))
        self.assertFalse(bool(package.get("spouse_child_parent_relationships")))
        self.assertFalse(bool(package.get("maintenance_included")))
        self.assertCountEqual(
            list(package.get("allowed_addons") or []),
            [
                "extra_org_level",
                "extra_admin_seat",
                "extra_storage",
                "rush_delivery",
                "command_report_addon",
            ],
        )
        self.assertNotIn("family_estate_concierge", list(package.get("upgrade_targets") or []))

    def test_command_structure_network_maintenance_default_is_none(self):
        profile = get_package_control_profile("command_structure_network")
        self.assertIsNotNone(profile)
        assert profile is not None
        self.assertEqual(str(profile.get("maintenance_default")), "none")


class EntitlementAddonBoundaryTests(unittest.TestCase):
    def test_heirloom_disallows_addons_that_expand_hard_caps(self):
        resolved = resolve_project_entitlements(
            "heirloom_legacy_tree",
            [
                "extra_mapped_person",
                "extra_zoom_layer",
                "extra_storage",
                # Intentional duplicate verifies idempotent addon processing.
                "extra_mapped_person",
                "rush_delivery",
            ],
        )
        self.assertEqual(resolved.get("max_members"), 15)
        self.assertEqual(resolved.get("max_zoom_layers"), 4)
        self.assertEqual(resolved.get("max_storage_gb"), 10)
        self.assertEqual(list(resolved.get("active_addons") or []), ["rush_delivery"])

    def test_heirloom_cannot_purchase_extra_storage_addon(self):
        self.assertFalse(can_purchase_addon("heirloom_legacy_tree", "extra_storage"))

    def test_legacy_plus_disallows_addons_that_expand_caps_or_network_scope(self):
        resolved = resolve_project_entitlements(
            "legacy_plus",
            [
                "extra_mapped_person",
                "extra_zoom_layer",
                "extra_storage",
                "extra_linked_household",
                "additional_narration_minute",
                "rush_delivery",
            ],
        )
        self.assertEqual(resolved.get("max_members"), 30)
        self.assertEqual(resolved.get("max_zoom_layers"), 5)
        self.assertEqual(resolved.get("max_storage_gb"), 25)
        self.assertEqual(resolved.get("max_households"), 1)
        self.assertFalse(bool(resolved.get("can_link_households")))
        self.assertEqual(
            list(resolved.get("active_addons") or []),
            ["additional_narration_minute", "rush_delivery"],
        )

    def test_legacy_plus_cannot_purchase_network_or_cap_expanding_addons(self):
        self.assertFalse(can_purchase_addon("legacy_plus", "extra_mapped_person"))
        self.assertFalse(can_purchase_addon("legacy_plus", "extra_zoom_layer"))
        self.assertFalse(can_purchase_addon("legacy_plus", "extra_storage"))
        self.assertFalse(can_purchase_addon("legacy_plus", "extra_linked_household"))

    def test_family_estate_concierge_disallows_silent_branch_cap_expansion_addons(self):
        resolved = resolve_project_entitlements(
            "family_estate_concierge",
            [
                "extra_linked_household",
                "extra_branch",
                "white_glove_archive_support",
            ],
        )
        self.assertEqual(resolved.get("max_households"), 3)
        self.assertEqual(
            list(resolved.get("active_addons") or []),
            ["white_glove_archive_support"],
        )

    def test_family_estate_concierge_cannot_purchase_silent_branch_cap_expansion_addons(self):
        self.assertFalse(
            can_purchase_addon("family_estate_concierge", "extra_linked_household")
        )
        self.assertFalse(can_purchase_addon("family_estate_concierge", "extra_branch"))

    def test_command_structure_network_disallows_org_node_cap_expansion_addon(self):
        resolved = resolve_project_entitlements(
            "command_structure_network",
            [
                "extra_org_node",
                "extra_admin_seat",
                "command_report_addon",
            ],
        )
        self.assertEqual(resolved.get("max_org_nodes"), 15)
        self.assertEqual(
            list(resolved.get("active_addons") or []),
            ["extra_admin_seat", "command_report_addon"],
        )

    def test_command_structure_network_cannot_purchase_extra_org_node_addon(self):
        self.assertFalse(can_purchase_addon("command_structure_network", "extra_org_node"))


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
