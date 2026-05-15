import ast
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6p_staging_approval_evidence.md"
ROUTE_PATH = REPO_ROOT / "backend" / "app" / "routes" / "admin_continuity_preview.py"
ROUTES_DIR = REPO_ROOT / "backend" / "app" / "routes"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "continuity-kernel-guardrails.yml"
SCRIPTS_DIR = REPO_ROOT / "backend" / "scripts"


class TestContinuityKernelPhase6PStagingApprovalEvidence(unittest.TestCase):
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

    def test_01_phase6p_evidence_doc_exists(self) -> None:
        self.assertTrue(self.doc_exists)

    def test_02_doc_includes_feature_flag_name(self) -> None:
        self.assertIn("CONTINUITY_KERNEL_READONLY_ADMIN_PREVIEW_ENABLED", self.doc_text)

    def test_03_doc_says_staging_only_approval_evidence_package(self) -> None:
        self.assertIn("staging-only approval evidence package", self.doc_lower)

    def test_04_doc_says_required_before_enabling_flag_in_staging(self) -> None:
        self.assertIn("required before enabling the flag in staging", self.doc_lower)

    def test_05_doc_says_no_production_enablement(self) -> None:
        self.assertIn("no production enablement", self.doc_lower)

    def test_06_doc_says_no_apply_mode(self) -> None:
        self.assertIn("no apply mode", self.doc_lower)

    def test_07_doc_says_no_repair_execution(self) -> None:
        self.assertIn("no repair execution", self.doc_lower)

    def test_08_doc_says_no_data_mutation(self) -> None:
        self.assertIn("no data mutation", self.doc_lower)

    def test_09_doc_includes_all_required_approval_fields(self) -> None:
        markers = [
            "approval_record_id",
            "requested_by",
            "owner_ceo_approval",
            "technical_reviewer_approval",
            "staging_environment_name",
            "planned_start_time",
            "planned_end_time",
            "time_box_duration",
            "production_flag_confirmed_off",
            "phase_6n_criteria_confirmed",
            "dependency_backed_ci_zero_skip_confirmed",
            "rollback_owner",
            "qa_owner",
            "monitoring_owner",
            "final_signoff_required",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_text)

    def test_10_doc_includes_all_required_pre_enable_evidence(self) -> None:
        markers = [
            "latest main commit SHA",
            "latest Continuity Kernel Guardrails workflow URL",
            "continuity-kernel-guardrails job status",
            "continuity-kernel-runtime-route-test-env job status",
            "Phase 6I focused runtime test output",
            "Phase 6L no-skip enforcement output",
            "confirmation runtime tests had zero skips in dependency-backed CI",
            "production flag confirmed off",
            "confirmation no production setting will be changed",
            "confirmation no frontend/customer-facing exposure exists",
        ]
        for marker in markers:
            self.assertIn(marker.lower(), self.doc_lower)

    def test_11_doc_includes_all_required_staging_test_evidence(self) -> None:
        markers = [
            "flag-off route response captured",
            "flag-on route response captured",
            "admin-only access result",
            "non-admin denial result",
            "marketing_admin/CMO no repair execution action result",
            "prohibited actions absent result",
            "sensitive payload fields absent result",
            "POST/PUT/PATCH/DELETE unavailable result",
            "logs show no DB writes",
            "logs show no jobs queued",
            "logs show no mint queueing",
            "logs show no certificate/customer mutation",
        ]
        for marker in markers:
            self.assertIn(marker.lower(), self.doc_lower)

    def test_12_doc_includes_all_required_rollback_evidence(self) -> None:
        markers = [
            "flag disabled after test",
            "disabled route response confirmed",
            "no data mutated",
            "no jobs queued",
            "no audit/apply state created",
            "architecture tests passed after test",
            "contract tests passed after test",
            "focused Phase 6I runtime route tests passed after test",
            "Phase 6L no-skip enforcement passed after test",
        ]
        for marker in markers:
            self.assertIn(marker.lower(), self.doc_lower)

    def test_13_doc_includes_all_approval_decision_values(self) -> None:
        markers = [
            "pending",
            "approved_for_staging_test",
            "rejected",
            "completed_successfully",
            "rolled_back",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_text)

    def test_14_doc_says_production_flag_confirmed_off(self) -> None:
        self.assertIn("production flag confirmed off", self.doc_lower)

    def test_15_doc_says_dependency_backed_ci_zero_skip_confirmed(self) -> None:
        self.assertIn("dependency-backed ci zero-skip confirmed", self.doc_lower)

    def test_16_doc_says_no_production_setting_will_be_changed(self) -> None:
        self.assertIn("no production setting will be changed", self.doc_lower)

    def test_17_doc_says_no_frontend_customer_facing_exposure_exists(self) -> None:
        self.assertIn("no frontend/customer-facing exposure exists", self.doc_lower)

    def test_18_doc_says_phase6p_does_not_enable_the_flag(self) -> None:
        self.assertIn("phase 6p does not enable the flag", self.doc_lower)

    def test_19_doc_says_phase6p_does_not_change_render_settings(self) -> None:
        self.assertIn("phase 6p does not change render settings", self.doc_lower)

    def test_20_doc_says_phase6p_does_not_change_production_settings(self) -> None:
        self.assertIn("phase 6p does not change production settings", self.doc_lower)

    def test_21_doc_says_phase6p_does_not_create_apply_mode_or_repair_scripts(self) -> None:
        self.assertIn("phase 6p does not create apply mode", self.doc_lower)
        self.assertIn("phase 6p does not create repair scripts", self.doc_lower)

    def test_22_doc_says_phase6p_does_not_touch_live_data(self) -> None:
        self.assertIn("phase 6p does not touch live data", self.doc_lower)

    def test_23_route_remains_get_only(self) -> None:
        get_calls = self._route_method_calls("get")
        has_preview_get = any(
            call.args and isinstance(call.args[0], ast.Constant) and call.args[0].value == "/preview"
            for call in get_calls
        )
        self.assertTrue(has_preview_get)

    def test_24_no_post_put_patch_delete_route_exists(self) -> None:
        self.assertEqual(len(self._route_method_calls("post")), 0)
        self.assertEqual(len(self._route_method_calls("put")), 0)
        self.assertEqual(len(self._route_method_calls("patch")), 0)
        self.assertEqual(len(self._route_method_calls("delete")), 0)

        for path in ROUTES_DIR.glob("**/*.py"):
            if path == ROUTE_PATH:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            self.assertNotIn("/admin/continuity-kernel/preview", text)

    def test_25_workflow_still_enforces_no_skips(self) -> None:
        self.assertIn('CONTINUITY_KERNEL_RUNTIME_TEST_ENFORCE_NO_SKIPS: "1"', self.workflow_text)
        self.assertIn(
            "python -m unittest backend.tests.contracts.test_continuity_kernel_phase6l_runtime_no_skip_enforcement -v",
            self.workflow_text,
        )

    def test_26_no_executable_repair_script_exists(self) -> None:
        repair_named_files = [path for path in SCRIPTS_DIR.glob("**/*") if path.is_file() and "repair" in path.name.lower()]
        self.assertEqual(repair_named_files, [])

        for path in SCRIPTS_DIR.glob("**/*.py"):
            self.assertFalse(path.stat().st_mode & 0o111, msg=f"Unexpected executable script bit set: {path}")


if __name__ == "__main__":
    unittest.main()
