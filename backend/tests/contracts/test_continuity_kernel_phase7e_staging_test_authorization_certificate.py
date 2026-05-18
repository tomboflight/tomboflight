import ast
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase7e_staging_test_authorization_certificate.md"
PHASE7C_DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase7c_human_approval_signoff.md"
PHASE7D_DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase7d_approval_completion_checklist.md"
ROUTE_PATH = REPO_ROOT / "backend" / "app" / "routes" / "admin_continuity_preview.py"
ROUTES_DIR = REPO_ROOT / "backend" / "app" / "routes"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "continuity-kernel-guardrails.yml"
SCRIPTS_DIR = REPO_ROOT / "backend" / "scripts"
EXECUTABLE_PERMISSION_BITS = 0o111


class TestContinuityKernelPhase7EStagingTestAuthorizationCertificate(unittest.TestCase):
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

    def test_01_phase7e_authorization_certificate_doc_exists(self) -> None:
        self.assertTrue(self.doc_exists)

    def test_02_doc_says_manual_staging_test_authorization_certificate(self) -> None:
        self.assertIn("manual staging test authorization certificate", self.doc_lower)

    def test_03_doc_says_completed_only_after_phase7c_record_passes_phase7d_checklist(self) -> None:
        self.assertIn(
            "completed only after the phase 7c approval record passes the phase 7d completion checklist",
            self.doc_lower,
        )

    def test_04_doc_says_authorizes_manual_staging_only_flag_test_only(self) -> None:
        self.assertIn("authorizes manual staging-only flag test only", self.doc_lower)

    def test_05_doc_says_no_production_enablement(self) -> None:
        self.assertIn("no production enablement", self.doc_lower)

    def test_06_doc_says_no_apply_mode(self) -> None:
        self.assertIn("no apply mode", self.doc_lower)

    def test_07_doc_says_no_repair_execution(self) -> None:
        self.assertIn("no repair execution", self.doc_lower)

    def test_08_doc_says_no_data_mutation(self) -> None:
        self.assertIn("no data mutation", self.doc_lower)

    def test_09_doc_includes_all_authorization_certificate_fields(self) -> None:
        markers = [
            "authorization_certificate_id:",
            "related_phase7c_approval_record:",
            "related_phase7d_completion_checklist:",
            "authorized_staging_environment:",
            "authorized_test_window:",
            "authorized_operator:",
            "authorized_by_owner_ceo:",
            "authorized_by_technical_reviewer:",
            "qa_owner:",
            "monitoring_owner:",
            "rollback_owner:",
            "authorization_decision:",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_text)

    def test_10_doc_includes_all_required_proof_before_authorization(self) -> None:
        markers = [
            "phase 7c approval record complete",
            "phase 7d checklist result is complete_ready_for_manual_staging_test",
            "production flag confirmed off",
            "dependency-backed ci zero-skip proof attached",
            "phase 6w command checklist ready",
            "phase 6q execution record ready",
            "rollback plan approved",
            "monitoring plan approved",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_lower)

    def test_11_doc_includes_all_authorization_scope_items(self) -> None:
        markers = [
            "staging only",
            "get /admin/continuity-kernel/preview only",
            "continuity_kernel_readonly_admin_preview_enabled only",
            "time-boxed test window only",
            "read-only verification only",
            "no production environment",
            "no customer-facing route",
            "no frontend/admin button exposure",
            "no apply/schedule/execute/rollback actions",
            "no repair execution",
            "no db writes",
            "no mint queueing",
            "no certificate/customer mutation",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_lower)

    def test_12_doc_includes_all_authorization_decision_values(self) -> None:
        markers = [
            "authorized_for_manual_staging_test",
            "not_authorized_missing_approval",
            "not_authorized_missing_ci_evidence",
            "not_authorized_safety_risk",
            "revoked",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_text)

    def test_13_doc_includes_all_required_operator_acknowledgements(self) -> None:
        markers = [
            "operator acknowledges staging only",
            "operator acknowledges no production enablement",
            "operator acknowledges no apply mode",
            "operator acknowledges no repair execution",
            "operator acknowledges flag must be disabled after test",
            "operator acknowledges results must be recorded in phase 6q",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_lower)

    def test_14_doc_says_phase7c_approval_record_complete(self) -> None:
        self.assertIn("phase 7c approval record complete", self.doc_lower)

    def test_15_doc_says_phase7d_checklist_result_complete_ready(self) -> None:
        self.assertIn("phase 7d checklist result is complete_ready_for_manual_staging_test", self.doc_lower)

    def test_16_doc_says_production_flag_confirmed_off(self) -> None:
        self.assertIn("production flag confirmed off", self.doc_lower)

    def test_17_doc_says_dependency_backed_ci_zero_skip_proof_attached(self) -> None:
        self.assertIn("dependency-backed ci zero-skip proof attached", self.doc_lower)

    def test_18_doc_says_phase6w_command_checklist_ready(self) -> None:
        self.assertIn("phase 6w command checklist ready", self.doc_lower)

    def test_19_doc_says_phase6q_execution_record_ready(self) -> None:
        self.assertIn("phase 6q execution record ready", self.doc_lower)

    def test_20_doc_says_get_preview_only(self) -> None:
        self.assertIn("get /admin/continuity-kernel/preview only", self.doc_lower)

    def test_21_doc_says_preview_flag_only(self) -> None:
        self.assertIn("continuity_kernel_readonly_admin_preview_enabled only", self.doc_lower)

    def test_22_doc_says_flag_must_be_disabled_after_test(self) -> None:
        self.assertIn("flag must be disabled after test", self.doc_lower)

    def test_23_doc_says_results_must_be_recorded_in_phase6q(self) -> None:
        self.assertIn("results must be recorded in phase 6q", self.doc_lower)

    def test_24_doc_says_phase7e_does_not_enable_the_flag(self) -> None:
        self.assertIn("phase 7e does not enable the flag", self.doc_lower)

    def test_25_doc_says_phase7e_does_not_change_render_settings(self) -> None:
        self.assertIn("phase 7e does not change render settings", self.doc_lower)

    def test_26_doc_says_phase7e_does_not_change_production_settings(self) -> None:
        self.assertIn("phase 7e does not change production settings", self.doc_lower)

    def test_27_doc_says_phase7e_does_not_create_apply_mode_or_repair_scripts(self) -> None:
        self.assertIn("phase 7e does not create apply mode", self.doc_lower)
        self.assertIn("phase 7e does not create repair scripts", self.doc_lower)

    def test_28_doc_says_phase7e_does_not_touch_live_data(self) -> None:
        self.assertIn("phase 7e does not touch live data", self.doc_lower)

    def test_29_phase7c_doc_exists(self) -> None:
        self.assertTrue(PHASE7C_DOC_PATH.exists())

    def test_30_phase7d_doc_exists(self) -> None:
        self.assertTrue(PHASE7D_DOC_PATH.exists())

    def test_31_route_remains_get_only(self) -> None:
        get_calls = self._route_method_calls("get")
        has_preview_get = any(
            call.args and isinstance(call.args[0], ast.Constant) and call.args[0].value == "/preview"
            for call in get_calls
        )
        self.assertTrue(has_preview_get)

    def test_32_no_post_put_patch_delete_route_exists(self) -> None:
        self.assertEqual(len(self._route_method_calls("post")), 0)
        self.assertEqual(len(self._route_method_calls("put")), 0)
        self.assertEqual(len(self._route_method_calls("patch")), 0)
        self.assertEqual(len(self._route_method_calls("delete")), 0)

        for path in ROUTES_DIR.glob("**/*.py"):
            if path == ROUTE_PATH:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            self.assertNotIn("/admin/continuity-kernel/preview", text)

    def test_33_workflow_still_enforces_no_skips(self) -> None:
        self.assertIn('CONTINUITY_KERNEL_RUNTIME_TEST_ENFORCE_NO_SKIPS: "1"', self.workflow_text)
        self.assertIn(
            "python -m unittest backend.tests.contracts.test_continuity_kernel_phase6l_runtime_no_skip_enforcement -v",
            self.workflow_text,
        )

    def test_34_no_executable_repair_script_exists(self) -> None:
        repair_named_files = [path for path in SCRIPTS_DIR.glob("**/*") if path.is_file() and "repair" in path.name.lower()]
        self.assertEqual(repair_named_files, [], msg=f"Found unexpected repair files: {repair_named_files}")

        for path in SCRIPTS_DIR.glob("**/*.py"):
            self.assertFalse(
                path.stat().st_mode & EXECUTABLE_PERMISSION_BITS,
                msg=f"Unexpected executable script bit set: {path}",
            )


if __name__ == "__main__":
    unittest.main()
