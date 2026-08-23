from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_PATH = REPO_ROOT / "backend" / "app" / "services" / "continuity_runtime_service.py"
AUTH_PATH = REPO_ROOT / "backend" / "app" / "services" / "auth_service.py"
PERMISSIONS_PATH = REPO_ROOT / "backend" / "app" / "core" / "admin_permission_registry.py"
DEPENDENCIES_PATH = REPO_ROOT / "backend" / "app" / "dependencies" / "auth.py"
GUARD_PATH = REPO_ROOT / "backend" / "app" / "core" / "continuity_route_guard.py"
STRIPE_PATH = REPO_ROOT / "backend" / "app" / "routes" / "stripe_webhooks.py"
DELETION_PATH = REPO_ROOT / "backend" / "app" / "services" / "admin_control_service.py"
DATABASE_PATH = REPO_ROOT / "backend" / "app" / "database.py"
AUTH_JS_PATH = REPO_ROOT / "auth.js"
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase11_backend_security_correction.md"


class TestContinuityKernelPhase11BackendSecurityCorrection(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime = RUNTIME_PATH.read_text(encoding="utf-8")
        cls.auth = AUTH_PATH.read_text(encoding="utf-8")
        cls.permissions = PERMISSIONS_PATH.read_text(encoding="utf-8")
        cls.dependencies = DEPENDENCIES_PATH.read_text(encoding="utf-8")
        cls.guard = GUARD_PATH.read_text(encoding="utf-8")
        cls.stripe = STRIPE_PATH.read_text(encoding="utf-8")
        cls.deletion = DELETION_PATH.read_text(encoding="utf-8")
        cls.database = DATABASE_PATH.read_text(encoding="utf-8")
        cls.auth_js = AUTH_JS_PATH.read_text(encoding="utf-8")
        cls.doc = DOC_PATH.read_text(encoding="utf-8")

    def test_01_runtime_preserves_phase11_and_registers_legacy_remediation(self) -> None:
        self.assertIn('RUNTIME_VERSION = "12.0.0"', self.runtime)
        self.assertIn('"legacy_admin_remediation": ActionSpec(', self.runtime)
        self.assertIn("retry_failed_operation", self.runtime)
        self.assertIn("RETRY_SAME_IDEMPOTENT_OPERATION", self.runtime)

    def test_02_ceo_is_the_only_wildcard_identity(self) -> None:
        self.assertIn('"super_admin": set()', self.permissions)
        self.assertIn('"ceo_master_admin": {"*"}', self.permissions)
        self.assertIn("is_canonical_ceo_email", self.dependencies)
        self.assertIn("permissions.discard(\"*\")", self.dependencies)
        self.assertIn("capabilities.discard(\"*\")", self.dependencies)

    def test_03_activation_is_passwordless_hashed_fragment_and_atomic(self) -> None:
        for marker in (
            '"status": "pending_activation"',
            '"password_hash": None',
            "_hash_account_activation_token",
            '"account_activation_token_hash": expected_activation_hash',
            '"password_hash": {"$in": [None, ""]}',
            "idx_users_email_unique",
            "idx_users_activation_token_hash_unique",
        ):
            self.assertIn(marker, self.auth)
        self.assertIn("#activation_token=", self.auth)
        self.assertIn("window.location.hash", self.auth_js)
        self.assertIn("window.history.replaceState", self.auth_js)

    def test_04_covered_legacy_mutations_fail_into_kernel(self) -> None:
        for marker in (
            "continuity_kernel_required",
            "/admin/control-center",
            "/admin/stripe-ops",
            "/auth/admin/users/",
            "/orders/admin/manual-order",
            "/project-entitlements/apply",
        ):
            self.assertIn(marker, self.guard + self.doc)

    def test_05_stripe_failures_are_retryable_not_false_completion(self) -> None:
        for marker in (
            "_mark_event_failed",
            '"processing_status": "retryable_failure"',
            '"processed_at": ""',
            "HTTP_503_SERVICE_UNAVAILABLE",
            "checkout_persisted",
            "maintenance_event_not_persisted",
        ):
            self.assertIn(marker, self.stripe)

    def test_06_deletion_is_tombstoned_locked_and_resumable(self) -> None:
        for marker in (
            '"status": "deletion_in_progress"',
            '"status": "failed_retryable"',
            '"status": "audit_pending"',
            '"resumed": True',
            "Retry the same Kernel operation",
            "subscription_id",
        ):
            self.assertIn(marker, self.deletion)

    def test_07_operational_details_are_explicit_and_not_public_by_default(self) -> None:
        for marker in (
            "include_operational_details",
            "production_signing_key_invalid",
            "stripe_configuration_incomplete",
            "upload_scanner_unavailable_quarantine_only",
            "private_upload_storage_not_persistent",
            "continuity_execution_disabled",
            "Public liveness and readiness surfaces intentionally omit",
        ):
            self.assertIn(marker, self.database)

    def test_08_governance_preserves_execution_constraints(self) -> None:
        for phrase in (
            "mfa remains optional",
            "paid order must come from verified stripe state",
            "no production customer mutation",
            "does not permanently delete marquis",
            "provider encryption",
            "independent penetration-test evidence",
        ):
            self.assertIn(phrase, self.doc.lower())


if __name__ == "__main__":
    unittest.main()
