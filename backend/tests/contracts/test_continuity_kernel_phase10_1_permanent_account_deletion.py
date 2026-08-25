from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
HTML_PATH = REPO_ROOT / "admin-control-center.html"
JS_PATH = REPO_ROOT / "admin-control-center.js"
SERVICE_PATH = REPO_ROOT / "backend" / "app" / "services" / "admin_control_service.py"
RUNTIME_PATH = REPO_ROOT / "backend" / "app" / "services" / "continuity_runtime_service.py"
VALIDATOR_PATH = REPO_ROOT / "backend" / "app" / "core" / "continuity_kernel_validator.py"
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase10_1_permanent_account_deletion.md"


class TestContinuityKernelPhase101PermanentAccountDeletion(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = HTML_PATH.read_text(encoding="utf-8")
        cls.javascript = JS_PATH.read_text(encoding="utf-8")
        cls.service = SERVICE_PATH.read_text(encoding="utf-8")
        cls.runtime = RUNTIME_PATH.read_text(encoding="utf-8")
        cls.validator = VALIDATOR_PATH.read_text(encoding="utf-8")
        cls.doc = DOC_PATH.read_text(encoding="utf-8")

    def test_01_recoverable_and_irreversible_controls_are_separate(self) -> None:
        self.assertIn('data-super-admin-user-action="billing_hold"', self.javascript)
        self.assertIn("Place on Billing Hold", self.javascript)
        self.assertIn("Recoverable archive", self.javascript)
        self.assertIn("data-super-admin-permanent-delete", self.javascript)
        self.assertIn("Permanent deletion", self.javascript)

    def test_02_permanent_deletion_has_a_separate_final_warning(self) -> None:
        for marker in (
            "data-admin-permanent-delete-dialog",
            "data-admin-permanent-delete-final-dialog",
            "This account will be permanently closed",
            "Type PERMANENTLY DELETE",
            "data-admin-permanent-delete-final-confirm",
            "Permanently Delete Account",
        ):
            self.assertIn(marker, self.html)

    def test_03_both_confirmations_are_enforced_by_backend_execution(self) -> None:
        self.assertIn('PERMANENT_DELETE_CONFIRMATION_PHRASE = "PERMANENTLY DELETE"', self.service)
        self.assertIn("confirmation_email", self.service)
        self.assertIn("initial_confirmation", self.service)
        self.assertIn("final_confirmation", self.service)
        self.assertIn("final_acknowledgement", self.service)
        self.assertIn("The confirmation email does not match", self.service)
        self.assertIn("Permanent account deletion is blocked for this identity", self.service)

    def test_04_kernel_registers_irreversible_execution_and_evidence_only_rollback(self) -> None:
        self.assertIn('RUNTIME_VERSION = "13.0.0"', self.runtime)
        self.assertIn('"account_permanent_delete": ActionSpec(', self.runtime)
        self.assertIn('"strategy": "irreversible_identity_erasure"', self.runtime)
        self.assertIn('"restoration_prohibited": True', self.runtime)
        self.assertIn('"evidence_only": True', self.runtime)
        self.assertIn("super_admin_apply_account_permanent_deletion", self.runtime)
        self.assertIn("Permanent account deletion is restricted to the canonical CEO Master Administrator", self.runtime)

    def test_05_mongodb_receipt_and_tombstone_are_first_class_records(self) -> None:
        for marker in (
            'ACCOUNT_DELETION_TOMBSTONES_COLLECTION = "account_deletion_tombstones"',
            '"continuity_operation_id"',
            '"original_email_sha256"',
            '"status": "started"',
            '"status": "completed"',
            '"records_closed"',
            '"mongo_evidence"',
            '"continuity_operations"',
            '"continuity_events"',
        ):
            self.assertIn(marker, self.service + self.runtime)
        self.assertIn("data-admin-kernel-view-deletion-receipt", self.javascript)

    def test_06_login_identity_is_destroyed_but_required_evidence_is_preserved(self) -> None:
        for marker in (
            '"password_hash": None',
            '"mfa_secret_encrypted": None',
            '"stripe_customer_id": None',
            '"status": "permanently_deleted"',
            '"login_enabled": False',
            '"restorable": False',
            '"orders"',
            '"billing_history"',
            '"corporate_ownership_records"',
            '"audit_logs"',
            '"project_link_keys"',
            '"admin_impersonation_sessions"',
            "stripe_admin_operations_service.cancel_subscription",
        ):
            self.assertIn(marker, self.service)

    def test_07_validator_exception_is_narrowly_scoped_to_structured_deletion(self) -> None:
        self.assertIn("_is_governed_permanent_account_deletion", self.validator)
        self.assertIn('"PROHIBITED_DELETE_CUSTOMER_RECORD"', self.validator)
        self.assertIn('== "account_permanent_delete"', self.validator)
        self.assertIn('proposed_after.get("restorable") is False', self.validator)

    def test_08_governance_document_explains_retention_and_interrupted_execution(self) -> None:
        for phrase in (
            "billing hold",
            "permanent delete",
            "corporate ownership records",
            "raw former email is not stored",
            "status=started",
            "status=completed",
            "no permanent-deletion success receipt",
        ):
            self.assertIn(phrase, self.doc.lower())


if __name__ == "__main__":
    unittest.main()
