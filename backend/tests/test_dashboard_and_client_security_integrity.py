import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


class CustomerDashboardIntegrityTests(unittest.TestCase):
    def test_customer_dashboard_has_single_package_access_block(self):
        source = (REPO_ROOT / "dashboard.html").read_text(encoding="utf-8")
        self.assertEqual(source.count("data-package-access-panel"), 1)

    def test_customer_dashboard_has_single_legacy_anchor_panel(self):
        source = (REPO_ROOT / "dashboard.html").read_text(encoding="utf-8")
        self.assertEqual(source.count("data-legacy-anchor-proof"), 1)

    def test_customer_dashboard_has_single_primary_action_row(self):
        source = (REPO_ROOT / "dashboard.html").read_text(encoding="utf-8")
        self.assertEqual(source.count("data-workspace-action-bar"), 1)
        self.assertNotIn("portal-outputs-panel", source)

    def test_customer_dashboard_upload_center_and_next_step_are_present(self):
        source = (REPO_ROOT / "dashboard.html").read_text(encoding="utf-8")
        self.assertIn("What To Do Next", source)
        self.assertIn("Upload Center", source)
        self.assertIn("Upload Photos &amp; Family Records", source)
        self.assertIn("Upload Verification Docs", source)
        self.assertIn("Continue Intake", source)
        self.assertIn("Portrait / Family Photos", source)
        self.assertIn("Family Records / Documents", source)
        self.assertIn("Verification Documents", source)
        self.assertIn("Optional Narration / Story Materials", source)


class ClientPrivilegeElevationTests(unittest.TestCase):
    def test_admin_control_center_does_not_use_local_or_session_storage_for_permissions(self):
        source = (REPO_ROOT / "admin-control-center.js").read_text(encoding="utf-8")
        self.assertNotIn("localStorage", source)
        self.assertNotIn("sessionStorage", source)
        self.assertIn('"/admin/control-center/access-profile"', source)

    def test_thank_you_page_does_not_activate_entitlements_from_query_params(self):
        source = (REPO_ROOT / "thank-you.js").read_text(encoding="utf-8")
        self.assertIn("getParam(", source)
        self.assertNotIn("/project-entitlements", source)
        self.assertNotIn("/admin/control-center", source)
        self.assertNotIn("generate_entitlement", source)
        self.assertNotIn("upsert_project_entitlement", source)


if __name__ == "__main__":
    unittest.main()
