from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


class TestPhase191ProductionTruthCorrections(unittest.TestCase):
    def test_non_payment_grants_are_distinct_from_stripe_backed_sales(self):
        service = _read("backend/app/services/admin_control_service.py")
        self.assertIn("def _project_payment_required", service)
        self.assertIn('"acquisition_satisfied": acquisition_satisfied', service)
        self.assertIn('if not mint_already_completed and not acquisition_satisfied:', service)
        self.assertIn("and _project_payment_required(project)", service)
        self.assertIn("Legacy projects predate the field", service)

    def test_existing_customer_email_is_routed_to_existing_account_provisioning(self):
        service = _read("backend/app/services/admin_control_service.py")
        self.assertIn("A customer account already exists for this email", service)
        self.assertIn("Provision First Customer Project + Package", service)
        self.assertIn("except DuplicateKeyError as exc", service)

    def test_review_previews_explain_fail_closed_blockers(self):
        routes = _read("backend/app/routes/uploads.py")
        portrait = _read("admin-portrait-review.js")
        evidence = _read("admin-verification-review.js")
        self.assertIn('"preview_available": not preview_blockers', routes)
        self.assertIn('or scan_status != "clean"', routes)
        self.assertIn("Preview Blocked", portrait)
        self.assertIn("Preview Blocked", evidence)
        self.assertIn("Private storage migration must complete before preview", portrait)
        self.assertIn("Private storage migration must complete before preview", evidence)

    def test_duplicate_candidates_are_visible_without_collapsing_distinct_records(self):
        routes = _read("backend/app/routes/uploads.py")
        self.assertIn("def _admin_review_semantic_identity", routes)
        self.assertIn('"possible_duplicate_count"', routes)
        self.assertIn("without suppressing distinct uploads", routes)

    def test_control_center_release_identity_matches_cache_busted_asset(self):
        service = _read("backend/app/services/admin_control_service.py")
        html = _read("admin-control-center.html")
        portrait_html = _read("admin-portrait-review.html")
        evidence_html = _read("admin-verification-review.html")
        self.assertIn('FRONTEND_ASSET_REVISION = "20260828-phase21-1"', service)
        self.assertIn("admin-control-center.js?v=20260824-phase19-1", html)
        self.assertIn("admin-portrait-review.js?v=20260824-phase19-1", portrait_html)
        self.assertIn("admin-verification-review.js?v=20260824-phase19-1", evidence_html)


if __name__ == "__main__":
    unittest.main()
