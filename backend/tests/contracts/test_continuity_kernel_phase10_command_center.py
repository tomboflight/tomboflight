from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
HTML_PATH = REPO_ROOT / "admin-control-center.html"
JS_PATH = REPO_ROOT / "admin-control-center.js"
CSS_PATH = REPO_ROOT / "styles.css"
SERVICE_PATH = REPO_ROOT / "backend" / "app" / "services" / "admin_control_service.py"
ROUTE_PATH = REPO_ROOT / "backend" / "app" / "routes" / "admin_control_center.py"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "continuity-kernel-guardrails.yml"


class TestContinuityKernelPhase10CommandCenter(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = HTML_PATH.read_text(encoding="utf-8")
        cls.javascript = JS_PATH.read_text(encoding="utf-8")
        cls.styles = CSS_PATH.read_text(encoding="utf-8")
        cls.service = SERVICE_PATH.read_text(encoding="utf-8")
        cls.routes = ROUTE_PATH.read_text(encoding="utf-8")
        cls.workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    def test_01_control_center_assets_use_phase10_revision(self) -> None:
        self.assertIn("styles.css?v=20260821-phase10-1", self.html)
        self.assertIn("app.js?v=20260821-phase10-1", self.html)
        self.assertIn("admin-control-center.js?v=20260821-phase10-1", self.html)
        self.assertIn('FRONTEND_ASSET_REVISION = "20260821-phase10-1"', self.service)

    def test_02_account_creation_and_closure_are_visible_previewed_workflows(self) -> None:
        for marker in (
            "data-admin-create-dialog",
            "data-admin-create-preview-action",
            "data-admin-create-execute",
            "data-admin-lifecycle-dialog",
            "data-admin-lifecycle-preview",
            "data-admin-lifecycle-typed-confirm",
            "data-super-admin-archive-owned",
        ):
            self.assertIn(marker, self.html + self.javascript)
        self.assertIn('/super-admin/users/preview', self.javascript)
        self.assertIn('/status-action/preview', self.javascript)
        self.assertNotIn('window.prompt("Customer full name:', self.javascript)

    def test_03_account_business_writes_remain_kernel_governed(self) -> None:
        self.assertIn('"customer_account_create"', self.javascript)
        self.assertIn('"account_lifecycle"', self.javascript)
        self.assertIn("submitGovernedOperation(", self.javascript)
        self.assertIn('@router.post("/super-admin/users/preview")', self.routes)
        self.assertGreaterEqual(self.javascript.count("setButtonEnabled(applyButton, false)"), 2)

    def test_04_ceo_owned_job_templates_cannot_assign_ceo_role(self) -> None:
        self.assertIn("TEAM_ACCESS_ROLE_TEMPLATES", self.service)
        for role in (
            "executive_tech_admin",
            "operations_admin",
            "finance_admin",
            "marketing_admin",
        ):
            self.assertIn(f'"{role}"', self.service)
        template_block = self.service.split("TEAM_ACCESS_ROLE_TEMPLATES =", 1)[1].split(")", 1)[0]
        self.assertNotIn("ceo_master_admin", template_block)
        self.assertIn('"immutable": True', self.service)
        self.assertIn('"officer_permissions"', self.javascript)
        self.assertIn('"managed_role_code"', self.service)
        self.assertIn("Only a CEO-approved job-scoped officer role can be assigned.", self.service)

    def test_05_operations_rail_is_grouped_and_role_filtered(self) -> None:
        for group in ("workflow", "finance", "records", "governance"):
            self.assertIn(f'data-admin-nav-group="{group}"', self.html)
        self.assertIn("button.hidden = !allowed", self.javascript)
        self.assertIn("syncRailGroups", self.javascript)

    def test_06_light_theme_uses_readable_surfaces_and_destructive_separation(self) -> None:
        for marker in (
            "Continuity Kernel Phase 10",
            "--admin-text: #132238",
            "--admin-panel: #ffffff",
            ".admin-danger-zone",
            ".admin-workflow-dialog",
            ".btn-danger",
        ):
            self.assertIn(marker, self.styles)

    def test_07_browser_workflows_are_required_in_ci(self) -> None:
        self.assertIn("admin-control-center-browser-execution", self.workflow)
        self.assertIn("npm run test:browser", self.workflow)


if __name__ == "__main__":
    unittest.main()
