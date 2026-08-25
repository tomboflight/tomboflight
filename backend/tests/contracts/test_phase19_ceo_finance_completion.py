from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


class TestPhase19CeoFinanceCompletion(unittest.TestCase):
    def test_every_catalog_addon_is_payment_bound(self):
        order_service = _read("backend/app/services/order_service.py")
        paid_addon = _read("backend/app/services/paid_addon_service.py")
        admin_service = _read("backend/app/services/admin_control_service.py")
        control = _read("admin-control-center.js")
        self.assertIn("get_addon_catalog", order_service)
        self.assertIn("validate_paid_addon_purchase_target", order_service)
        self.assertIn("activate_paid_addon_order", paid_addon)
        self.assertIn("sync_paid_addon_subscription_event", paid_addon)
        self.assertIn("Catalog add-ons cannot be granted or removed through service controls", admin_service)
        self.assertIn("Create Verified Add-On Checkout", control)
        self.assertIn("Activate Verified Paid Add-On", control)

    def test_refunds_credits_and_discounts_are_governed_ceo_actions(self):
        runtime = _read("backend/app/services/continuity_runtime_service.py")
        finance = _read("backend/app/services/finance_control_service.py")
        stripe = _read("backend/app/services/stripe_admin_operations_service.py")
        control = _read("admin-control-center.js")
        self.assertIn('"billing_adjustment"', runtime)
        self.assertIn("stripe_refund_is_irreversible_provider_evidence", runtime)
        self.assertIn("production_work_has_begun", finance)
        self.assertIn("refund_payment", stripe)
        self.assertIn("create_customer_credit", stripe)
        self.assertIn("apply_subscription_discount", stripe)
        self.assertIn("Issue Governed Refund", control)

    def test_payroll_writes_are_governed_and_never_claim_bank_transfer(self):
        runtime = _read("backend/app/services/continuity_runtime_service.py")
        finance = _read("backend/app/services/finance_control_service.py")
        control = _read("admin-control-center.js")
        self.assertIn('"payroll_control"', runtime)
        self.assertIn("external_payment_reference_required", finance)
        self.assertIn('"bank_transfer_initiated": False', finance)
        self.assertIn("Create Payroll Draft", control)
        self.assertIn("never initiates a bank transfer", control)

    def test_finance_exports_are_live_and_protected(self):
        routes = _read("backend/app/routes/admin_control_center.py")
        service = _read("backend/app/services/finance_control_service.py")
        control = _read("admin-control-center.js")
        self.assertIn('@router.get("/finance/reports/{report_type}/export")', routes)
        self.assertIn('require_permission("admin.control.billing")', routes)
        for report_type in (
            "monthly_finance_export",
            "tax_export",
            "refund_report",
            "subscription_report",
            "payroll_report",
            "package_performance_report",
        ):
            self.assertIn(report_type, service)
        self.assertIn("Protected Finance Exports", control)

    def test_phase19_control_center_asset_is_cache_busted(self):
        html = _read("admin-control-center.html")
        self.assertIn("admin-control-center.js?v=20260824-phase19", html)


if __name__ == "__main__":
    unittest.main()
