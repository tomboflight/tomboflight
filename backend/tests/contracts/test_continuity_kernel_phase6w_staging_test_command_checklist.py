import ast
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6w_staging_test_command_checklist.md"
ROUTE_PATH = REPO_ROOT / "backend" / "app" / "routes" / "admin_continuity_preview.py"
ROUTES_DIR = REPO_ROOT / "backend" / "app" / "routes"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "continuity-kernel-guardrails.yml"
SCRIPTS_DIR = REPO_ROOT / "backend" / "scripts"
EXECUTABLE_PERMISSION_BITS = 0o111


class TestContinuityKernelPhase6WStagingTestCommandChecklist(unittest.TestCase):
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

    def test_01_phase6w_command_checklist_doc_exists(self) -> None:
        self.assertTrue(self.doc_exists)

    def test_02_doc_says_operator_facing_staging_manual_test_command_checklist(self) -> None:
        self.assertIn("operator-facing staging manual test command checklist", self.doc_lower)

    def test_03_doc_says_used_only_after_phase6s_go_decision_and_phase6v_preflight_evidence(self) -> None:
        self.assertIn("used only after phase 6s go decision and phase 6v preflight evidence", self.doc_lower)

    def test_04_doc_says_staging_only(self) -> None:
        self.assertIn("staging only", self.doc_lower)

    def test_05_doc_says_no_production_enablement(self) -> None:
        self.assertIn("no production enablement", self.doc_lower)

    def test_06_doc_says_no_apply_mode(self) -> None:
        self.assertIn("no apply mode", self.doc_lower)

    def test_07_doc_says_no_repair_execution(self) -> None:
        self.assertIn("no repair execution", self.doc_lower)

    def test_08_doc_says_no_data_mutation(self) -> None:
        self.assertIn("no data mutation", self.doc_lower)

    def test_09_doc_includes_all_preconditions(self) -> None:
        markers = [
            "Phase 6N readiness complete:",
            "Phase 6O runbook reviewed:",
            "Phase 6P approval/evidence complete:",
            "Phase 6Q execution record ready:",
            "Phase 6R packet index complete:",
            "Phase 6S go decision complete:",
            "Phase 6T readiness lock complete:",
            "Phase 6U manual test packet ready:",
            "Phase 6V preflight evidence refreshed:",
            "production flag confirmed off:",
            "owner/CEO approval recorded:",
            "technical reviewer approval recorded:",
            "rollback owner assigned:",
            "QA owner assigned:",
            "monitoring owner assigned:",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_text)

    def test_10_doc_includes_all_environment_restrictions(self) -> None:
        markers = [
            "staging only",
            "production flag must remain off",
            "no production setting change",
            "no customer-facing exposure",
            "no frontend/admin button exposure",
            "no POST/PUT/PATCH/DELETE route testing except to confirm unavailable",
            "no apply/schedule/execute/rollback action",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_text)

    def test_11_doc_includes_all_required_command_evidence_checklist_items(self) -> None:
        markers = [
            "record staging base URL",
            "record authenticated admin test account",
            "record non-admin test account",
            "record marketing_admin/CMO test account or equivalent role simulation",
            "capture flag-off GET /admin/continuity-kernel/preview response",
            "enable flag in staging only by approved manual process",
            "capture flag-on GET /admin/continuity-kernel/preview response",
            "verify response enabled true",
            "verify read-only envelope only",
            "verify no prohibited actions",
            "verify no full rollback_plan",
            "verify no override reason_detail",
            "verify no justification reason_detail",
            "verify no audit_context",
            "verify non-admin denied",
            "verify marketing_admin/CMO receives no repair execution actions",
            "verify POST unavailable",
            "verify PUT unavailable",
            "verify PATCH unavailable",
            "verify DELETE unavailable",
            "verify no customer-facing route exists",
            "verify backend logs show no DB writes",
            "verify no jobs queued",
            "verify no mint queueing",
            "verify no certificate/customer mutation",
            "disable flag after test",
            "capture flag-off response after rollback",
            "rerun architecture tests",
            "rerun contract tests",
            "rerun focused Phase 6I runtime route test",
            "rerun Phase 6L no-skip enforcement",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_text)

    def test_12_doc_includes_all_prohibited_actions(self) -> None:
        markers = [
            "approve_apply",
            "schedule_apply",
            "execute_apply",
            "rollback_apply",
            "mutate_entitlement",
            "mutate_workspace_member",
            "mutate_certificate",
            "queue_mint",
            "delete_customer_record",
            "bypass_validator",
            "bypass_audit",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_text)

    def test_13_doc_includes_all_stop_conditions(self) -> None:
        markers = [
            "production flag changes",
            "customer-facing route is exposed",
            "POST/PUT/PATCH/DELETE works",
            "prohibited action appears",
            "sensitive payload appears",
            "DB write observed",
            "job queued",
            "mint queueing observed",
            "certificate/customer mutation observed",
            "non-admin gains access",
            "rollback/flag-off response fails",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_text)

    def test_14_doc_includes_all_evidence_fields(self) -> None:
        markers = [
            "command_run",
            "expected_result",
            "actual_result",
            "screenshot_or_log_reference",
            "pass_fail",
            "notes",
            "reviewer_initials",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_text)

    def test_15_doc_says_production_flag_must_remain_off(self) -> None:
        self.assertIn("production flag must remain off", self.doc_lower)

    def test_16_doc_says_no_customer_facing_exposure(self) -> None:
        self.assertIn("no customer-facing exposure", self.doc_lower)

    def test_17_doc_says_no_frontend_admin_button_exposure(self) -> None:
        self.assertIn("no frontend/admin button exposure", self.doc_lower)

    def test_18_doc_says_phase6w_does_not_enable_the_flag(self) -> None:
        self.assertIn("phase 6w does not enable the flag", self.doc_lower)

    def test_19_doc_says_phase6w_does_not_change_render_settings(self) -> None:
        self.assertIn("phase 6w does not change render settings", self.doc_lower)

    def test_20_doc_says_phase6w_does_not_change_production_settings(self) -> None:
        self.assertIn("phase 6w does not change production settings", self.doc_lower)

    def test_21_doc_says_phase6w_does_not_create_apply_mode_or_repair_scripts(self) -> None:
        self.assertIn("phase 6w does not create apply mode or repair scripts", self.doc_lower)

    def test_22_doc_says_phase6w_does_not_touch_live_data(self) -> None:
        self.assertIn("phase 6w does not touch live data", self.doc_lower)

    def test_23_route_remains_get_only(self) -> None:
        get_calls = self._route_method_calls("get")
        has_preview_get = any(
            call.args and isinstance(call.args[0], ast.Constant) and call.args[0].value == "/preview"
            for call in get_calls
        )
        self.assertTrue(has_preview_get)

    def test_24_no_post_put_patch_delete_route_exists(self) -> None:
        self.assertEqual(len(self._route_method_calls("post")), 0)
        self.assertEqual(len(self._route_method_calls("put")), 0)
        self.assertEqual(len(self._route_method_calls("patch")), 0)
        self.assertEqual(len(self._route_method_calls("delete")), 0)

        for path in ROUTES_DIR.glob("**/*.py"):
            if path == ROUTE_PATH:
                continue
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("/admin/continuity-kernel/preview", text)

    def test_25_workflow_still_enforces_no_skips(self) -> None:
        self.assertIn('CONTINUITY_KERNEL_RUNTIME_TEST_ENFORCE_NO_SKIPS: "1"', self.workflow_text)
        self.assertIn(
            "python -m unittest backend.tests.contracts.test_continuity_kernel_phase6l_runtime_no_skip_enforcement -v",
            self.workflow_text,
        )

    def test_26_no_executable_repair_script_exists(self) -> None:
        repair_named_files = [path for path in SCRIPTS_DIR.glob("**/*") if path.is_file() and "repair" in path.name.lower()]
        self.assertFalse(repair_named_files, msg="Found unexpected repair-named files")

        for path in SCRIPTS_DIR.glob("**/*.py"):
            self.assertFalse(
                path.stat().st_mode & EXECUTABLE_PERMISSION_BITS,
                msg=f"Unexpected executable script bit set: {path}",
            )


if __name__ == "__main__":
    unittest.main()
