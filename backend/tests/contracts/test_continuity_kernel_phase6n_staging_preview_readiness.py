import ast
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase6n_staging_preview_readiness.md"
ROUTE_PATH = REPO_ROOT / "backend" / "app" / "routes" / "admin_continuity_preview.py"
ROUTES_DIR = REPO_ROOT / "backend" / "app" / "routes"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "continuity-kernel-guardrails.yml"
SCRIPTS_DIR = REPO_ROOT / "backend" / "scripts"


class TestContinuityKernelPhase6NStagingPreviewReadiness(unittest.TestCase):
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

    def test_01_phase6n_doc_exists(self) -> None:
        self.assertTrue(self.doc_exists)

    def test_02_doc_says_staging_only_readiness_review(self) -> None:
        self.assertIn("staging-only readiness review", self.doc_lower)

    def test_03_doc_says_no_production_enablement(self) -> None:
        self.assertIn("phase 6n does not approve production enablement", self.doc_lower)

    def test_04_doc_says_no_apply_mode(self) -> None:
        self.assertIn("phase 6n does not approve apply mode", self.doc_lower)

    def test_05_doc_says_no_repair_execution(self) -> None:
        self.assertIn("phase 6n does not approve repair execution", self.doc_lower)

    def test_06_doc_includes_all_staging_readiness_criteria(self) -> None:
        markers = [
            "the route is get-only",
            "the route is admin-only",
            "the route is feature-flagged",
            "route returns disabled when flag is missing, off, or invalid",
            "no prohibited actions are returned",
            "no db writes",
            "no mint queueing",
            "no certificate/customer mutation",
            "no full rollback_plan exposure",
            "no full override/justification reason_detail exposure",
            "no full audit_context exposure",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_lower)

    def test_07_doc_says_phase6i_zero_skips_dependency_backed_ci(self) -> None:
        self.assertIn("phase 6i runtime route tests pass with zero skips in dependency-backed ci", self.doc_lower)

    def test_08_doc_says_phase6l_no_skip_enforcement_passes(self) -> None:
        self.assertIn("phase 6l no-skip enforcement passes", self.doc_lower)

    def test_09_doc_says_feature_flag_default_off(self) -> None:
        self.assertIn("feature flag default remains off", self.doc_lower)

    def test_10_doc_says_production_default_off(self) -> None:
        self.assertIn("production default remains off", self.doc_lower)

    def test_11_doc_says_true_like_returns_read_only_envelope(self) -> None:
        self.assertIn("explicit true-like flag returns read-only envelope", self.doc_lower)

    def test_12_doc_says_no_prohibited_actions_returned(self) -> None:
        self.assertIn("no prohibited actions are returned", self.doc_lower)

    def test_13_doc_says_no_db_writes(self) -> None:
        self.assertIn("no db writes", self.doc_lower)

    def test_14_doc_says_no_mint_queueing(self) -> None:
        self.assertIn("no mint queueing", self.doc_lower)

    def test_15_doc_says_no_certificate_customer_mutation(self) -> None:
        self.assertIn("no certificate/customer mutation", self.doc_lower)

    def test_16_doc_says_no_full_rollback_plan_exposure(self) -> None:
        self.assertIn("no full rollback_plan exposure", self.doc_lower)

    def test_17_doc_says_no_full_reason_detail_exposure(self) -> None:
        self.assertIn("no full override/justification reason_detail exposure", self.doc_lower)

    def test_18_doc_says_no_full_audit_context_exposure(self) -> None:
        self.assertIn("no full audit_context exposure", self.doc_lower)

    def test_19_doc_includes_all_staging_enablement_restrictions(self) -> None:
        markers = [
            "staging only",
            "enablement must be explicitly approved",
            "enablement must be time-boxed or reviewed after test",
            "must not enable in production",
            "must not expose customer-facing route",
            "must not expose frontend/admin ui buttons unless separately approved",
            "must not permit apply/schedule/execute/rollback actions",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_lower)

    def test_20_doc_includes_staging_manual_qa_checklist_items(self) -> None:
        markers = [
            "confirm flag-off response",
            "confirm flag-on response",
            "confirm admin-only access",
            "confirm non-admin denial",
            "confirm marketing_admin/cmo receives no repair execution actions",
            "confirm no prohibited actions",
            "confirm no sensitive full payload fields",
            "confirm logs show no db write/mutation/job activity",
            "confirm disabling the flag returns the route to disabled state",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_lower)

    def test_21_doc_includes_rollback_criteria(self) -> None:
        markers = [
            "disable feature flag",
            "confirm disabled response",
            "confirm no data mutated",
            "confirm no jobs queued",
            "confirm no audit/apply state created",
            "rerun architecture/contracts/runtime tests",
        ]
        for marker in markers:
            self.assertIn(marker, self.doc_lower)

    def test_22_doc_says_phase6n_may_certify_staging_only(self) -> None:
        self.assertIn("phase 6n may certify staging readiness only", self.doc_lower)

    def test_23_doc_says_phase6n_does_not_approve_production_enablement(self) -> None:
        self.assertIn("phase 6n does not approve production enablement", self.doc_lower)

    def test_24_doc_says_phase6n_does_not_approve_apply_or_repair(self) -> None:
        self.assertIn("phase 6n does not approve apply mode", self.doc_lower)
        self.assertIn("phase 6n does not approve repair execution", self.doc_lower)

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
            self.assertFalse(path.stat().st_mode & 0o111, msg=f"Unexpected executable script bit set: {path}")


if __name__ == "__main__":
    unittest.main()
