import ast
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6o_staging_flag_runbook.md"
ROUTE_PATH = REPO_ROOT / "backend" / "app" / "routes" / "admin_continuity_preview.py"
ROUTES_DIR = REPO_ROOT / "backend" / "app" / "routes"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "continuity-kernel-guardrails.yml"
SCRIPTS_DIR = REPO_ROOT / "backend" / "scripts"


class TestContinuityKernelPhase6OStagingFlagRunbook(unittest.TestCase):
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

    def test_01_phase6o_runbook_doc_exists(self) -> None:
        self.assertTrue(self.doc_exists)

    def test_02_doc_includes_feature_flag_name(self) -> None:
        self.assertIn("CONTINUITY_KERNEL_READONLY_ADMIN_PREVIEW_ENABLED", self.doc_text)

    def test_03_doc_says_staging_only_feature_flag_enablement_runbook(self) -> None:
        self.assertIn("staging-only feature flag enablement runbook", self.doc_lower)

    def test_04_doc_says_no_production_enablement(self) -> None:
        self.assertIn("no production enablement", self.doc_lower)

    def test_05_doc_says_no_apply_mode(self) -> None:
        self.assertIn("no apply mode", self.doc_lower)

    def test_06_doc_says_no_repair_execution(self) -> None:
        self.assertIn("no repair execution", self.doc_lower)

    def test_07_doc_says_no_data_mutation(self) -> None:
        self.assertIn("no data mutation", self.doc_lower)

    def test_08_doc_requires_owner_ceo_approval(self) -> None:
        self.assertIn("owner/ceo approval", self.doc_lower)

    def test_09_doc_requires_technical_reviewer_approval(self) -> None:
        self.assertIn("technical reviewer approval", self.doc_lower)

    def test_10_doc_requires_confirmation_phase6n_criteria_are_met(self) -> None:
        self.assertIn("confirmation phase 6n criteria are met", self.doc_lower)

    def test_11_doc_requires_dependency_backed_ci_has_zero_runtime_skips(self) -> None:
        self.assertIn("confirmation dependency-backed ci has zero runtime skips", self.doc_lower)

    def test_12_doc_requires_production_flag_remains_off(self) -> None:
        self.assertIn("confirmation feature flag remains off in production", self.doc_lower)

    def test_13_doc_says_staging_only(self) -> None:
        self.assertIn("staging only", self.doc_lower)

    def test_14_doc_says_time_boxed_test_window(self) -> None:
        self.assertIn("time-boxed test window", self.doc_lower)

    def test_15_doc_says_flag_must_be_turned_off_after_testing(self) -> None:
        self.assertIn("flag must be turned off after testing", self.doc_lower)

    def test_16_doc_includes_all_manual_staging_qa_checklist_items(self) -> None:
        markers = [
            "verify route disabled before enabling flag",
            "enable flag in staging only",
            "verify get /admin/continuity-kernel/preview returns read-only envelope",
            "verify admin-only access",
            "verify non-admin is denied",
            "verify marketing_admin/cmo receives no repair execution actions",
            "verify no prohibited actions are returned",
            "verify no full rollback_plan is exposed",
            "verify no override reason_detail is exposed",
            "verify no justification reason_detail is exposed",
            "verify no audit_context is exposed",
            "verify no post/put/patch/delete routes work",
            "verify logs show no db writes",
            "verify no jobs are queued",
            "verify no mint queueing occurs",
            "verify no certificate/customer mutation occurs",
            "disable flag after test",
            "verify route returns disabled after flag is off",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_lower)

    def test_17_doc_includes_all_monitoring_checklist_items(self) -> None:
        markers = [
            "check backend logs",
            "check error rates",
            "check auth failures",
            "check route access attempts",
            "check no write operations occurred",
            "check no job queue activity occurred",
            "check no customer-facing traffic hit the route",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_lower)

    def test_18_doc_includes_all_rollback_steps(self) -> None:
        markers = [
            "disable feature flag",
            "redeploy/restart only if needed",
            "verify disabled response",
            "verify no data changed",
            "verify no jobs queued",
            "rerun architecture tests",
            "rerun contract tests",
            "rerun focused phase 6i runtime route tests",
            "document test result",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_lower)

    def test_19_doc_includes_all_exit_criteria(self) -> None:
        markers = [
            "successful qa checklist",
            "flag disabled after test",
            "no mutation observed",
            "no prohibited actions observed",
            "no sensitive payload exposure observed",
            "owner sign-off recorded",
            "staging result documented",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_lower)

    def test_20_doc_says_phase6o_does_not_enable_the_flag(self) -> None:
        self.assertIn("phase 6o does not enable the flag", self.doc_lower)

    def test_21_doc_says_phase6o_does_not_change_render_settings(self) -> None:
        self.assertIn("phase 6o does not change render settings", self.doc_lower)

    def test_22_doc_says_phase6o_does_not_change_production_settings(self) -> None:
        self.assertIn("phase 6o does not change production settings", self.doc_lower)

    def test_23_doc_says_phase6o_does_not_create_apply_mode_or_repair_scripts(self) -> None:
        self.assertIn("phase 6o does not create apply mode", self.doc_lower)
        self.assertIn("phase 6o does not create repair scripts", self.doc_lower)

    def test_24_doc_says_phase6o_does_not_touch_live_data(self) -> None:
        self.assertIn("phase 6o does not touch live data", self.doc_lower)

    def test_25_route_remains_get_only(self) -> None:
        get_calls = self._route_method_calls("get")
        has_preview_get = any(
            call.args and isinstance(call.args[0], ast.Constant) and call.args[0].value == "/preview"
            for call in get_calls
        )
        self.assertTrue(has_preview_get)

    def test_26_no_post_put_patch_delete_route_exists(self) -> None:
        self.assertEqual(len(self._route_method_calls("post")), 0)
        self.assertEqual(len(self._route_method_calls("put")), 0)
        self.assertEqual(len(self._route_method_calls("patch")), 0)
        self.assertEqual(len(self._route_method_calls("delete")), 0)

        for path in ROUTES_DIR.glob("**/*.py"):
            if path == ROUTE_PATH:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            self.assertNotIn("/admin/continuity-kernel/preview", text)

    def test_27_workflow_still_enforces_no_skips(self) -> None:
        self.assertIn('CONTINUITY_KERNEL_RUNTIME_TEST_ENFORCE_NO_SKIPS: "1"', self.workflow_text)
        self.assertIn(
            "python -m unittest backend.tests.contracts.test_continuity_kernel_phase6l_runtime_no_skip_enforcement -v",
            self.workflow_text,
        )

    def test_28_no_executable_repair_script_exists(self) -> None:
        repair_named_files = [path for path in SCRIPTS_DIR.glob("**/*") if path.is_file() and "repair" in path.name.lower()]
        self.assertEqual(repair_named_files, [])

        for path in SCRIPTS_DIR.glob("**/*.py"):
            self.assertFalse(path.stat().st_mode & 0o111, msg=f"Unexpected executable script bit set: {path}")


if __name__ == "__main__":
    unittest.main()
