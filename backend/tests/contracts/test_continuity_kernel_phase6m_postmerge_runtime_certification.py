import ast
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6m_postmerge_runtime_certification.md"
ROUTE_PATH = REPO_ROOT / "backend" / "app" / "routes" / "admin_continuity_preview.py"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "continuity-kernel-guardrails.yml"

PHASE6I_COMMAND = "python -m unittest backend.tests.contracts.test_continuity_kernel_phase6i_runtime_route_verification -v"
PHASE6L_COMMAND = "python -m unittest backend.tests.contracts.test_continuity_kernel_phase6l_runtime_no_skip_enforcement -v"


class TestContinuityKernelPhase6MPostmergeRuntimeCertification(unittest.TestCase):
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

    def test_01_phase6m_doc_exists(self) -> None:
        self.assertTrue(self.doc_exists)

    def test_02_doc_says_get_preview_route_was_tested(self) -> None:
        self.assertIn("get /admin/continuity-kernel/preview was tested", self.doc_lower)

    def test_03_doc_says_dependency_backed_runtime_route_job_ran(self) -> None:
        self.assertIn("dependency-backed runtime route job ran", self.doc_lower)

    def test_04_doc_says_backend_requirements_installed(self) -> None:
        self.assertIn("backend dependencies installed from backend/requirements.txt", self.doc_lower)

    def test_05_doc_says_httpx_was_available(self) -> None:
        self.assertIn("httpx was available", self.doc_lower)

    def test_06_doc_says_focused_phase6i_tests_ran(self) -> None:
        self.assertIn("focused phase 6i runtime route tests ran", self.doc_lower)

    def test_07_doc_says_phase6l_no_skip_enforcement_ran(self) -> None:
        self.assertIn("phase 6l no-skip enforcement ran", self.doc_lower)

    def test_08_doc_says_runtime_tests_had_zero_skips_in_dependency_backed_ci(self) -> None:
        self.assertIn("runtime tests had zero skips in dependency-backed ci", self.doc_lower)

    def test_09_doc_says_route_remains_get_only(self) -> None:
        self.assertIn("route remains get-only", self.doc_lower)

    def test_10_doc_says_route_remains_admin_only(self) -> None:
        self.assertIn("route remains admin-only", self.doc_lower)

    def test_11_doc_says_route_remains_feature_flagged(self) -> None:
        self.assertIn("route remains feature-flagged", self.doc_lower)

    def test_12_doc_says_feature_flag_off_by_default(self) -> None:
        self.assertIn("feature flag remains off by default", self.doc_lower)

    def test_13_doc_says_missing_off_invalid_returns_disabled(self) -> None:
        self.assertIn("missing/off/invalid flag returns disabled", self.doc_lower)

    def test_14_doc_says_true_like_returns_enabled_read_only_envelope(self) -> None:
        self.assertIn("explicit true-like flag returns enabled read-only envelope", self.doc_lower)

    def test_15_doc_says_no_prohibited_actions_returned(self) -> None:
        self.assertIn("no prohibited actions returned", self.doc_lower)

    def test_16_doc_says_no_post_put_patch_delete_route_exists(self) -> None:
        self.assertIn("no post/put/patch/delete route exists", self.doc_lower)

    def test_17_doc_says_no_apply_mode_exists(self) -> None:
        self.assertIn("no apply mode exists", self.doc_lower)

    def test_18_doc_says_no_repair_scripts_exist(self) -> None:
        self.assertIn("no repair scripts exist", self.doc_lower)

    def test_19_doc_says_no_db_writes_exist(self) -> None:
        self.assertIn("no db writes exist", self.doc_lower)

    def test_20_doc_says_no_mint_queueing_exists(self) -> None:
        self.assertIn("no mint queueing exists", self.doc_lower)

    def test_21_doc_says_no_certificate_customer_mutation_exists(self) -> None:
        self.assertIn("no certificate/customer mutation exists", self.doc_lower)

    def test_22_doc_says_no_frontend_customer_facing_exposure_exists(self) -> None:
        self.assertIn("no frontend/customer-facing exposure exists", self.doc_lower)

    def test_23_doc_says_phase6m_does_not_approve_apply_mode(self) -> None:
        self.assertIn("phase 6m does not approve apply mode", self.doc_lower)

    def test_24_doc_says_phase6m_does_not_approve_repair_execution(self) -> None:
        self.assertIn("phase 6m does not approve repair execution", self.doc_lower)

    def test_25_doc_says_phase6m_does_not_approve_frontend_admin_ui_changes(self) -> None:
        self.assertIn("phase 6m does not approve frontend/admin ui changes", self.doc_lower)

    def test_26_doc_says_phase6n_next_allowed_step_only(self) -> None:
        self.assertIn("phase 6n may perform staging/admin preview readiness review only", self.doc_lower)

    def test_27_route_file_still_has_get_preview_path(self) -> None:
        get_calls = self._route_method_calls("get")
        has_preview_get = any(
            call.args and isinstance(call.args[0], ast.Constant) and call.args[0].value == "/preview"
            for call in get_calls
        )
        self.assertTrue(has_preview_get)

    def test_28_route_file_has_no_post_put_patch_delete_decorators(self) -> None:
        self.assertEqual(len(self._route_method_calls("post")), 0)
        self.assertEqual(len(self._route_method_calls("put")), 0)
        self.assertEqual(len(self._route_method_calls("patch")), 0)
        self.assertEqual(len(self._route_method_calls("delete")), 0)

    def test_29_route_uses_admin_control_view_permission(self) -> None:
        self.assertIn('require_permission("admin.control.view")', self.route_source)

    def test_30_workflow_sets_runtime_no_skip_env_var(self) -> None:
        self.assertIn('CONTINUITY_KERNEL_RUNTIME_TEST_ENFORCE_NO_SKIPS: "1"', self.workflow_text)

    def test_31_workflow_runs_phase6i_focused_runtime_route_verification(self) -> None:
        self.assertIn(PHASE6I_COMMAND, self.workflow_text)

    def test_32_workflow_runs_phase6l_no_skip_enforcement(self) -> None:
        self.assertIn(PHASE6L_COMMAND, self.workflow_text)


if __name__ == "__main__":
    unittest.main()
