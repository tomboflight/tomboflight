from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_PATH = REPO_ROOT / "backend" / "app" / "services" / "continuity_runtime_service.py"
AUDIT_PATH = REPO_ROOT / "backend" / "app" / "services" / "audit_log_service.py"
AUTH_PATH = REPO_ROOT / "backend" / "app" / "services" / "auth_service.py"
ACCOUNT_SECURITY_JS_PATH = REPO_ROOT / "account-security.js"
POSTER_PATH = REPO_ROOT / "backend" / "app" / "services" / "poster_asset_service.py"
RATE_LIMIT_PATH = REPO_ROOT / "backend" / "app" / "services" / "rate_limit_service.py"
GUARD_PATH = REPO_ROOT / "backend" / "app" / "core" / "continuity_route_guard.py"
MAIN_PATH = REPO_ROOT / "backend" / "app" / "main.py"
CONTROL_SERVICE_PATH = REPO_ROOT / "backend" / "app" / "services" / "admin_control_service.py"
CONTROL_ROUTE_PATH = REPO_ROOT / "backend" / "app" / "routes" / "admin_control_center.py"
CONTROL_HTML_PATH = REPO_ROOT / "admin-control-center.html"
CONTROL_JS_PATH = REPO_ROOT / "admin-control-center.js"
DOC_PATH = REPO_ROOT / "backend" / "docs" / "governance" / "continuity_kernel_phase12_production_security_closure.md"


class TestContinuityKernelPhase12ProductionSecurityClosure(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime = RUNTIME_PATH.read_text(encoding="utf-8")
        cls.audit = AUDIT_PATH.read_text(encoding="utf-8")
        cls.auth = AUTH_PATH.read_text(encoding="utf-8")
        cls.account_security_js = ACCOUNT_SECURITY_JS_PATH.read_text(encoding="utf-8")
        cls.poster = POSTER_PATH.read_text(encoding="utf-8")
        cls.rate_limit = RATE_LIMIT_PATH.read_text(encoding="utf-8")
        cls.guard = GUARD_PATH.read_text(encoding="utf-8")
        cls.main = MAIN_PATH.read_text(encoding="utf-8")
        cls.control_service = CONTROL_SERVICE_PATH.read_text(encoding="utf-8")
        cls.control_route = CONTROL_ROUTE_PATH.read_text(encoding="utf-8")
        cls.control_html = CONTROL_HTML_PATH.read_text(encoding="utf-8")
        cls.control_js = CONTROL_JS_PATH.read_text(encoding="utf-8")
        cls.doc = DOC_PATH.read_text(encoding="utf-8")

    def test_01_runtime_registers_truthful_orphan_reconciliation(self) -> None:
        self.assertIn('RUNTIME_VERSION = "12.0.0"', self.runtime)
        self.assertIn('"orphan_identity_reconciliation": ActionSpec(', self.runtime)
        for marker in (
            'ORPHAN_RECONCILIATION_CONFIRMATION_PHRASE = "RECONCILE MANUAL REMOVAL"',
            '"evidence_type": "post_hoc_manual_identity_reconciliation"',
            '"deletion_origin": "manual_external_to_kernel"',
            '"governed_deletion_observed": False',
            '"reconciliation_receipt"',
        ):
            self.assertIn(marker, self.control_service)
        self.assertNotIn('"deletion_receipt"', self.control_service.split(
            "def super_admin_apply_orphan_identity_reconciliation", 1
        )[1].split("def super_admin_transfer_project_ownership", 1)[0])

    def test_02_reconciliation_is_ceo_only_previewed_and_explicitly_confirmed(self) -> None:
        for marker in (
            "super_admin_preview_orphan_identity_reconciliation",
            "_assert_canonical_ceo",
            "data-admin-orphan-reconciliation-dialog",
            "data-admin-orphan-preview-action",
            "data-admin-orphan-execute",
            "RECONCILE MANUAL REMOVAL",
            "window.confirm",
        ):
            self.assertIn(
                marker,
                self.control_route + self.control_service + self.control_html + self.control_js,
            )

    def test_03_authentication_tokens_are_version_bound_atomic_and_fragment_only(self) -> None:
        for marker in (
            "def _assert_mfa_token_version",
            '"mfa_backup_code_hashes": target_hash',
            '"$pull": {"mfa_backup_code_hashes": target_hash}',
            '"password_reset_token_hash": token_hash',
            "matched_count",
            "#mode=reset&token=",
        ):
            self.assertIn(marker, self.auth)
        self.assertIn("window.location.hash", self.account_security_js)
        self.assertIn("window.history.replaceState", self.account_security_js)

    def test_04_poster_upload_selection_requires_clean_approval_and_consent(self) -> None:
        for marker in (
            '"scan_status": "clean"',
            '"quarantined": {"$ne": True}',
            '"approved_for_cinematic": True',
            '"verification_status": "approved"',
            '"consent_status": "approved"',
        ):
            self.assertIn(marker, self.poster)

    def test_05_broad_admin_access_is_removed_from_live_routes(self) -> None:
        offenders = []
        for path in sorted((REPO_ROOT / "backend" / "app" / "routes").glob("*.py")):
            source = path.read_text(encoding="utf-8")
            if 'require_permission("admin.access")' in source:
                offenders.append(path.name)
        self.assertEqual(offenders, [])

    def test_06_legacy_privileged_production_writes_fail_into_kernel(self) -> None:
        for marker in (
            "PRODUCTION_LEGACY_PRIVILEGED_MUTATION_PATTERNS",
            "settings.is_production_environment",
            "continuity_kernel_required",
            "KERNEL_EXECUTION_PATH",
        ):
            self.assertIn(marker, self.guard + self.main)

    def test_07_production_rate_limits_are_shared_and_principals_are_hashed(self) -> None:
        for marker in (
            'RATE_LIMIT_COLLECTION = "auth_rate_limit_state"',
            "hashlib.sha256",
            "find_one_and_update",
            "ReturnDocument.AFTER",
            "expireAfterSeconds=0",
            "settings.is_production_environment",
        ):
            self.assertIn(marker, self.rate_limit)

    def test_08_critical_startup_controls_fail_closed(self) -> None:
        self.assertIn("if unique:\n                raise", (
            REPO_ROOT / "backend" / "app" / "services" / "order_service.py"
        ).read_text(encoding="utf-8"))
        self.assertIn("if unique:\n                raise", (
            REPO_ROOT / "backend" / "app" / "services" / "public_manifest_service.py"
        ).read_text(encoding="utf-8"))
        self.assertIn("if settings.is_production_environment", self.main)
        self.assertIn("Admin access bootstrap failed closed", self.main)

    def test_09_kernel_evidence_is_idempotent_checkpointed_and_resumable(self) -> None:
        for marker in (
            "def _record_stage_evidence",
            "event_identity",
            "request_evidence_status",
            "approval_evidence_status",
            "scheduling_evidence_status",
            "closure_evidence_status",
            "resume evidence recording",
        ):
            self.assertIn(marker, self.runtime)
        for marker in (
            "audit_idempotency_key",
            "hashlib.sha256",
            "DuplicateKeyError",
        ):
            self.assertIn(marker, self.audit)

    def test_10_governance_discloses_post_hoc_and_static_edge_boundaries(self) -> None:
        for phrase in (
            "does not claim that an earlier manual mongodb deletion was governed",
            "reconciliation receipt rather than a deletion receipt",
            "does not misrepresent it as closed",
            "action-time confirmation",
            "no production customer mutation",
        ):
            self.assertIn(phrase, self.doc.lower())


if __name__ == "__main__":
    unittest.main()
