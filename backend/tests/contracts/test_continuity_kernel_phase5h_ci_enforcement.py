from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase5h_ci_enforcement.md"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "continuity-kernel-guardrails.yml"


class TestContinuityKernelPhase5HCiEnforcement(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.doc_text = DOC_PATH.read_text(encoding="utf-8") if DOC_PATH.exists() else ""
        cls.doc_lower = cls.doc_text.lower()
        cls.workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8") if WORKFLOW_PATH.exists() else ""

    def test_01_phase5h_ci_enforcement_doc_exists(self) -> None:
        self.assertTrue(DOC_PATH.exists())

    def test_02_doc_includes_three_ci_commands(self) -> None:
        for command in [
            "python -m compileall backend/app backend/scripts",
            'python -m unittest discover -s backend/tests/architecture -p "test_*.py" -v',
            'python -m unittest discover -s backend/tests/contracts -p "test_*.py" -v',
        ]:
            self.assertIn(command, self.doc_text)

    def test_03_doc_says_ci_must_not_require_database_connection(self) -> None:
        self.assertIn("database connection", self.doc_lower)

    def test_04_doc_says_ci_must_not_require_live_secrets(self) -> None:
        self.assertIn("live secrets", self.doc_lower)

    def test_05_doc_says_ci_must_not_require_fastapi_startup(self) -> None:
        self.assertIn("fastapi startup", self.doc_lower)

    def test_06_doc_says_ci_must_not_require_stripe_web3_connection(self) -> None:
        self.assertIn("stripe/web3 connection", self.doc_lower)

    def test_07_doc_says_ci_must_not_require_customer_or_production_data(self) -> None:
        self.assertIn("customer data", self.doc_lower)
        self.assertIn("production data", self.doc_lower)

    def test_08_doc_says_ci_fails_for_duplicate_source_of_truth_drift(self) -> None:
        self.assertIn("duplicate package/role/entitlement/manifest source-of-truth files appear", self.doc_lower)

    def test_09_doc_says_ci_fails_for_unsafe_repair_apply_behavior(self) -> None:
        self.assertIn("repair scripts lack dry-run/apply controls", self.doc_lower)

    def test_10_doc_includes_non_operational_guardrails(self) -> None:
        for line in [
            "phase 5h does not wire validator into runtime routes",
            "phase 5h does not create apply mode",
            "phase 5h does not create repair scripts",
            "phase 5h does not touch live data",
            "phase 5h only adds ci/test-gate protection",
        ]:
            self.assertIn(line, self.doc_lower)

    def test_11_if_workflow_file_exists_it_includes_required_triggers_and_commands(self) -> None:
        if not WORKFLOW_PATH.exists():
            self.skipTest("Workflow file is optional when equivalent CI exists elsewhere")

        for required in [
            "pull_request",
            "push",
            "python -m compileall backend/app backend/scripts",
            'python -m unittest discover -s backend/tests/architecture -p "test_*.py" -v',
            'python -m unittest discover -s backend/tests/contracts -p "test_*.py" -v',
        ]:
            self.assertIn(required, self.workflow_text)


if __name__ == "__main__":
    unittest.main()
