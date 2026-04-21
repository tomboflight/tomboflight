import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.relationship_catalog import normalize_relationship_type
from app.core.role_catalog import normalize_project_member_role
from app.services import access_context_service, project_membership_service
from app.services.workspace_access_service import require_workspace_member_role


REPO_ROOT = Path(__file__).resolve().parents[2]


class WorkspaceAliasParityRegressionTests(unittest.TestCase):
    def test_role_aliases_normalize_to_expected_codes(self):
        self.assertEqual(normalize_project_member_role("owner"), "billing_owner")
        self.assertEqual(normalize_project_member_role("co_owner"), "co_owner")
        self.assertEqual(normalize_project_member_role("spouse"), "co_owner")
        self.assertEqual(normalize_project_member_role("partner"), "co_owner")

    def test_project_access_snapshot_normalizes_spouse_membership_to_co_owner(self):
        project = {"_id": "project-1", "owner_user_id": "owner-1", "owner_email": "owner@example.com"}
        with patch.object(
            project_membership_service,
            "get_project_member",
            return_value={"project_id": "project-1", "member_role": "spouse", "status": "active"},
        ):
            snapshot = project_membership_service.get_project_access_snapshot(
                project,
                user_id="user-2",
                email="spouse@example.com",
            )
        self.assertTrue(snapshot["accessible"])
        self.assertEqual(snapshot["member_role"], "co_owner")

    def test_project_access_snapshot_normalizes_partner_membership_to_co_owner(self):
        project = {"_id": "project-1", "owner_user_id": "owner-1", "owner_email": "owner@example.com"}
        with patch.object(
            project_membership_service,
            "get_project_member",
            return_value={"project_id": "project-1", "member_role": "partner", "status": "active"},
        ):
            snapshot = project_membership_service.get_project_access_snapshot(
                project,
                user_id="user-3",
                email="partner@example.com",
            )
        self.assertTrue(snapshot["accessible"])
        self.assertEqual(snapshot["member_role"], "co_owner")

    def test_workspace_role_guard_treats_spouse_as_co_owner(self):
        context = require_workspace_member_role(
            {"is_admin": False, "member_role": "spouse"},
            allowed_roles=("billing_owner", "co_owner", "family_manager"),
            detail="Denied",
        )
        self.assertEqual(context["member_role"], "spouse")

    def test_default_project_resolution_uses_memberships_for_relogin(self):
        with (
            patch.object(
                access_context_service,
                "list_accessible_project_ids",
                return_value=["project-membership-1"],
            ) as membership_mock,
            patch.object(
                access_context_service,
                "list_user_project_entitlements",
                return_value=[],
            ) as entitlements_mock,
        ):
            project_id = access_context_service.resolve_default_project_id(
                {"id": "user-1", "email": "coowner@example.com"}
            )
        self.assertEqual(project_id, "project-membership-1")
        membership_mock.assert_called_once()
        entitlements_mock.assert_not_called()


class TreeAndHeaderRegressionTests(unittest.TestCase):
    def test_relationship_aliases_include_step_parent_variants(self):
        self.assertEqual(normalize_relationship_type("stepparent"), "step_parent")
        self.assertEqual(normalize_relationship_type("step parent"), "step_parent")

    def test_tree_view_renders_step_parent_links_as_dotted(self):
        tree_view_js = (REPO_ROOT / "tree-view.js").read_text(encoding="utf-8")
        self.assertIn('stepparent: "step_parent"', tree_view_js)
        self.assertIn('"step parent": "step_parent"', tree_view_js)
        self.assertIn('dashed.style.strokeDasharray = "8 8";', tree_view_js)

    def test_dashboard_header_half_screen_rules_are_present(self):
        styles_css = (REPO_ROOT / "styles.css").read_text(encoding="utf-8")
        self.assertIn("@media (max-width: 1200px)", styles_css)
        self.assertIn(".portal-dashboard-body .site-nav,\n  .portal-dashboard-body .header-actions {\n    display: none;", styles_css)
        self.assertIn(".portal-dashboard-body .menu-toggle {\n    display: inline-flex;", styles_css)

    def test_header_scroll_polish_rules_are_present(self):
        app_js = (REPO_ROOT / "app.js").read_text(encoding="utf-8")
        styles_css = (REPO_ROOT / "styles.css").read_text(encoding="utf-8")
        self.assertIn('header.classList.toggle("is-scrolled", window.scrollY > 18);', app_js)
        self.assertIn(".portal-dashboard-body .site-header.is-scrolled .brand-logo {", styles_css)
        self.assertIn("transform: scale(1.08);", styles_css)

    def test_dashboard_household_nav_is_not_forced_for_portrait_lane(self):
        dashboard_js = (REPO_ROOT / "dashboard-intake.js").read_text(encoding="utf-8")
        self.assertIn("showHouseholdAccess: false", dashboard_js)
        self.assertIn('applyNavVisibility("household-access.html", config.showHouseholdAccess);', dashboard_js)
        self.assertNotIn('applyNavVisibility("household-access.html", true);', dashboard_js)


if __name__ == "__main__":
    unittest.main()
