import ast
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6y_final_staging_packet_closeout.md"
ROUTE_PATH = REPO_ROOT / "backend" / "app" / "routes" / "admin_continuity_preview.py"
ROUTES_DIR = REPO_ROOT / "backend" / "app" / "routes"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "continuity-kernel-guardrails.yml"
SCRIPTS_DIR = REPO_ROOT / "backend" / "scripts"
EXECUTABLE_PERMISSION_BITS = 0o111

REQUIRED_ARTIFACT_INDEX = [
    "Phase 6N staging preview readiness review",
    "Phase 6O staging flag enablement runbook",
    "Phase 6P staging approval evidence package",
    "Phase 6Q staging execution result record",
    "Phase 6R staging approval packet index",
    "Phase 6S staging go/no-go certification",
    "Phase 6T post-6S readiness lock",
    "Phase 6U staging manual test packet",
    "Phase 6V staging preflight evidence refresh",
    "Phase 6W staging manual test command checklist",
    "Phase 6X staging execution approval summary",
]

REQUIRED_ARTIFACT_PATHS = [
    "backend/docs/governance/continuity_kernel_phase6n_staging_preview_readiness.md",
    "backend/docs/governance/continuity_kernel_phase6o_staging_flag_runbook.md",
    "backend/docs/governance/continuity_kernel_phase6p_staging_approval_evidence.md",
    "backend/docs/governance/continuity_kernel_phase6q_staging_execution_record.md",
    "backend/docs/governance/continuity_kernel_phase6r_staging_approval_packet_index.md",
    "backend/docs/governance/continuity_kernel_phase6s_staging_go_no_go_certification.md",
    "backend/docs/governance/continuity_kernel_phase6t_post_6s_readiness_lock.md",
    "backend/docs/governance/continuity_kernel_phase6u_staging_manual_test_packet.md",
    "backend/docs/governance/continuity_kernel_phase6v_staging_preflight_evidence.md",
    "backend/docs/governance/continuity_kernel_phase6w_staging_test_command_checklist.md",
    "backend/docs/governance/continuity_kernel_phase6x_staging_execution_approval_summary.md",
]

REMAINING_ACTION_ITEMS = [
    "perform approved manual staging-only flag test",
    "complete phase 6u packet during test",
    "complete phase 6q record after test",
    "keep production disabled",
    "do not enable apply mode",
    "do not execute repair",
]


class TestContinuityKernelPhase6YFinalStagingPacketCloseout(unittest.TestCase):
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

    def test_01_phase6y_closeout_doc_exists(self) -> None:
        self.assertTrue(self.doc_exists)

    def test_02_doc_says_final_staging_packet_closeout_index(self) -> None:
        self.assertIn("final staging packet closeout index", self.doc_lower)

    def test_03_doc_says_all_staging_governance_artifacts_exist(self) -> None:
        self.assertIn("all staging governance artifacts exist", self.doc_lower)

    def test_04_doc_says_only_remaining_action_is_approved_manual_staging_flag_test(self) -> None:
        self.assertIn("only remaining action is approved manual staging flag test", self.doc_lower)

    def test_05_doc_says_staging_only(self) -> None:
        self.assertIn("staging only", self.doc_lower)

    def test_06_doc_says_no_production_enablement(self) -> None:
        self.assertIn("no production enablement", self.doc_lower)

    def test_07_doc_says_no_apply_mode(self) -> None:
        self.assertIn("no apply mode", self.doc_lower)

    def test_08_doc_says_no_repair_execution(self) -> None:
        self.assertIn("no repair execution", self.doc_lower)

    def test_09_doc_says_no_data_mutation(self) -> None:
        self.assertIn("no data mutation", self.doc_lower)

    def test_10_doc_includes_all_required_artifact_index_entries(self) -> None:
        for marker in REQUIRED_ARTIFACT_INDEX:
            self.assertIn(marker, self.doc_text)

    def test_11_doc_includes_all_required_artifact_paths(self) -> None:
        for marker in REQUIRED_ARTIFACT_PATHS:
            self.assertIn(marker, self.doc_text)

    def test_12_all_required_artifact_paths_exist_in_repository(self) -> None:
        for relative_path in REQUIRED_ARTIFACT_PATHS:
            self.assertTrue((REPO_ROOT / relative_path).exists(), msg=f"Missing required artifact path: {relative_path}")

    def test_13_doc_says_dependency_backed_ci_zero_skip_proof_is_required(self) -> None:
        self.assertIn("dependency-backed ci zero-skip proof is required", self.doc_lower)

    def test_14_doc_says_production_flag_must_remain_off(self) -> None:
        self.assertIn("production flag must remain off", self.doc_lower)

    def test_15_doc_says_owner_ceo_approval_is_required(self) -> None:
        self.assertIn("owner/ceo approval is required", self.doc_lower)

    def test_16_doc_says_technical_reviewer_approval_is_required(self) -> None:
        self.assertIn("technical reviewer approval is required", self.doc_lower)

    def test_17_doc_says_rollback_qa_monitoring_owner_approvals_are_required(self) -> None:
        self.assertIn("rollback owner, qa owner, and monitoring owner are required", self.doc_lower)

    def test_18_doc_says_manual_staging_test_must_be_time_boxed(self) -> None:
        self.assertIn("manual staging test must be time-boxed", self.doc_lower)

    def test_19_doc_says_flag_must_be_disabled_after_test(self) -> None:
        self.assertIn("flag must be disabled after test", self.doc_lower)

    def test_20_doc_says_results_must_be_recorded_in_phase6q(self) -> None:
        self.assertIn("results must be recorded in phase 6q", self.doc_lower)

    def test_21_doc_includes_all_remaining_action_items(self) -> None:
        for marker in REMAINING_ACTION_ITEMS:
            self.assertIn(marker, self.doc_lower)

    def test_22_doc_says_phase6y_does_not_enable_the_flag(self) -> None:
        self.assertIn("phase 6y does not enable the flag", self.doc_lower)

    def test_23_doc_says_phase6y_does_not_change_render_settings(self) -> None:
        self.assertIn("phase 6y does not change render settings", self.doc_lower)

    def test_24_doc_says_phase6y_does_not_change_production_settings(self) -> None:
        self.assertIn("phase 6y does not change production settings", self.doc_lower)

    def test_25_doc_says_phase6y_does_not_create_apply_mode_or_repair_scripts(self) -> None:
        self.assertIn("phase 6y does not create apply mode or repair scripts", self.doc_lower)

    def test_26_doc_says_phase6y_does_not_touch_live_data(self) -> None:
        self.assertIn("phase 6y does not touch live data", self.doc_lower)

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
        self.assertFalse(repair_named_files, msg="Found unexpected repair-named files")

        for path in SCRIPTS_DIR.glob("**/*.py"):
            self.assertFalse(
                path.stat().st_mode & EXECUTABLE_PERMISSION_BITS,
                msg=f"Unexpected executable script bit set: {path}",
            )


if __name__ == "__main__":
    unittest.main()
