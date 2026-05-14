from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase5r_phase6_pr_checklist.md"

KERNEL_MODULE_IMPORT_TOKENS = [
    "continuity_kernel_taxonomy",
    "continuity_kernel_validator",
    "continuity_kernel_dry_run_adapter",
    "continuity_kernel_admin_preview",
]


class TestContinuityKernelPhase5RPhase6PRChecklist(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc_exists = DOC_PATH.exists()
        cls.doc_text = DOC_PATH.read_text(encoding="utf-8") if cls.doc_exists else ""
        cls.doc_lower = cls.doc_text.lower()

    def _runtime_candidates(self, *patterns: str) -> list[Path]:
        candidates: list[Path] = []
        for pattern in patterns:
            candidates.extend(path for path in REPO_ROOT.glob(pattern) if path.is_file())
        return candidates

    def _assert_kernel_not_imported_under(self, paths: list[Path]) -> None:
        for path in paths:
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            for token in KERNEL_MODULE_IMPORT_TOKENS:
                self.assertNotIn(token, text, msg=f"Unexpected kernel import token '{token}' in {path}")

    def test_01_phase5r_checklist_doc_exists(self) -> None:
        self.assertTrue(self.doc_exists)

    def test_02_doc_says_every_phase6_pr_must_include_feature_flag_name(self) -> None:
        self.assertIn("feature flag name", self.doc_lower)

    def test_03_doc_requires_proof_feature_flag_default_is_off(self) -> None:
        self.assertIn("proof feature flag default is off", self.doc_lower)

    def test_04_doc_requires_proof_production_default_is_off(self) -> None:
        self.assertIn("proof production default is off", self.doc_lower)

    def test_05_doc_requires_changed_file_list(self) -> None:
        self.assertIn("changed file list", self.doc_lower)

    def test_06_doc_requires_proof_wiring_is_read_only(self) -> None:
        self.assertIn("proof wiring is read-only", self.doc_lower)

    def test_07_doc_requires_proof_no_apply_mode_exists(self) -> None:
        self.assertIn("proof no apply mode exists", self.doc_lower)

    def test_08_doc_requires_proof_no_repair_scripts_were_created(self) -> None:
        self.assertIn("proof no repair scripts were created", self.doc_lower)

    def test_09_doc_requires_proof_no_database_write_calls_were_added(self) -> None:
        self.assertIn("proof no database write calls were added", self.doc_lower)

    def test_10_doc_requires_proof_no_mint_queueing_was_added(self) -> None:
        self.assertIn("proof no mint queueing was added", self.doc_lower)

    def test_11_doc_requires_proof_no_certificate_mutation_was_added(self) -> None:
        self.assertIn("proof no certificate mutation was added", self.doc_lower)

    def test_12_doc_requires_proof_no_customer_record_mutation_was_added(self) -> None:
        self.assertIn("proof no customer record mutation was added", self.doc_lower)

    def test_13_doc_requires_rollback_plan(self) -> None:
        self.assertIn("rollback plan", self.doc_lower)

    def test_14_doc_requires_manual_qa_plan(self) -> None:
        self.assertIn("manual qa plan", self.doc_lower)

    def test_15_doc_includes_all_required_phase6_tests(self) -> None:
        for expected in [
            "feature flag off returns unavailable/disabled response",
            "feature flag on in test/staging returns read-only preview only",
            "no prohibited actions returned",
            "no db write methods called",
            "no mint queueing called",
            "no apply/schedule/execute/rollback actions exposed",
            "no full rollback_plan exposed",
            "no full override/justification audit_context exposed",
            "no customer-facing route exposed",
            "architecture tests pass",
            "contract tests pass",
            "ci guardrails pass",
        ]:
            self.assertIn(expected, self.doc_lower)

    def test_16_doc_includes_all_stop_criteria(self) -> None:
        for expected in [
            "apply mode appears",
            "repair script appears",
            "db write method appears",
            "mint queueing appears",
            "certificate mutation appears",
            "customer mutation appears",
            "frontend customer exposure appears",
            "feature flag defaults on",
            "production default can be on accidentally",
            "validator_result is accepted as user approval input",
            "prohibited actions appear in preview",
            "admin preview exposes full sensitive rollback/override/justification payloads",
            "kernel modules are wired outside the approved read-only path",
        ]:
            self.assertIn(expected, self.doc_lower)

    def test_17_doc_includes_all_rollback_criteria(self) -> None:
        for expected in [
            "how to disable the feature flag",
            "how to remove the route/helper safely",
            "how to confirm no data was mutated",
            "how to confirm no jobs were queued",
            "how to confirm no audit/apply state was created",
            "how to run architecture and contract tests after rollback",
        ]:
            self.assertIn(expected, self.doc_lower)

    def test_18_doc_says_future_phase6_may_only_consider_one_read_only_route_helper_or_one_existing_admin_route_extension(self) -> None:
        self.assertIn("one read-only route/helper file or one existing admin route extension", self.doc_lower)

    def test_19_doc_says_no_frontend_changes_unless_separately_approved(self) -> None:
        self.assertIn("no frontend changes unless separately approved", self.doc_lower)

    def test_20_doc_says_phase5r_does_not_implement_phase6(self) -> None:
        self.assertIn("phase 5r does not implement phase 6", self.doc_lower)

    def test_21_doc_says_phase5r_does_not_wire_runtime_routes(self) -> None:
        self.assertIn("phase 5r does not wire runtime routes", self.doc_lower)

    def test_22_doc_says_phase5r_does_not_create_apply_mode_or_repair_scripts(self) -> None:
        self.assertIn("phase 5r does not create apply mode", self.doc_lower)
        self.assertIn("phase 5r does not create repair scripts", self.doc_lower)

    def test_23_doc_says_phase5r_does_not_touch_live_data(self) -> None:
        self.assertIn("phase 5r does not touch live data", self.doc_lower)

    def test_24_existing_kernel_modules_remain_not_imported_in_routes(self) -> None:
        self._assert_kernel_not_imported_under(self._runtime_candidates("backend/app/routes/**/*.py", "backend/app/routes/*.py"))

    def test_25_existing_kernel_modules_remain_not_imported_in_services(self) -> None:
        self._assert_kernel_not_imported_under(self._runtime_candidates("backend/app/services/**/*.py", "backend/app/services/*.py"))

    def test_26_existing_kernel_modules_remain_not_imported_in_scripts(self) -> None:
        self._assert_kernel_not_imported_under(self._runtime_candidates("backend/scripts/**/*.py", "backend/scripts/*.py"))

    def test_27_existing_kernel_modules_remain_not_imported_in_app_main(self) -> None:
        app_main = REPO_ROOT / "backend" / "app" / "main.py"
        self.assertTrue(app_main.exists(), msg="backend/app/main.py must exist for this assertion")
        self._assert_kernel_not_imported_under([app_main])


if __name__ == "__main__":
    unittest.main()
