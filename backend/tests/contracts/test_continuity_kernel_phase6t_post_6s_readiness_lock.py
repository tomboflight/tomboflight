import ast
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6t_post_6s_readiness_lock.md"
PHASE_6N_DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6n_staging_preview_readiness.md"
PHASE_6O_DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6o_staging_flag_runbook.md"
PHASE_6P_DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6p_staging_approval_evidence.md"
PHASE_6Q_DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6q_staging_execution_record.md"
PHASE_6R_DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6r_staging_approval_packet_index.md"
PHASE_6S_DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6s_staging_go_no_go_certification.md"
ROUTE_PATH = REPO_ROOT / "backend" / "app" / "routes" / "admin_continuity_preview.py"
ROUTES_DIR = REPO_ROOT / "backend" / "app" / "routes"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "continuity-kernel-guardrails.yml"
SCRIPTS_DIR = REPO_ROOT / "backend" / "scripts"
EXECUTABLE_PERMISSION_BITS = 0o111


class TestContinuityKernelPhase6TPost6SReadinessLock(unittest.TestCase):
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

    def test_01_phase6t_readiness_lock_doc_exists(self) -> None:
        self.assertTrue(self.doc_exists)

    def test_02_doc_says_post_6s_main_ci_certification(self) -> None:
        self.assertIn("post-6s main ci certification", self.doc_lower)

    def test_03_doc_says_staging_approval_readiness_lock(self) -> None:
        self.assertIn("staging approval readiness lock", self.doc_lower)

    def test_04_doc_says_no_flag_enablement(self) -> None:
        self.assertIn("no flag enablement", self.doc_lower)

    def test_05_doc_says_no_production_enablement(self) -> None:
        self.assertIn("no production enablement", self.doc_lower)

    def test_06_doc_says_no_apply_mode(self) -> None:
        self.assertIn("no apply mode", self.doc_lower)

    def test_07_doc_says_no_repair_execution(self) -> None:
        self.assertIn("no repair execution", self.doc_lower)

    def test_08_doc_says_no_data_mutation(self) -> None:
        self.assertIn("no data mutation", self.doc_lower)

    def test_09_doc_includes_all_required_post_6s_ci_evidence_fields(self) -> None:
        markers = [
            "latest main workflow run url",
            "commit sha tested",
            "continuity-kernel-guardrails job status",
            "continuity-kernel-runtime-route-test-env job status",
            "focused phase 6i runtime test output",
            "phase 6l no-skip enforcement output",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_lower)

    def test_10_doc_says_zero_runtime_skips_confirmed(self) -> None:
        self.assertIn("zero runtime skips confirmed", self.doc_lower)

    def test_11_doc_says_no_route_security_failures(self) -> None:
        self.assertIn("no route/security failures", self.doc_lower)

    def test_12_doc_includes_all_required_governance_packet_readiness_docs(self) -> None:
        markers = [
            "phase 6n doc exists",
            "phase 6o doc exists",
            "phase 6p doc exists",
            "phase 6q doc exists",
            "phase 6r doc exists",
            "phase 6s doc exists",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_lower)

    def test_13_phase6n_doc_exists(self) -> None:
        self.assertTrue(PHASE_6N_DOC_PATH.exists())

    def test_14_phase6o_doc_exists(self) -> None:
        self.assertTrue(PHASE_6O_DOC_PATH.exists())

    def test_15_phase6p_doc_exists(self) -> None:
        self.assertTrue(PHASE_6P_DOC_PATH.exists())

    def test_16_phase6q_doc_exists(self) -> None:
        self.assertTrue(PHASE_6Q_DOC_PATH.exists())

    def test_17_phase6r_doc_exists(self) -> None:
        self.assertTrue(PHASE_6R_DOC_PATH.exists())

    def test_18_phase6s_doc_exists(self) -> None:
        self.assertTrue(PHASE_6S_DOC_PATH.exists())

    def test_19_doc_says_staging_may_not_proceed_without_phase6s_go_decision(self) -> None:
        self.assertIn("staging may not proceed unless phase 6s go decision is completed", self.doc_lower)

    def test_20_doc_says_staging_may_not_proceed_without_owner_ceo_approval(self) -> None:
        self.assertIn("staging may not proceed without owner/ceo approval", self.doc_lower)

    def test_21_doc_says_staging_may_not_proceed_without_technical_reviewer_approval(self) -> None:
        self.assertIn("staging may not proceed without technical reviewer approval", self.doc_lower)

    def test_22_doc_says_production_flag_must_remain_off(self) -> None:
        self.assertIn("production flag must remain off", self.doc_lower)

    def test_23_doc_says_feature_flag_must_not_be_enabled_by_phase6t(self) -> None:
        self.assertIn("feature flag must not be enabled by phase 6t", self.doc_lower)

    def test_24_doc_says_phase6t_does_not_authorize_production_enablement(self) -> None:
        self.assertIn("phase 6t does not authorize production enablement", self.doc_lower)

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
            self.assertFalse(
                path.stat().st_mode & EXECUTABLE_PERMISSION_BITS,
                msg=f"Unexpected executable script bit set: {path}",
            )


if __name__ == "__main__":
    unittest.main()
