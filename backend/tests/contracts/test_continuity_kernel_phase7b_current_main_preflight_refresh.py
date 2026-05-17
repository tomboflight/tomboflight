import ast
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase7b_current_main_preflight_refresh.md"
ROUTE_PATH = REPO_ROOT / "backend" / "app" / "routes" / "admin_continuity_preview.py"
ROUTES_DIR = REPO_ROOT / "backend" / "app" / "routes"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "continuity-kernel-guardrails.yml"
SCRIPTS_DIR = REPO_ROOT / "backend" / "scripts"
EXECUTABLE_PERMISSION_BITS = 0o111


class TestContinuityKernelPhase7BCurrentMainPreflightRefresh(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc_exists = DOC_PATH.exists()
        cls.doc_text = DOC_PATH.read_text(encoding="utf-8") if cls.doc_exists else ""
        cls.doc_lower = cls.doc_text.lower()

        cls.route_source = ROUTE_PATH.read_text(encoding="utf-8")
        cls.route_tree = ast.parse(cls.route_source)

        cls.workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")

    def _route_method_calls(self, method_name: str) -> list[ast.Call]:
        calls: list[ast.Call] = []
        for node in ast.walk(self.route_tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "router" and node.func.attr == method_name:
                    calls.append(node)
        return calls

    def test_01_phase7b_doc_exists(self) -> None:
        self.assertTrue(self.doc_exists)

    def test_02_doc_says_current_main_staging_preflight_refresh(self) -> None:
        self.assertIn("current-main staging preflight refresh", self.doc_lower)

    def test_03_doc_says_resolves_phase7a_not_ready_evidence_freshness_issue(self) -> None:
        self.assertIn("resolves the phase 7a not ready evidence freshness issue", self.doc_lower)

    def test_04_doc_says_does_not_resolve_human_approval_completion(self) -> None:
        self.assertIn("does not resolve human approval completion by itself", self.doc_lower)

    def test_05_doc_says_no_production_enablement(self) -> None:
        self.assertIn("no production enablement", self.doc_lower)

    def test_06_doc_says_no_apply_mode(self) -> None:
        self.assertIn("no apply mode", self.doc_lower)

    def test_07_doc_says_no_repair_execution(self) -> None:
        self.assertIn("no repair execution", self.doc_lower)

    def test_08_doc_says_no_data_mutation(self) -> None:
        self.assertIn("no data mutation", self.doc_lower)

    def test_09_doc_includes_latest_main_commit_sha(self) -> None:
        self.assertIn("e915aed0202b72541419fb86d944f3ca84d9135b", self.doc_text)

    def test_10_doc_includes_latest_guardrails_run_url(self) -> None:
        self.assertIn("https://github.com/tomboflight/tomboflight/actions/runs/25991319616", self.doc_text)

    def test_11_doc_says_both_guardrail_jobs_were_success(self) -> None:
        self.assertIn("continuity-kernel-guardrails job status: success", self.doc_lower)
        self.assertIn("continuity-kernel-runtime-route-test-env job status: success", self.doc_lower)

    def test_12_doc_says_focused_phase6i_zero_skips_confirmed(self) -> None:
        self.assertIn("focused phase 6i dependency-backed runtime test zero skips: confirmed", self.doc_lower)

    def test_13_doc_says_no_route_security_failures(self) -> None:
        self.assertIn("no route/security failures", self.doc_lower)

    def test_14_doc_includes_all_current_route_safety_confirmations(self) -> None:
        markers = [
            "get /admin/continuity-kernel/preview exists",
            "route is get-only",
            "route is admin-only",
            "route is feature-flagged",
            "feature flag default is off",
            "no customer-facing route exists",
            "prohibited actions are filtered/blocked",
            "no apply/schedule/execute/rollback actions exposed",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_lower)

    def test_15_doc_includes_all_current_hard_stop_confirmations(self) -> None:
        markers = [
            "no production flag enabled",
            "no production setting change",
            "no apply mode",
            "no repair execution",
            "no executable repair scripts",
            "no db write path for this feature",
            "no mint queueing",
            "no certificate/customer/entitlement/workspace-member mutation",
            "no frontend/admin button exposure",
            "no customer-facing exposure",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_lower)

    def test_16_doc_includes_all_remaining_human_approvals(self) -> None:
        markers = [
            "owner/ceo approval",
            "technical reviewer approval",
            "qa owner",
            "monitoring owner",
            "rollback owner",
            "production flag confirmed off by human reviewer",
            "staging environment confirmed",
            "manual test window confirmed",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_lower)

    def test_17_doc_says_execution_status_not_ready_until_human_approvals_recorded(self) -> None:
        self.assertIn("execution_status: not_ready_until_human_approvals_recorded", self.doc_text)

    def test_18_doc_says_manual_staging_may_not_proceed_until_approvals_recorded(self) -> None:
        self.assertIn("manual staging test may not proceed until approvals/sign-offs are recorded", self.doc_lower)

    def test_19_doc_says_phase7b_does_not_enable_staging(self) -> None:
        self.assertIn("phase 7b does not enable staging", self.doc_lower)

    def test_20_doc_says_phase7b_does_not_authorize_production(self) -> None:
        self.assertIn("phase 7b does not authorize production", self.doc_lower)

    def test_21_doc_includes_all_next_human_actions(self) -> None:
        markers = [
            "record owner/ceo approval",
            "record technical reviewer approval",
            "assign qa owner",
            "assign monitoring owner",
            "assign rollback owner",
            "confirm production flag remains off",
            "then proceed to approved staging-only phase 6w manual test checklist",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_lower)

    def test_22_doc_says_phase7b_does_not_enable_the_flag(self) -> None:
        self.assertIn("phase 7b does not enable the flag", self.doc_lower)

    def test_23_doc_says_phase7b_does_not_change_render_settings(self) -> None:
        self.assertIn("phase 7b does not change render settings", self.doc_lower)

    def test_24_doc_says_phase7b_does_not_change_production_settings(self) -> None:
        self.assertIn("phase 7b does not change production settings", self.doc_lower)

    def test_25_doc_says_phase7b_does_not_create_apply_mode_or_repair_scripts(self) -> None:
        self.assertIn("phase 7b does not create apply mode", self.doc_lower)
        self.assertIn("phase 7b does not create repair scripts", self.doc_lower)

    def test_26_doc_says_phase7b_does_not_touch_live_data(self) -> None:
        self.assertIn("phase 7b does not touch live data", self.doc_lower)

    def test_27_route_remains_get_only(self) -> None:
        get_calls = self._route_method_calls("get")
        has_preview_get = any(
            call.args and isinstance(call.args[0], ast.Constant) and call.args[0].value == "/preview"
            for call in get_calls
        )
        self.assertTrue(has_preview_get)

    def test_28_no_post_put_patch_delete_route_exists(self) -> None:
        self.assertEqual(len(self._route_method_calls("post")), 0)
        self.assertEqual(len(self._route_method_calls("put")), 0)
        self.assertEqual(len(self._route_method_calls("patch")), 0)
        self.assertEqual(len(self._route_method_calls("delete")), 0)

        for path in ROUTES_DIR.glob("**/*.py"):
            if path == ROUTE_PATH:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            self.assertNotIn("/admin/continuity-kernel/preview", text)

    def test_29_workflow_still_enforces_no_skips(self) -> None:
        self.assertIn('CONTINUITY_KERNEL_RUNTIME_TEST_ENFORCE_NO_SKIPS: "1"', self.workflow_text)
        self.assertIn(
            "python -m unittest backend.tests.contracts.test_continuity_kernel_phase6l_runtime_no_skip_enforcement -v",
            self.workflow_text,
        )

    def test_30_no_executable_repair_script_exists(self) -> None:
        repair_named_files = [path for path in SCRIPTS_DIR.glob("**/*") if path.is_file() and "repair" in path.name.lower()]
        self.assertEqual(repair_named_files, [])

        for path in SCRIPTS_DIR.glob("**/*.py"):
            self.assertFalse(
                path.stat().st_mode & EXECUTABLE_PERMISSION_BITS,
                msg=f"Unexpected executable script bit set: {path}",
            )


if __name__ == "__main__":
    unittest.main()
