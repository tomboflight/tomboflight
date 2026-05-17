import ast
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6x_staging_execution_approval_summary.md"
ROUTE_PATH = REPO_ROOT / "backend" / "app" / "routes" / "admin_continuity_preview.py"
ROUTES_DIR = REPO_ROOT / "backend" / "app" / "routes"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "continuity-kernel-guardrails.yml"
SCRIPTS_DIR = REPO_ROOT / "backend" / "scripts"
EXECUTABLE_PERMISSION_BITS = 0o111


class TestContinuityKernelPhase6XStagingExecutionApprovalSummary(unittest.TestCase):
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

    def test_01_phase6x_approval_summary_doc_exists(self) -> None:
        self.assertTrue(self.doc_exists)

    def test_02_doc_says_final_staging_execution_approval_summary(self) -> None:
        self.assertIn("final staging execution approval summary", self.doc_lower)

    def test_03_doc_says_used_immediately_before_manual_staging_only_flag_test(self) -> None:
        self.assertIn("used immediately before manual staging-only flag test", self.doc_lower)

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

    def test_09_doc_includes_all_required_approval_summary_fields(self) -> None:
        markers = [
            "approval_summary_id:",
            "related_phase6p_approval_record_id:",
            "related_phase6s_go_no_go_decision:",
            "related_phase6v_preflight_record:",
            "related_phase6w_command_checklist:",
            "staging_environment_name:",
            "planned_test_window:",
            "owner_ceo_approval:",
            "technical_reviewer_approval:",
            "qa_owner:",
            "monitoring_owner:",
            "rollback_owner:",
            "final_decision:",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_text)

    def test_10_doc_includes_all_required_final_verification_checklist_items(self) -> None:
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
            "Phase 6W command checklist ready:",
            "dependency-backed CI zero-skip proof attached:",
            "production flag confirmed off:",
            "no production setting change planned:",
            "no frontend/customer-facing exposure planned:",
            "no apply/repair execution planned:",
            "rollback plan approved:",
            "monitoring plan approved:",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_text)

    def test_11_doc_includes_all_required_hard_stop_confirmation_items(self) -> None:
        markers = [
            "no missing owner/CEO approval",
            "no missing technical reviewer approval",
            "no missing rollback owner",
            "no missing QA owner",
            "no missing monitoring owner",
            "no missing zero-skip CI proof",
            "no production flag uncertainty",
            "no production setting change",
            "no customer-facing exposure",
            "no apply mode",
            "no repair execution",
            "no DB write path",
            "no mint queueing",
            "no certificate/customer mutation risk",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_text)

    def test_12_doc_includes_all_allowed_final_decisions(self) -> None:
        markers = [
            "approved_for_manual_staging_test",
            "blocked_missing_approval",
            "blocked_missing_ci_evidence",
            "blocked_safety_risk",
            "rejected",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_text)

    def test_13_doc_includes_all_operator_acknowledgement_fields(self) -> None:
        markers = [
            "operator_name:",
            "operator_acknowledges_staging_only:",
            "operator_acknowledges_no_production_enablement:",
            "operator_acknowledges_flag_must_be_disabled_after_test:",
            "operator_acknowledges_no_apply_or_repair_execution:",
            "operator_acknowledges_results_must_be_recorded_in_phase6q:",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_text)

    def test_14_doc_says_dependency_backed_ci_zero_skip_proof_attached(self) -> None:
        self.assertIn("dependency-backed ci zero-skip proof attached", self.doc_lower)

    def test_15_doc_says_production_flag_confirmed_off(self) -> None:
        self.assertIn("production flag confirmed off", self.doc_lower)

    def test_16_doc_says_no_production_setting_change_planned(self) -> None:
        self.assertIn("no production setting change planned", self.doc_lower)

    def test_17_doc_says_no_frontend_customer_facing_exposure_planned(self) -> None:
        self.assertIn("no frontend/customer-facing exposure planned", self.doc_lower)

    def test_18_doc_says_rollback_plan_approved(self) -> None:
        self.assertIn("rollback plan approved", self.doc_lower)

    def test_19_doc_says_monitoring_plan_approved(self) -> None:
        self.assertIn("monitoring plan approved", self.doc_lower)

    def test_20_doc_says_operator_acknowledges_staging_only(self) -> None:
        self.assertIn("operator acknowledges staging only", self.doc_lower)

    def test_21_doc_says_operator_acknowledges_no_production_enablement(self) -> None:
        self.assertIn("operator acknowledges no production enablement", self.doc_lower)

    def test_22_doc_says_operator_acknowledges_flag_must_be_disabled_after_test(self) -> None:
        self.assertIn("operator acknowledges flag must be disabled after test", self.doc_lower)

    def test_23_doc_says_operator_acknowledges_no_apply_or_repair_execution(self) -> None:
        self.assertIn("operator acknowledges no apply or repair execution", self.doc_lower)

    def test_24_doc_says_results_must_be_recorded_in_phase6q(self) -> None:
        self.assertIn("results must be recorded in phase 6q", self.doc_lower)

    def test_25_doc_says_phase6x_does_not_enable_the_flag(self) -> None:
        self.assertIn("phase 6x does not enable the flag", self.doc_lower)

    def test_26_doc_says_phase6x_does_not_change_render_settings(self) -> None:
        self.assertIn("phase 6x does not change render settings", self.doc_lower)

    def test_27_doc_says_phase6x_does_not_change_production_settings(self) -> None:
        self.assertIn("phase 6x does not change production settings", self.doc_lower)

    def test_28_doc_says_phase6x_does_not_create_apply_mode_or_repair_scripts(self) -> None:
        self.assertIn("phase 6x does not create apply mode or repair scripts", self.doc_lower)

    def test_29_doc_says_phase6x_does_not_touch_live_data(self) -> None:
        self.assertIn("phase 6x does not touch live data", self.doc_lower)

    def test_30_route_remains_get_only(self) -> None:
        get_calls = self._route_method_calls("get")
        has_preview_get = any(
            call.args and isinstance(call.args[0], ast.Constant) and call.args[0].value == "/preview"
            for call in get_calls
        )
        self.assertTrue(has_preview_get)

    def test_31_no_post_put_patch_delete_route_exists(self) -> None:
        self.assertEqual(len(self._route_method_calls("post")), 0)
        self.assertEqual(len(self._route_method_calls("put")), 0)
        self.assertEqual(len(self._route_method_calls("patch")), 0)
        self.assertEqual(len(self._route_method_calls("delete")), 0)

        for path in ROUTES_DIR.glob("**/*.py"):
            if path == ROUTE_PATH:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            self.assertNotIn("/admin/continuity-kernel/preview", text)

    def test_32_workflow_still_enforces_no_skips(self) -> None:
        self.assertIn('CONTINUITY_KERNEL_RUNTIME_TEST_ENFORCE_NO_SKIPS: "1"', self.workflow_text)
        self.assertIn(
            "python -m unittest backend.tests.contracts.test_continuity_kernel_phase6l_runtime_no_skip_enforcement -v",
            self.workflow_text,
        )

    def test_33_no_executable_repair_script_exists(self) -> None:
        repair_named_files = [path for path in SCRIPTS_DIR.glob("**/*") if path.is_file() and "repair" in path.name.lower()]
        self.assertFalse(repair_named_files, msg="Found unexpected repair-named files")

        for path in SCRIPTS_DIR.glob("**/*.py"):
            self.assertFalse(
                path.stat().st_mode & EXECUTABLE_PERMISSION_BITS,
                msg=f"Unexpected executable script bit set: {path}",
            )


if __name__ == "__main__":
    unittest.main()
