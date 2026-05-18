import ast
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase7d_approval_completion_checklist.md"
PHASE7C_DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase7c_human_approval_signoff.md"
ROUTE_PATH = REPO_ROOT / "backend" / "app" / "routes" / "admin_continuity_preview.py"
ROUTES_DIR = REPO_ROOT / "backend" / "app" / "routes"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "continuity-kernel-guardrails.yml"
SCRIPTS_DIR = REPO_ROOT / "backend" / "scripts"
EXECUTABLE_PERMISSION_BITS = 0o111


class TestContinuityKernelPhase7DApprovalCompletionChecklist(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc_exists = DOC_PATH.exists()
        cls.doc_text = DOC_PATH.read_text(encoding="utf-8") if cls.doc_exists else ""
        cls.doc_lower = cls.doc_text.lower()

        cls.route_source = ROUTE_PATH.read_text(encoding="utf-8")
        cls.route_tree = ast.parse(cls.route_source)

        cls.workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        cls.workflow_lower = cls.workflow_text.lower()

    def _route_method_calls(self, method_name: str) -> list[ast.Call]:
        calls: list[ast.Call] = []
        for node in ast.walk(self.route_tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "router" and node.func.attr == method_name:
                    calls.append(node)
        return calls

    def test_01_phase7d_checklist_doc_exists(self) -> None:
        self.assertTrue(self.doc_exists)

    def test_02_doc_says_approval_completion_checklist(self) -> None:
        self.assertIn("approval completion checklist", self.doc_lower)

    def test_03_doc_says_verifies_phase7c_human_approval_signoff_record_completeness(self) -> None:
        self.assertIn("verifies phase 7c human approval/sign-off record completeness", self.doc_lower)

    def test_04_doc_says_required_before_manual_staging_only_flag_test(self) -> None:
        self.assertIn("required before manual staging-only flag test", self.doc_lower)

    def test_05_doc_says_no_production_enablement(self) -> None:
        self.assertIn("no production enablement", self.doc_lower)

    def test_06_doc_says_no_apply_mode(self) -> None:
        self.assertIn("no apply mode", self.doc_lower)

    def test_07_doc_says_no_repair_execution(self) -> None:
        self.assertIn("no repair execution", self.doc_lower)

    def test_08_doc_says_no_data_mutation(self) -> None:
        self.assertIn("no data mutation", self.doc_lower)

    def test_09_doc_includes_all_required_phase7c_record_checks(self) -> None:
        markers = [
            "approval_record_id is present",
            "related_phase7b_preflight_record is present",
            "related_phase6s_go_no_go_certification is present",
            "related_phase6x_execution_approval_summary is present",
            "staging_environment_name is present",
            "planned_test_window is present",
            "production_flag_confirmed_off is true/recorded",
            "dependency_backed_ci_zero_skip_proof_attached is true/recorded",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_lower)

    def test_10_doc_includes_all_required_approval_completion_checks(self) -> None:
        markers = [
            "owner_ceo_approval_status is approved",
            "owner_ceo_signature_or_acknowledgement is present",
            "technical_reviewer_approval_status is approved",
            "technical_reviewer_signature_or_acknowledgement is present",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_lower)

    def test_11_doc_includes_all_required_owner_assignment_checks(self) -> None:
        markers = [
            "qa_owner_name is present",
            "qa_owner_acknowledgement is present",
            "monitoring_owner_name is present",
            "monitoring_owner_acknowledgement is present",
            "rollback_owner_name is present",
            "rollback_owner_acknowledgement is present",
            "staging_operator_name is present",
            "staging_operator_acknowledgement is present",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_lower)

    def test_12_doc_includes_all_required_acknowledgement_checks(self) -> None:
        markers = [
            "staging only acknowledged",
            "production flag remains off acknowledged",
            "no production settings will be changed acknowledged",
            "no customer-facing route will be exposed acknowledged",
            "no frontend/admin button will be exposed acknowledged",
            "no apply/schedule/execute/rollback action will be performed acknowledged",
            "no repair execution will be performed acknowledged",
            "no database writes will be performed acknowledged",
            "no mint queueing will be performed acknowledged",
            "no certificate/customer mutation will be performed acknowledged",
            "flag will be disabled after test acknowledged",
            "results will be recorded in phase 6q acknowledged",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_lower)

    def test_13_doc_includes_all_completion_decision_values(self) -> None:
        markers = [
            "complete_ready_for_manual_staging_test",
            "incomplete_missing_owner_ceo_approval",
            "incomplete_missing_technical_reviewer_approval",
            "incomplete_missing_owner_assignment",
            "incomplete_missing_acknowledgement",
            "incomplete_missing_ci_evidence",
            "rejected",
            "revoked",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_text)

    def test_14_doc_says_production_flag_confirmed_off_is_true_recorded(self) -> None:
        self.assertIn("production_flag_confirmed_off is true/recorded", self.doc_lower)

    def test_15_doc_says_dependency_backed_ci_zero_skip_proof_attached_is_true_recorded(self) -> None:
        self.assertIn("dependency_backed_ci_zero_skip_proof_attached is true/recorded", self.doc_lower)

    def test_16_doc_says_owner_ceo_approval_status_is_approved(self) -> None:
        self.assertIn("owner_ceo_approval_status is approved", self.doc_lower)

    def test_17_doc_says_technical_reviewer_approval_status_is_approved(self) -> None:
        self.assertIn("technical_reviewer_approval_status is approved", self.doc_lower)

    def test_18_doc_says_flag_will_be_disabled_after_test_acknowledged(self) -> None:
        self.assertIn("flag will be disabled after test acknowledged", self.doc_lower)

    def test_19_doc_says_results_will_be_recorded_in_phase6q_acknowledged(self) -> None:
        self.assertIn("results will be recorded in phase 6q acknowledged", self.doc_lower)

    def test_20_doc_says_phase7d_does_not_enable_the_flag(self) -> None:
        self.assertIn("phase 7d does not enable the flag", self.doc_lower)

    def test_21_doc_says_phase7d_does_not_change_render_settings(self) -> None:
        self.assertIn("phase 7d does not change render settings", self.doc_lower)

    def test_22_doc_says_phase7d_does_not_change_production_settings(self) -> None:
        self.assertIn("phase 7d does not change production settings", self.doc_lower)

    def test_23_doc_says_phase7d_does_not_create_apply_mode_or_repair_scripts(self) -> None:
        self.assertIn("phase 7d does not create apply mode", self.doc_lower)
        self.assertIn("phase 7d does not create repair scripts", self.doc_lower)

    def test_24_doc_says_phase7d_does_not_touch_live_data(self) -> None:
        self.assertIn("phase 7d does not touch live data", self.doc_lower)

    def test_25_phase7c_doc_exists(self) -> None:
        self.assertTrue(PHASE7C_DOC_PATH.exists())

    def test_26_route_remains_get_only(self) -> None:
        get_calls = self._route_method_calls("get")
        has_preview_get = any(
            call.args and isinstance(call.args[0], ast.Constant) and call.args[0].value == "/preview"
            for call in get_calls
        )
        self.assertTrue(has_preview_get)

    def test_27_no_post_put_patch_delete_route_exists(self) -> None:
        self.assertEqual(len(self._route_method_calls("post")), 0)
        self.assertEqual(len(self._route_method_calls("put")), 0)
        self.assertEqual(len(self._route_method_calls("patch")), 0)
        self.assertEqual(len(self._route_method_calls("delete")), 0)

        for path in ROUTES_DIR.glob("**/*.py"):
            if path == ROUTE_PATH:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            self.assertNotIn("/admin/continuity-kernel/preview", text)

    def test_28_workflow_still_enforces_no_skips(self) -> None:
        self.assertIn('CONTINUITY_KERNEL_RUNTIME_TEST_ENFORCE_NO_SKIPS: "1"', self.workflow_text)
        self.assertIn(
            "python -m unittest backend.tests.contracts.test_continuity_kernel_phase6l_runtime_no_skip_enforcement -v",
            self.workflow_text,
        )

    def test_29_no_executable_repair_script_exists(self) -> None:
        repair_named_files = [path for path in SCRIPTS_DIR.glob("**/*") if path.is_file() and "repair" in path.name.lower()]
        self.assertEqual(repair_named_files, [], msg=f"Found unexpected repair files: {repair_named_files}")

        for path in SCRIPTS_DIR.glob("**/*.py"):
            self.assertFalse(
                path.stat().st_mode & EXECUTABLE_PERMISSION_BITS,
                msg=f"Unexpected executable script bit set: {path}",
            )


if __name__ == "__main__":
    unittest.main()
