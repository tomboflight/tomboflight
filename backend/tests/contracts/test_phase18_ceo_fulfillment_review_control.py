from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


class TestPhase18CeoFulfillmentReviewControl(unittest.TestCase):
    def test_review_pages_use_secure_same_origin_preview_and_kernel_decisions(self):
        portrait = _read("admin-portrait-review.js")
        evidence = _read("admin-verification-review.js")
        for source in (portrait, evidence):
            self.assertIn("/admin-preview", source)
            self.assertIn("/admin/control-center/kernel/execute", source)
            self.assertIn("upload_rescan", source)
        self.assertIn('"portrait_review"', portrait)
        self.assertIn('"evidence_review"', evidence)

    def test_review_queue_deduplicates_shared_storage_records_without_hiding_distinct_uploads(self):
        routes = _read("backend/app/routes/uploads.py")
        self.assertIn("_deduplicate_admin_review_records", routes)
        self.assertIn('"duplicates_suppressed"', routes)
        self.assertIn('("storage_key", "relative_path", "stored_filename")', routes)

    def test_old_portraits_have_customer_attestation_recovery_without_admin_impersonation(self):
        routes = _read("backend/app/routes/uploads.py")
        customer = _read("portrait-upload.js")
        manager = _read("admin-family-manager.js")
        self.assertIn('@router.post("/{upload_id}/portrait-attestations")', routes)
        self.assertIn("cannot provide customer consent", routes)
        self.assertIn("data-attest-upload-id", customer)
        self.assertIn('body.append("authority_attested", "true")', manager)
        self.assertIn('body.append("consent_attested", "true")', manager)

    def test_existing_customer_first_project_package_grant_is_governed_and_non_payment(self):
        service = _read("backend/app/services/admin_control_service.py")
        runtime = _read("backend/app/services/continuity_runtime_service.py")
        control = _read("admin-control-center.js")
        self.assertIn("super_admin_provision_customer_package", service)
        self.assertIn('"payment_record_created": False', service)
        self.assertIn('"stripe_payment_mutated": False', service)
        self.assertIn('"customer_package_provision"', runtime)
        self.assertIn("Provision First Customer Project + Package", control)
        self.assertIn("does not create a payment record", control)

    def test_paid_nft_addons_remain_bound_to_authoritative_stripe_orders(self):
        service = _read("backend/app/services/admin_control_service.py")
        control = _read("admin-control-center.js")
        self.assertIn("Paid NFT add-ons cannot be granted or removed", service)
        self.assertIn("authoritative paid Stripe order", service)
        self.assertIn("Paid NFT boundary", control)

    def test_active_read_only_preview_can_return_to_its_exact_customer_case(self):
        control = _read("admin-control-center.js")
        self.assertIn("data-admin-open-impersonated-case", control)
        self.assertIn("Different Customer Preview Active", control)
        self.assertIn("The preview remains read-only", control)

    def test_phase18_assets_are_cache_busted(self):
        expected = {
            "admin-control-center.html": "admin-control-center.js",
            "admin-family-manager.html": "admin-family-manager.js",
            "admin-portrait-review.html": "admin-portrait-review.js",
            "admin-verification-review.html": "admin-verification-review.js",
            "portrait-upload.html": "portrait-upload.js",
        }
        for html_path, asset in expected.items():
            with self.subTest(html_path=html_path):
                self.assertIn(f'{asset}?v=20260824-phase18', _read(html_path))


if __name__ == "__main__":
    unittest.main()
