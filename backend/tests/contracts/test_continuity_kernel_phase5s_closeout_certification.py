from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase5s_closeout_certification.md"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "continuity-kernel-guardrails.yml"
ARCH_TESTS_DIR = REPO_ROOT / "backend" / "tests" / "architecture"
CONTRACT_TESTS_DIR = REPO_ROOT / "backend" / "tests" / "contracts"

KERNEL_MODULE_IMPORT_TOKENS = [
    "continuity_kernel_taxonomy",
    "continuity_kernel_validator",
    "continuity_kernel_dry_run_adapter",
    "continuity_kernel_admin_preview",
]

COMPLETED_MODULES = [
    "continuity_kernel_taxonomy.py",
    "continuity_kernel_validator.py",
    "continuity_kernel_dry_run_adapter.py",
    "continuity_kernel_admin_preview.py",
]

COMPLETED_GOVERNANCE_AREAS = [
    "apply-mode governance",
    "implementation contracts",
    "validator/schema design",
    "isolated validator",
    "cross-payload consistency",
    "structured overrides and justifications",
    "canonical payload placement",
    "ci guardrails",
    "staging dry-run adapter contract",
    "isolated staging dry-run adapter",
    "read-only admin preview contract",
    "isolated read-only admin preview module",
    "role/category taxonomy hardening",
    "shared taxonomy",
    "direct import cleanup",
    "pre-wiring readiness audit",
    "phase 6 read-only charter",
    "phase 6 pr checklist and stop criteria",
]

APPROVED_CAPABILITIES = [
    "isolated payload validation",
    "isolated staging dry-run payload assembly",
    "isolated read-only admin preview shaping",
    "shared role/category taxonomy",
    "structured override and justification validation",
    "ci enforcement of architecture/contract tests",
]

PROHIBITED_CAPABILITIES = [
    "live apply mode",
    "repair execution",
    "executable repair scripts",
    "database writes",
    "mint queueing",
    "certificate mutation",
    "customer record mutation",
    "frontend/customer exposure",
    "runtime route wiring",
    "service wiring",
    "admin action wiring",
    "accepting validator_result as user approval input",
    "using free-text override phrases as approval",
]

REQUIRED_SAFETY_GATES = [
    "feature flag must be off by default",
    "production default must be off",
    "first phase 6 integration must be read-only admin preview only",
    "no apply/schedule/execute/rollback action",
    "no db writes",
    "no mint queueing",
    "no certificate/customer mutation",
    "no full sensitive rollback/override/justification payload exposure",
    "architecture tests must pass",
    "contract tests must pass",
    "continuity kernel ci guardrails must pass",
    "owner approval required before merge",
]


class TestContinuityKernelPhase5SCloseoutCertification(unittest.TestCase):
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

    def test_01_phase5s_closeout_doc_exists(self) -> None:
        self.assertTrue(self.doc_exists)

    def test_02_doc_says_phase5_created_isolated_non_operational_continuity_kernel_foundation(self) -> None:
        self.assertIn("phase 5 created an isolated, non-operational continuity kernel foundation", self.doc_lower)

    def test_03_doc_says_phase5_did_not_create_live_apply_mode(self) -> None:
        self.assertIn("phase 5 did not create live apply mode", self.doc_lower)

    def test_04_doc_says_phase5_did_not_create_executable_repair_scripts(self) -> None:
        self.assertIn("phase 5 did not create executable repair scripts", self.doc_lower)

    def test_05_doc_says_phase5_did_not_touch_live_data(self) -> None:
        self.assertIn("phase 5 did not touch live data", self.doc_lower)

    def test_06_doc_says_phase5_did_not_wire_kernel_modules_into_runtime_routes_services_admin_actions(self) -> None:
        self.assertIn("phase 5 did not wire kernel modules into runtime routes/services/admin actions", self.doc_lower)

    def test_07_doc_lists_all_completed_phase5_modules(self) -> None:
        for expected in COMPLETED_MODULES:
            self.assertIn(expected, self.doc_lower)

    def test_08_doc_lists_all_completed_governance_areas(self) -> None:
        for expected in COMPLETED_GOVERNANCE_AREAS:
            self.assertIn(expected, self.doc_lower)

    def test_09_doc_lists_approved_capabilities(self) -> None:
        for expected in APPROVED_CAPABILITIES:
            self.assertIn(expected, self.doc_lower)

    def test_10_doc_lists_explicitly_prohibited_capabilities(self) -> None:
        for expected in PROHIBITED_CAPABILITIES:
            self.assertIn(expected, self.doc_lower)

    def test_11_doc_lists_required_safety_gates_before_phase6(self) -> None:
        for expected in REQUIRED_SAFETY_GATES:
            self.assertIn(expected, self.doc_lower)

    def test_12_doc_says_feature_flag_must_be_off_by_default(self) -> None:
        self.assertIn("feature flag must be off by default", self.doc_lower)

    def test_13_doc_says_production_default_must_be_off(self) -> None:
        self.assertIn("production default must be off", self.doc_lower)

    def test_14_doc_says_first_phase6_integration_must_be_read_only_admin_preview_only(self) -> None:
        self.assertIn("first phase 6 integration must be read-only admin preview only", self.doc_lower)

    def test_15_doc_says_owner_approval_required_before_merge(self) -> None:
        self.assertIn("owner approval required before merge", self.doc_lower)

    def test_16_doc_says_phase5_foundation_is_ready_for_phase6_planning(self) -> None:
        self.assertIn("phase 5 foundation is ready for phase 6 planning", self.doc_lower)

    def test_17_doc_says_phase5s_does_not_approve_phase6_implementation_by_itself(self) -> None:
        self.assertIn("phase 5s does not approve phase 6 implementation by itself", self.doc_lower)

    def test_18_doc_says_phase6_must_be_separate_pr_read_only_first_feature_flagged_and_reviewed_against_phase5r_checklist(self) -> None:
        self.assertIn(
            "phase 6 must be a separate pr, read-only first, feature-flagged, and reviewed against the phase 5r checklist",
            self.doc_lower,
        )

    def test_19_existing_kernel_modules_remain_not_imported_in_routes(self) -> None:
        self._assert_kernel_not_imported_under(self._runtime_candidates("backend/app/routes/**/*.py", "backend/app/routes/*.py"))

    def test_20_existing_kernel_modules_remain_not_imported_in_services(self) -> None:
        self._assert_kernel_not_imported_under(self._runtime_candidates("backend/app/services/**/*.py", "backend/app/services/*.py"))

    def test_21_existing_kernel_modules_remain_not_imported_in_scripts(self) -> None:
        self._assert_kernel_not_imported_under(self._runtime_candidates("backend/scripts/**/*.py", "backend/scripts/*.py"))

    def test_22_existing_kernel_modules_remain_not_imported_in_app_main(self) -> None:
        app_main = REPO_ROOT / "backend" / "app" / "main.py"
        self.assertTrue(app_main.exists(), msg="backend/app/main.py must exist for this assertion")
        self._assert_kernel_not_imported_under([app_main])

    def test_23_ci_workflow_exists(self) -> None:
        self.assertTrue(WORKFLOW_PATH.exists())

    def test_24_architecture_tests_directory_exists(self) -> None:
        self.assertTrue(ARCH_TESTS_DIR.exists() and ARCH_TESTS_DIR.is_dir())

    def test_25_contract_tests_directory_exists(self) -> None:
        self.assertTrue(CONTRACT_TESTS_DIR.exists() and CONTRACT_TESTS_DIR.is_dir())


if __name__ == "__main__":
    unittest.main()
