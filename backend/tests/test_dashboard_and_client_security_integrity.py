import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_CACHE_VERSION = "20260509-audit"
AUDITED_PORTAL_PAGES = [
    "dashboard.html",
    "upload-hub.html",
    "portrait-upload.html",
    "verification-upload.html",
    "vault-upload.html",
    "household-access.html",
    "link-keys.html",
    "tree-view.html",
    "lineage-certificate.html",
    "intake-review.html",
    "intake-uploads.html",
    "billing.html",
    "account-security.html",
    "digital-collectible.html",
]


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
        self.assertIn("Tomb of Light Continuity OS", source)
        self.assertIn("What To Do Next", source)
        self.assertIn("Upload Hub", source)
        self.assertIn("Upload Photos &amp; Family Records", source)
        self.assertIn("Upload Verification Documents", source)
        self.assertIn("View Intake", source)
        self.assertIn("Portrait / Family Photos", source)
        self.assertIn("Family Records / Documents", source)
        self.assertIn("Verification Documents", source)
        self.assertIn("Optional Narration / Story Materials", source)
        self.assertIn("Private Vault Files", source)
        self.assertIn("Lineage Certificate", source)
        self.assertIn("Members &amp; Access", source)
        self.assertIn("Billing &amp; Cards", source)
        self.assertIn("Account Security", source)
        self.assertIn("Help Center", source)

    def test_customer_dashboard_link_keys_follow_resolved_entitlements(self):
        source = (REPO_ROOT / "dashboard-intake.js").read_text(encoding="utf-8")
        self.assertIn("canUseLinkKeyTools", source)
        self.assertIn("can_manage_link_keys", source)
        self.assertNotIn('showLinkKeys: canUseLinkKeys || packageCode === "legacy_plus"', source)
        self.assertNotIn('navLinkKeys: canUseLinkKeys || packageCode === "legacy_plus"', source)

    def test_household_access_keeps_forbidden_workspace_errors_in_portal(self):
        source = (REPO_ROOT / "household-access.js").read_text(encoding="utf-8")
        self.assertIn("Members & Access is not included in your active package.", source)
        self.assertIn("No active workspace found. Return to Dashboard or contact support.", source)
        self.assertIn("Members & Access is unavailable for this workspace.", source)
        self.assertIn("isSessionInvalidError", source)
        self.assertNotIn("statusCode === 401 || (statusCode === 403", source)

    def test_shared_auth_does_not_classify_every_403_as_auth_failure(self):
        source = (REPO_ROOT / "auth.js").read_text(encoding="utf-8")
        is_auth_failure_body = source.split("function isAuthFailure(error)", 1)[1].split(
            "function sleep", 1
        )[0]
        self.assertIn("statusCode === 403 && isAuthEndpoint", is_auth_failure_body)
        self.assertNotIn('message.includes("forbidden")', is_auth_failure_body)
        self.assertNotIn('message.includes("403") ||', is_auth_failure_body)

    def test_audited_portal_pages_use_audit_css_and_auth_cache_versions(self):
        for page in AUDITED_PORTAL_PAGES:
            with self.subTest(page=page):
                source = (REPO_ROOT / page).read_text(encoding="utf-8")
                self.assertIn(f"styles.css?v={AUDIT_CACHE_VERSION}", source)
                self.assertIn(f"auth.js?v={AUDIT_CACHE_VERSION}", source)

    def test_changed_page_scripts_use_audit_cache_versions(self):
        expected_scripts = {
            "dashboard.html": "dashboard-intake.js",
            "household-access.html": "household-access.js",
            "link-keys.html": "link-keys.js",
        }
        for page, script in expected_scripts.items():
            with self.subTest(page=page):
                source = (REPO_ROOT / page).read_text(encoding="utf-8")
                self.assertIn(f"{script}?v={AUDIT_CACHE_VERSION}", source)

    def test_household_access_has_customer_nav_and_no_admin_controls(self):
        source = (REPO_ROOT / "household-access.html").read_text(encoding="utf-8")
        self.assertIn('href="dashboard.html">Dashboard</a>', source)
        self.assertIn('href="link-keys.html">Link Keys</a>', source)
        self.assertIn('data-logout-btn', source)
        self.assertNotIn("admin-control", source)
        self.assertNotIn("SUPERADMIN", source)


class ClientPrivilegeElevationTests(unittest.TestCase):
    def test_admin_control_center_does_not_use_local_or_session_storage_for_permissions(self):
        source = (REPO_ROOT / "admin-control-center.js").read_text(encoding="utf-8")
        self.assertNotIn(".localStorage", source)
        self.assertNotIn(".sessionStorage", source)
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
