from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase5q_phase6_readonly_charter.md"

KERNEL_MODULE_IMPORT_TOKENS = [
    "continuity_kernel_taxonomy",
    "continuity_kernel_validator",
    "continuity_kernel_dry_run_adapter",
    "continuity_kernel_admin_preview",
]

PROHIBITED_ACTIONS = [
    "approve_apply",
    "schedule_apply",
    "execute_apply",
    "rollback_apply",
    "mutate_entitlement",
    "mutate_workspace_member",
    "mutate_certificate",
    "queue_mint",
    "delete_customer_record",
    "bypass_validator",
    "bypass_audit",
    "automatic apply after dry-run",
    "accepting validator_result as user input approval",
]


class TestContinuityKernelPhase5QPhase6ReadonlyCharter(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc_exists = DOC_PATH.exists()
        cls.doc_text = DOC_PATH.read_text(encoding="utf-8") if cls.doc_exists else ""
        cls.doc_lower = cls.doc_text.lower()

    def _runtime_candidates(self, pattern: str) -> list[Path]:
        return [path for path in REPO_ROOT.glob(pattern) if path.is_file()]

    def _assert_kernel_not_imported_under(self, paths: list[Path]) -> None:
        for path in paths:
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
            for token in KERNEL_MODULE_IMPORT_TOKENS:
                self.assertNotIn(token, text, msg=f"Unexpected kernel import token '{token}' in {path}")

    def test_01_phase5q_charter_doc_exists(self) -> None:
        self.assertTrue(self.doc_exists)

    def test_02_doc_says_phase6_must_be_read_only_first(self) -> None:
        self.assertIn("read-only-first", self.doc_lower)

    def test_03_doc_says_phase6_must_be_feature_flagged(self) -> None:
        self.assertIn("feature-flagged", self.doc_lower)

    def test_04_doc_says_feature_flag_default_must_be_false_off(self) -> None:
        self.assertIn("default must be false/off", self.doc_lower)

    def test_05_doc_says_production_default_must_be_off(self) -> None:
        self.assertIn("production default must be off", self.doc_lower)

    def test_06_doc_prohibits_apply_mode(self) -> None:
        self.assertIn("apply mode", self.doc_lower)
        self.assertIn("prohibited", self.doc_lower)

    def test_07_doc_prohibits_repair_execution(self) -> None:
        self.assertIn("repair execution", self.doc_lower)

    def test_08_doc_prohibits_database_writes(self) -> None:
        self.assertIn("database writes", self.doc_lower)

    def test_09_doc_prohibits_customer_data_mutation(self) -> None:
        self.assertIn("customer data mutation", self.doc_lower)

    def test_10_doc_prohibits_mint_queueing(self) -> None:
        self.assertIn("mint queueing", self.doc_lower)

    def test_11_doc_prohibits_certificate_mutation(self) -> None:
        self.assertIn("certificate mutation", self.doc_lower)

    def test_12_doc_lists_all_prohibited_actions(self) -> None:
        for action in PROHIBITED_ACTIONS:
            self.assertIn(action, self.doc_lower)

    def test_13_doc_says_no_customer_facing_exposure(self) -> None:
        self.assertIn("no customer-facing exposure", self.doc_lower)

    def test_14_doc_says_no_apply_schedule_execute_rollback_action(self) -> None:
        self.assertIn("no apply/schedule/execute/rollback action", self.doc_lower)

    def test_15_doc_says_first_allowed_integration_is_read_only_admin_preview_only(self) -> None:
        self.assertIn("read-only admin preview only", self.doc_lower)

    def test_16_doc_says_preview_must_not_expose_sensitive_payloads(self) -> None:
        self.assertIn("must not expose full sensitive rollback/override/justification payloads", self.doc_lower)

    def test_17_doc_includes_required_approval_gate_criteria(self) -> None:
        for expected in [
            "route/service wiring scope is read-only",
            "feature flag default is off",
            "no apply/repair execution path exists",
            "no db write methods are called",
            "no mint queueing exists",
            "no certificate/customer mutation exists",
            "no frontend/admin button triggers mutation",
            "tests prove disabled-by-default behavior",
            "tests prove no prohibited actions are returned",
        ]:
            self.assertIn(expected, self.doc_lower)

    def test_18_doc_includes_required_testing_requirements(self) -> None:
        for expected in [
            "architecture tests must pass",
            "contract tests must pass",
            "ci guardrails must pass",
            "new read-only integration tests must prove feature flag off behavior",
            "new read-only integration tests must prove no prohibited actions",
            "new read-only integration tests must prove no db writes",
        ]:
            self.assertIn(expected, self.doc_lower)

    def test_19_doc_says_phase5q_does_not_implement_phase6(self) -> None:
        self.assertIn("phase 5q does not implement phase 6", self.doc_lower)

    def test_20_doc_says_phase5q_does_not_wire_runtime_routes(self) -> None:
        self.assertIn("phase 5q does not wire runtime routes", self.doc_lower)

    def test_21_doc_says_phase5q_does_not_create_apply_mode_or_repair_scripts(self) -> None:
        self.assertIn("phase 5q does not create apply mode", self.doc_lower)
        self.assertIn("phase 5q does not create repair scripts", self.doc_lower)

    def test_22_doc_says_phase5q_does_not_touch_live_data(self) -> None:
        self.assertIn("phase 5q does not touch live data", self.doc_lower)

    def test_23_existing_kernel_modules_remain_not_imported_in_routes(self) -> None:
        self._assert_kernel_not_imported_under(self._runtime_candidates("backend/app/routes/**/*.py"))

    def test_24_existing_kernel_modules_remain_not_imported_in_services(self) -> None:
        self._assert_kernel_not_imported_under(self._runtime_candidates("backend/app/services/**/*.py"))

    def test_25_existing_kernel_modules_remain_not_imported_in_scripts(self) -> None:
        self._assert_kernel_not_imported_under(self._runtime_candidates("backend/scripts/**/*.py"))

    def test_26_existing_kernel_modules_remain_not_imported_in_app_main(self) -> None:
        app_main = REPO_ROOT / "backend" / "app" / "main.py"
        self.assertTrue(app_main.exists(), msg="Backend/app/main.py must exist for this assertion")
        self._assert_kernel_not_imported_under([app_main])


if __name__ == "__main__":
    unittest.main()
