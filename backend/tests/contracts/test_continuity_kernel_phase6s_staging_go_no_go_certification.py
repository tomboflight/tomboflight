import ast
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6s_staging_go_no_go_certification.md"
PHASE_6N_DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6n_staging_preview_readiness.md"
PHASE_6O_DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6o_staging_flag_runbook.md"
PHASE_6P_DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6p_staging_approval_evidence.md"
PHASE_6Q_DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6q_staging_execution_record.md"
PHASE_6R_DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6r_staging_approval_packet_index.md"
ROUTE_PATH = REPO_ROOT / "backend" / "app" / "routes" / "admin_continuity_preview.py"
ROUTES_DIR = REPO_ROOT / "backend" / "app" / "routes"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "continuity-kernel-guardrails.yml"
SCRIPTS_DIR = REPO_ROOT / "backend" / "scripts"
EXECUTABLE_PERMISSION_BITS = 0o111


class TestContinuityKernelPhase6SStagingGoNoGoCertification(unittest.TestCase):
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

    def test_01_phase6s_certification_doc_exists(self) -> None:
        self.assertTrue(self.doc_exists)

    def test_02_doc_says_final_staging_go_no_go_certification(self) -> None:
        self.assertIn("final staging go/no-go certification", self.doc_lower)

    def test_03_doc_says_decision_required_before_manually_enabling_staging_flag(self) -> None:
        self.assertIn("decision required before manually enabling the staging flag", self.doc_lower)

    def test_04_doc_says_no_production_enablement(self) -> None:
        self.assertIn("no production enablement", self.doc_lower)

    def test_05_doc_says_no_apply_mode(self) -> None:
        self.assertIn("no apply mode", self.doc_lower)

    def test_06_doc_says_no_repair_execution(self) -> None:
        self.assertIn("no repair execution", self.doc_lower)

    def test_07_doc_says_no_data_mutation(self) -> None:
        self.assertIn("no data mutation", self.doc_lower)

    def test_08_doc_includes_all_required_prerequisites(self) -> None:
        markers = [
            "phase 6n readiness criteria completed",
            "phase 6o runbook reviewed",
            "phase 6p approval/evidence package completed",
            "phase 6r packet index completed",
            "dependency-backed ci zero-skip proof attached",
            "production flag confirmed off",
            "owner/ceo approval recorded",
            "technical reviewer approval recorded",
            "rollback owner assigned",
            "qa owner assigned",
            "monitoring owner assigned",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_lower)

    def test_09_doc_includes_all_go_decision_requirements(self) -> None:
        markers = [
            "all prerequisites complete",
            "no pre-staging hard stops active",
            "staging environment identified",
            "time-box approved",
            "rollback plan approved",
            "monitoring plan approved",
            "manual qa checklist ready",
            "production setting untouched",
            "customer-facing exposure absent",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_lower)

    def test_10_doc_includes_all_no_go_decision_triggers(self) -> None:
        markers = [
            "missing owner/ceo approval",
            "missing technical reviewer approval",
            "production flag not confirmed off",
            "dependency-backed ci zero-skip proof missing",
            "any post/put/patch/delete route detected",
            "apply mode detected",
            "repair script detected",
            "db write path detected",
            "mint queueing detected",
            "certificate/customer mutation risk detected",
            "customer-facing exposure detected",
            "rollback owner missing",
            "monitoring owner missing",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_lower)

    def test_11_doc_includes_all_decision_values(self) -> None:
        markers = [
            "go_for_staging_flag_test",
            "no_go_missing_evidence",
            "no_go_safety_risk",
            "no_go_ci_failure",
            "no_go_owner_rejected",
            "no_go_technical_reviewer_rejected",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_text)

    def test_12_doc_includes_all_required_sign_off_fields(self) -> None:
        markers = [
            "decision",
            "decision_made_by",
            "owner_ceo_signoff",
            "technical_reviewer_signoff",
            "qa_owner",
            "monitoring_owner",
            "rollback_owner",
            "decision_time",
            "notes",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_text)

    def test_13_doc_says_production_flag_confirmed_off(self) -> None:
        self.assertIn("production flag confirmed off", self.doc_lower)

    def test_14_doc_says_dependency_backed_ci_zero_skip_proof_attached(self) -> None:
        self.assertIn("dependency-backed ci zero-skip proof attached", self.doc_lower)

    def test_15_doc_says_owner_ceo_approval_recorded(self) -> None:
        self.assertIn("owner/ceo approval recorded", self.doc_lower)

    def test_16_doc_says_technical_reviewer_approval_recorded(self) -> None:
        self.assertIn("technical reviewer approval recorded", self.doc_lower)

    def test_17_doc_says_rollback_owner_assigned(self) -> None:
        self.assertIn("rollback owner assigned", self.doc_lower)

    def test_18_doc_says_qa_owner_assigned(self) -> None:
        self.assertIn("qa owner assigned", self.doc_lower)

    def test_19_doc_says_monitoring_owner_assigned(self) -> None:
        self.assertIn("monitoring owner assigned", self.doc_lower)

    def test_20_doc_says_phase6s_does_not_enable_the_flag(self) -> None:
        self.assertIn("phase 6s does not enable the flag", self.doc_lower)

    def test_21_doc_says_phase6s_does_not_change_render_settings(self) -> None:
        self.assertIn("phase 6s does not change render settings", self.doc_lower)

    def test_22_doc_says_phase6s_does_not_change_production_settings(self) -> None:
        self.assertIn("phase 6s does not change production settings", self.doc_lower)

    def test_23_doc_says_phase6s_does_not_create_apply_mode_or_repair_scripts(self) -> None:
        self.assertIn("phase 6s does not create apply mode", self.doc_lower)
        self.assertIn("phase 6s does not create repair scripts", self.doc_lower)

    def test_24_doc_says_phase6s_does_not_touch_live_data(self) -> None:
        self.assertIn("phase 6s does not touch live data", self.doc_lower)

    def test_25_phase6n_doc_exists(self) -> None:
        self.assertTrue(PHASE_6N_DOC_PATH.exists())

    def test_26_phase6o_doc_exists(self) -> None:
        self.assertTrue(PHASE_6O_DOC_PATH.exists())

    def test_27_phase6p_doc_exists(self) -> None:
        self.assertTrue(PHASE_6P_DOC_PATH.exists())

    def test_28_phase6q_doc_exists(self) -> None:
        self.assertTrue(PHASE_6Q_DOC_PATH.exists())

    def test_29_phase6r_doc_exists(self) -> None:
        self.assertTrue(PHASE_6R_DOC_PATH.exists())

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
        self.assertEqual(repair_named_files, [])

        for path in SCRIPTS_DIR.glob("**/*.py"):
            self.assertFalse(
                path.stat().st_mode & EXECUTABLE_PERMISSION_BITS,
                msg=f"Unexpected executable script bit set: {path}",
            )


if __name__ == "__main__":
    unittest.main()
