import ast
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6u_staging_manual_test_packet.md"
ROUTE_PATH = REPO_ROOT / "backend" / "app" / "routes" / "admin_continuity_preview.py"
ROUTES_DIR = REPO_ROOT / "backend" / "app" / "routes"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "continuity-kernel-guardrails.yml"
SCRIPTS_DIR = REPO_ROOT / "backend" / "scripts"
EXECUTABLE_PERMISSION_BITS = 0o111


class TestContinuityKernelPhase6UStagingManualTestPacket(unittest.TestCase):
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

    def test_01_phase6u_manual_test_packet_doc_exists(self) -> None:
        self.assertTrue(self.doc_exists)

    def test_02_doc_says_fillable_staging_manual_test_packet(self) -> None:
        self.assertIn("fillable staging manual test packet", self.doc_lower)

    def test_03_doc_says_used_only_after_phase6s_go_decision(self) -> None:
        self.assertIn("used only after phase 6s go decision", self.doc_lower)

    def test_04_doc_says_used_only_for_staging(self) -> None:
        self.assertIn("used only for staging", self.doc_lower)

    def test_05_doc_says_no_production_enablement(self) -> None:
        self.assertIn("no production enablement", self.doc_lower)

    def test_06_doc_says_no_apply_mode(self) -> None:
        self.assertIn("no apply mode", self.doc_lower)

    def test_07_doc_says_no_repair_execution(self) -> None:
        self.assertIn("no repair execution", self.doc_lower)

    def test_08_doc_says_no_data_mutation(self) -> None:
        self.assertIn("no data mutation", self.doc_lower)

    def test_09_doc_includes_all_packet_identification_fields(self) -> None:
        markers = [
            "packet_id:",
            "related_phase6p_approval_record_id:",
            "related_phase6q_execution_record_id:",
            "staging_environment_name:",
            "tester_name:",
            "technical_reviewer:",
            "owner_ceo_signoff_reference:",
            "planned_test_window:",
            "production_flag_confirmed_off:",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_text)

    def test_10_doc_includes_all_pre_enable_checklist_fields(self) -> None:
        markers = [
            "Phase 6N readiness confirmed:",
            "Phase 6O runbook reviewed:",
            "Phase 6P approval/evidence completed:",
            "Phase 6R packet index completed:",
            "Phase 6S go decision completed:",
            "Phase 6T readiness lock confirmed:",
            "dependency-backed CI zero-skip proof attached:",
            "rollback owner assigned:",
            "QA owner assigned:",
            "monitoring owner assigned:",
            "production flag confirmed off:",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_text)

    def test_11_doc_includes_all_staging_flag_action_log_fields(self) -> None:
        markers = [
            "flag_before_test:",
            "flag_enabled_at:",
            "flag_enabled_by:",
            "flag_disabled_at:",
            "flag_disabled_by:",
            "flag_after_test:",
            "production_flag_unchanged:",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_text)

    def test_12_doc_includes_all_manual_qa_checklist_fields(self) -> None:
        markers = [
            "flag off route returns disabled",
            "flag on route returns read-only envelope",
            "admin-only access confirmed",
            "non-admin denied",
            "marketing_admin/CMO no repair execution actions",
            "no prohibited actions",
            "no full rollback_plan exposed",
            "no override reason_detail exposed",
            "no justification reason_detail exposed",
            "no audit_context exposed",
            "no POST/PUT/PATCH/DELETE methods available",
            "no customer-facing route",
            "no frontend/admin button exposed",
            "no DB writes observed",
            "no job queue activity observed",
            "no mint queueing observed",
            "no certificate/customer mutation observed",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_text)

    def test_13_doc_includes_all_monitoring_log_fields(self) -> None:
        markers = [
            "backend logs checked:",
            "auth failures checked:",
            "error rates checked:",
            "route access attempts checked:",
            "write operation scan completed:",
            "job queue scan completed:",
            "mint queue scan completed:",
            "customer-facing traffic scan completed:",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_text)

    def test_14_doc_includes_all_rollback_confirmation_fields(self) -> None:
        markers = [
            "flag disabled after test:",
            "disabled response confirmed:",
            "production flag still off:",
            "no data mutated:",
            "no jobs queued:",
            "no audit/apply state created:",
            "architecture tests rerun:",
            "contract tests rerun:",
            "focused Phase 6I runtime route test rerun:",
            "Phase 6L no-skip enforcement rerun:",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_text)

    def test_15_doc_includes_all_final_decision_fields(self) -> None:
        markers = [
            "result:",
            "qa_owner_signoff:",
            "monitoring_owner_signoff:",
            "technical_reviewer_signoff:",
            "owner_ceo_signoff:",
            "follow_up_required:",
            "final_notes:",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_text)

    def test_16_doc_includes_final_result_values(self) -> None:
        markers = [
            "passed",
            "passed_with_notes",
            "failed",
            "rolled_back",
            "blocked",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_text)

    def test_17_doc_says_production_flag_confirmed_off(self) -> None:
        self.assertIn("production flag confirmed off", self.doc_lower)

    def test_18_doc_says_production_flag_unchanged(self) -> None:
        self.assertIn("production_flag_unchanged", self.doc_text)

    def test_19_doc_says_no_frontend_admin_button_exposed(self) -> None:
        self.assertIn("no frontend/admin button exposed", self.doc_lower)

    def test_20_doc_says_no_customer_facing_route(self) -> None:
        self.assertIn("no customer-facing route", self.doc_lower)

    def test_21_doc_says_phase6u_does_not_enable_the_flag(self) -> None:
        self.assertIn("phase 6u does not enable the flag", self.doc_lower)

    def test_22_doc_says_phase6u_does_not_change_render_settings(self) -> None:
        self.assertIn("phase 6u does not change render settings", self.doc_lower)

    def test_23_doc_says_phase6u_does_not_change_production_settings(self) -> None:
        self.assertIn("phase 6u does not change production settings", self.doc_lower)

    def test_24_doc_says_phase6u_does_not_create_apply_mode_or_repair_scripts(self) -> None:
        self.assertIn("phase 6u does not create apply mode", self.doc_lower)
        self.assertIn("phase 6u does not create repair scripts", self.doc_lower)

    def test_25_doc_says_phase6u_does_not_touch_live_data(self) -> None:
        self.assertIn("phase 6u does not touch live data", self.doc_lower)

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
            text = path.read_text(encoding="utf-8", errors="ignore")
            self.assertNotIn("/admin/continuity-kernel/preview", text)

    def test_28_workflow_still_enforces_no_skips(self) -> None:
        self.assertIn('CONTINUITY_KERNEL_RUNTIME_TEST_ENFORCE_NO_SKIPS: "1"', self.workflow_text)
        self.assertIn(
            "python -m unittest backend.tests.contracts.test_continuity_kernel_phase6l_runtime_no_skip_enforcement -v",
            self.workflow_text,
        )

    def test_29_no_executable_repair_script_exists(self) -> None:
        repair_named_files = [path for path in SCRIPTS_DIR.glob("**/*") if path.is_file() and "repair" in path.name.lower()]
        self.assertEqual(repair_named_files, [])

        for path in SCRIPTS_DIR.glob("**/*.py"):
            self.assertFalse(
                path.stat().st_mode & EXECUTABLE_PERMISSION_BITS,
                msg=f"Unexpected executable script bit set: {path}",
            )


if __name__ == "__main__":
    unittest.main()
