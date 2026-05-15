import ast
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6r_staging_approval_packet_index.md"
PHASE_6N_DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6n_staging_preview_readiness.md"
PHASE_6O_DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6o_staging_flag_runbook.md"
PHASE_6P_DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6p_staging_approval_evidence.md"
PHASE_6Q_DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6q_staging_execution_record.md"
ROUTE_PATH = REPO_ROOT / "backend" / "app" / "routes" / "admin_continuity_preview.py"
ROUTES_DIR = REPO_ROOT / "backend" / "app" / "routes"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "continuity-kernel-guardrails.yml"
SCRIPTS_DIR = REPO_ROOT / "backend" / "scripts"
EXECUTABLE_PERMISSION_BITS = 0o111


class TestContinuityKernelPhase6RStagingApprovalPacketIndex(unittest.TestCase):
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

    def test_01_phase6r_packet_index_doc_exists(self) -> None:
        self.assertTrue(self.doc_exists)

    def test_02_doc_says_master_staging_approval_packet_index(self) -> None:
        self.assertIn("master staging approval packet index", self.doc_lower)

    def test_03_doc_says_prevents_out_of_order_staging_enablement(self) -> None:
        self.assertIn("prevents out-of-order staging enablement", self.doc_lower)

    def test_04_doc_says_no_production_enablement(self) -> None:
        self.assertIn("no production enablement", self.doc_lower)

    def test_05_doc_says_no_apply_mode(self) -> None:
        self.assertIn("no apply mode", self.doc_lower)

    def test_06_doc_says_no_repair_execution(self) -> None:
        self.assertIn("no repair execution", self.doc_lower)

    def test_07_doc_says_no_data_mutation(self) -> None:
        self.assertIn("no data mutation", self.doc_lower)

    def test_08_doc_lists_phase6n_staging_preview_readiness_review(self) -> None:
        self.assertIn("phase 6n staging preview readiness review", self.doc_lower)

    def test_09_doc_lists_phase6o_staging_flag_enablement_runbook(self) -> None:
        self.assertIn("phase 6o staging flag enablement runbook", self.doc_lower)

    def test_10_doc_lists_phase6p_staging_approval_evidence_package(self) -> None:
        self.assertIn("phase 6p staging approval evidence package", self.doc_lower)

    def test_11_doc_lists_phase6q_staging_execution_result_record(self) -> None:
        self.assertIn("phase 6q staging execution result record", self.doc_lower)

    def test_12_doc_includes_all_required_order_steps(self) -> None:
        markers = [
            "step 1: complete phase 6n readiness criteria",
            "step 2: complete phase 6p approval/evidence package",
            "step 3: execute phase 6o staging flag runbook",
            "step 4: complete phase 6q staging execution result record",
            "step 5: confirm flag disabled after test",
            "step 6: confirm no data mutation, no jobs queued, no audit/apply state created",
            "step 7: record final owner/ceo and technical reviewer sign-off",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_lower)

    def test_13_doc_includes_all_required_pre_staging_hard_stops(self) -> None:
        markers = [
            "phase 6n criteria missing",
            "phase 6p approval missing",
            "owner/ceo approval missing",
            "technical reviewer approval missing",
            "production flag not confirmed off",
            "dependency-backed ci zero-skip proof missing",
            "rollback owner missing",
            "qa owner missing",
            "monitoring owner missing",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_lower)

    def test_14_doc_includes_all_required_post_staging_hard_stops(self) -> None:
        markers = [
            "flag not disabled after test",
            "disabled response not confirmed",
            "data mutation detected",
            "job queue activity detected",
            "mint queueing detected",
            "certificate/customer mutation detected",
            "prohibited actions observed",
            "sensitive payload exposure observed",
            "architecture/contract/runtime tests not rerun",
            "final sign-off missing",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_lower)

    def test_15_doc_includes_all_staging_decision_states(self) -> None:
        markers = [
            "not_ready",
            "ready_for_approval",
            "approved_for_staging_test",
            "staging_test_in_progress",
            "completed_successfully",
            "rolled_back",
            "rejected",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_text)

    def test_16_doc_says_phase6r_does_not_enable_the_flag(self) -> None:
        self.assertIn("phase 6r does not enable the flag", self.doc_lower)

    def test_17_doc_says_phase6r_does_not_change_render_settings(self) -> None:
        self.assertIn("phase 6r does not change render settings", self.doc_lower)

    def test_18_doc_says_phase6r_does_not_change_production_settings(self) -> None:
        self.assertIn("phase 6r does not change production settings", self.doc_lower)

    def test_19_doc_says_phase6r_does_not_create_apply_mode_or_repair_scripts(self) -> None:
        self.assertIn("phase 6r does not create apply mode", self.doc_lower)
        self.assertIn("phase 6r does not create repair scripts", self.doc_lower)

    def test_20_doc_says_phase6r_does_not_touch_live_data(self) -> None:
        self.assertIn("phase 6r does not touch live data", self.doc_lower)

    def test_21_phase6n_doc_exists(self) -> None:
        self.assertTrue(PHASE_6N_DOC_PATH.exists())

    def test_22_phase6o_doc_exists(self) -> None:
        self.assertTrue(PHASE_6O_DOC_PATH.exists())

    def test_23_phase6p_doc_exists(self) -> None:
        self.assertTrue(PHASE_6P_DOC_PATH.exists())

    def test_24_phase6q_doc_exists(self) -> None:
        self.assertTrue(PHASE_6Q_DOC_PATH.exists())

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
