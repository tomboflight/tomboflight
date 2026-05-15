import ast
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6q_staging_execution_record.md"
ROUTE_PATH = REPO_ROOT / "backend" / "app" / "routes" / "admin_continuity_preview.py"
ROUTES_DIR = REPO_ROOT / "backend" / "app" / "routes"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "continuity-kernel-guardrails.yml"
SCRIPTS_DIR = REPO_ROOT / "backend" / "scripts"
EXECUTABLE_PERMISSION_BITS = 0o111


class TestContinuityKernelPhase6QStagingExecutionRecord(unittest.TestCase):
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

    def test_01_phase6q_execution_record_doc_exists(self) -> None:
        self.assertTrue(self.doc_exists)

    def test_02_doc_says_staging_only_execution_result_record(self) -> None:
        self.assertIn("staging-only execution result record", self.doc_lower)

    def test_03_doc_says_used_after_phase6p_approval_and_phase6o_runbook_execution(self) -> None:
        self.assertIn("used after phase 6p approval and phase 6o runbook execution", self.doc_lower)

    def test_04_doc_says_no_production_enablement(self) -> None:
        self.assertIn("no production enablement", self.doc_lower)

    def test_05_doc_says_no_apply_mode(self) -> None:
        self.assertIn("no apply mode", self.doc_lower)

    def test_06_doc_says_no_repair_execution(self) -> None:
        self.assertIn("no repair execution", self.doc_lower)

    def test_07_doc_says_no_data_mutation(self) -> None:
        self.assertIn("no data mutation", self.doc_lower)

    def test_08_doc_includes_all_required_execution_metadata_fields(self) -> None:
        markers = [
            "execution_record_id",
            "approval_record_id",
            "staging_environment_name",
            "executed_by",
            "technical_reviewer",
            "owner_ceo_approval_reference",
            "start_time",
            "end_time",
            "feature_flag_name",
            "flag_enabled_time",
            "flag_disabled_time",
            "production_flag_confirmed_off",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_text)

    def test_09_doc_includes_all_required_pre_test_confirmations(self) -> None:
        markers = [
            "phase_6p_approval_completed",
            "dependency_backed_ci_zero_skip_confirmed",
            "production_flag_confirmed_off",
            "staging_flag_initially_off",
            "rollback_owner_identified",
            "monitoring_owner_identified",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_text)

    def test_10_doc_includes_all_required_qa_result_fields(self) -> None:
        markers = [
            "flag_off_response_result",
            "flag_on_response_result",
            "admin_only_access_result",
            "non_admin_denial_result",
            "marketing_admin_cmo_no_execution_actions_result",
            "no_prohibited_actions_result",
            "no_full_rollback_plan_result",
            "no_override_reason_detail_result",
            "no_justification_reason_detail_result",
            "no_audit_context_result",
            "no_post_put_patch_delete_result",
            "no_db_write_log_result",
            "no_job_queue_activity_result",
            "no_mint_queueing_result",
            "no_certificate_customer_mutation_result",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_text)

    def test_11_doc_includes_all_required_rollback_result_fields(self) -> None:
        markers = [
            "flag_disabled_after_test",
            "disabled_response_after_test",
            "no_data_mutated_confirmed",
            "no_jobs_queued_confirmed",
            "no_audit_apply_state_created",
            "architecture_tests_after_test",
            "contract_tests_after_test",
            "focused_phase6i_runtime_test_after_test",
            "phase6l_no_skip_after_test",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_text)

    def test_12_doc_includes_all_result_decision_values(self) -> None:
        markers = [
            "not_started",
            "passed",
            "passed_with_notes",
            "failed",
            "rolled_back",
            "blocked",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_text)

    def test_13_doc_includes_all_required_final_sign_off_fields(self) -> None:
        markers = [
            "qa_owner_signoff",
            "monitoring_owner_signoff",
            "technical_reviewer_signoff",
            "owner_ceo_signoff",
            "final_decision",
            "notes",
            "follow_up_required",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_text)

    def test_14_doc_says_production_flag_confirmed_off(self) -> None:
        self.assertIn("production flag confirmed off", self.doc_lower)

    def test_15_doc_says_flag_disabled_after_test(self) -> None:
        self.assertIn("flag disabled after test", self.doc_lower)

    def test_16_doc_says_no_data_mutated_confirmed(self) -> None:
        self.assertIn("no data mutated confirmed", self.doc_lower)

    def test_17_doc_says_phase6q_does_not_enable_the_flag(self) -> None:
        self.assertIn("phase 6q does not enable the flag", self.doc_lower)

    def test_18_doc_says_phase6q_does_not_change_render_settings(self) -> None:
        self.assertIn("phase 6q does not change render settings", self.doc_lower)

    def test_19_doc_says_phase6q_does_not_change_production_settings(self) -> None:
        self.assertIn("phase 6q does not change production settings", self.doc_lower)

    def test_20_doc_says_phase6q_does_not_create_apply_mode_or_repair_scripts(self) -> None:
        self.assertIn("phase 6q does not create apply mode", self.doc_lower)
        self.assertIn("phase 6q does not create repair scripts", self.doc_lower)

    def test_21_doc_says_phase6q_does_not_touch_live_data(self) -> None:
        self.assertIn("phase 6q does not touch live data", self.doc_lower)

    def test_22_route_remains_get_only(self) -> None:
        get_calls = self._route_method_calls("get")
        has_preview_get = any(
            call.args and isinstance(call.args[0], ast.Constant) and call.args[0].value == "/preview"
            for call in get_calls
        )
        self.assertTrue(has_preview_get)

    def test_23_no_post_put_patch_delete_route_exists(self) -> None:
        self.assertEqual(len(self._route_method_calls("post")), 0)
        self.assertEqual(len(self._route_method_calls("put")), 0)
        self.assertEqual(len(self._route_method_calls("patch")), 0)
        self.assertEqual(len(self._route_method_calls("delete")), 0)

        for path in ROUTES_DIR.glob("**/*.py"):
            if path == ROUTE_PATH:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            self.assertNotIn("/admin/continuity-kernel/preview", text)

    def test_24_workflow_still_enforces_no_skips(self) -> None:
        self.assertIn('CONTINUITY_KERNEL_RUNTIME_TEST_ENFORCE_NO_SKIPS: "1"', self.workflow_text)
        self.assertIn(
            "python -m unittest backend.tests.contracts.test_continuity_kernel_phase6l_runtime_no_skip_enforcement -v",
            self.workflow_text,
        )

    def test_25_no_executable_repair_script_exists(self) -> None:
        repair_named_files = [path for path in SCRIPTS_DIR.glob("**/*") if path.is_file() and "repair" in path.name.lower()]
        self.assertEqual(repair_named_files, [])

        for path in SCRIPTS_DIR.glob("**/*.py"):
            self.assertFalse(
                path.stat().st_mode & EXECUTABLE_PERMISSION_BITS,
                msg=f"Unexpected executable script bit set: {path}",
            )


if __name__ == "__main__":
    unittest.main()
