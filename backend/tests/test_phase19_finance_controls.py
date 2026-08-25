from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bson import ObjectId

from app.services import admin_control_service
from app.services import finance_control_service as finance
from app.services import maintenance_subscription_service as maintenance
from app.services import paid_addon_service as paid_addon
from app.services import stripe_admin_operations_service as stripe_ops


def _value(document, dotted_key):
    value = document
    for part in dotted_key.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _matches(document, query):
    for key, expected in (query or {}).items():
        if key == "$or":
            if not any(_matches(document, item) for item in expected):
                return False
            continue
        actual = _value(document, key)
        if isinstance(expected, dict):
            if "$in" in expected and actual not in expected["$in"]:
                return False
            if "$ne" in expected and actual == expected["$ne"]:
                return False
            if "$gte" in expected and (actual is None or actual < expected["$gte"]):
                return False
            if "$lte" in expected and (actual is None or actual > expected["$lte"]):
                return False
            continue
        if actual != expected:
            return False
    return True


class _Cursor:
    def __init__(self, documents):
        self.documents = [deepcopy(item) for item in documents]

    def sort(self, key, direction):
        self.documents.sort(key=lambda item: str(_value(item, key) or ""), reverse=direction < 0)
        return self

    def limit(self, limit):
        self.documents = self.documents[:limit]
        return self

    def __iter__(self):
        return iter(deepcopy(self.documents))


class _Collection:
    def __init__(self, documents=None):
        self.documents = [deepcopy(item) for item in (documents or [])]

    def find_one(self, query, *args, **kwargs):
        del args, kwargs
        for item in self.documents:
            if _matches(item, query):
                return deepcopy(item)
        return None

    def find(self, query, *args, **kwargs):
        del args, kwargs
        return _Cursor([item for item in self.documents if _matches(item, query)])

    def insert_one(self, document):
        stored = deepcopy(document)
        stored.setdefault("_id", ObjectId())
        self.documents.append(stored)
        return SimpleNamespace(inserted_id=stored["_id"])

    def update_one(self, query, update):
        for item in self.documents:
            if not _matches(item, query):
                continue
            item.update(deepcopy((update or {}).get("$set") or {}))
            return SimpleNamespace(matched_count=1, modified_count=1)
        return SimpleNamespace(matched_count=0, modified_count=0)

    def update_many(self, query, update):
        modified = 0
        for item in self.documents:
            if not _matches(item, query):
                continue
            item.update(deepcopy((update or {}).get("$set") or {}))
            modified += 1
        return SimpleNamespace(matched_count=modified, modified_count=modified)


class _Database(dict):
    def __getitem__(self, key):
        if key not in self:
            self[key] = _Collection()
        return super().__getitem__(key)


ACTOR = {
    "_id": "ceo-1",
    "email": "l.robinson@tomboflight.com",
    "full_name": "Larry Robinson",
}


class TestPhase19FinanceControls(unittest.TestCase):
    def setUp(self):
        self.user_id = ObjectId()
        self.project_id = ObjectId()
        self.order_id = ObjectId()
        self.entitlement_id = ObjectId()
        self.database = _Database(
            {
                "users": _Collection(
                    [{"_id": self.user_id, "email": "customer@example.com", "stripe_customer_id": "cus_1"}]
                ),
                "projects": _Collection(
                    [
                        {
                            "_id": self.project_id,
                            "owner_user_id": self.user_id,
                            "owner_email": "customer@example.com",
                            "package_code": "digital_legacy_portrait",
                            "status": "intake_pending",
                            "phase": "intake_pending",
                        }
                    ]
                ),
                "project_members": _Collection(),
                "project_entitlements": _Collection(
                    [
                        {
                            "_id": self.entitlement_id,
                            "project_id": self.project_id,
                            "user_id": self.user_id,
                            "package_code": "digital_legacy_portrait",
                            "status": "active",
                            "active_addons": [],
                        }
                    ]
                ),
                "orders": _Collection(
                    [
                        {
                            "_id": self.order_id,
                            "user_id": self.user_id,
                            "email": "customer@example.com",
                            "project_id": self.project_id,
                            "package_code": "legacy_plus",
                            "item_type": "package",
                            "source": "stripe_webhook",
                            "status": "paid",
                            "stripe_payment_intent_id": "pi_1",
                            "amount_total_cents": 320000,
                            "created_at": datetime.now(UTC),
                        }
                    ]
                ),
                "payroll_runs": _Collection(),
                "finance_events": _Collection(),
                "audit_logs": _Collection(),
            }
        )

    def test_refund_preview_blocks_after_production_begins(self):
        self.database["projects"].documents[0].update({"status": "in_production", "phase": "build_started"})
        with patch.object(finance, "get_database", return_value=self.database):
            preview = finance.preview_billing_adjustment(
                order_id=str(self.order_id),
                payload={"billing_action": "refund", "amount_cents": 0},
            )
        self.assertTrue(preview["blocked"])
        self.assertIn("production_work_has_begun", preview["blocked_reasons"])

    def test_refund_preview_is_open_before_production(self):
        with patch.object(finance, "get_database", return_value=self.database):
            preview = finance.preview_billing_adjustment(
                order_id=str(self.order_id),
                payload={"billing_action": "refund", "amount_cents": 10000},
            )
        self.assertFalse(preview["blocked"])

    def test_billing_adjustments_reject_non_authoritative_payment_sources(self):
        self.database["orders"].documents[0]["source"] = "admin_manual"
        with patch.object(finance, "get_database", return_value=self.database):
            preview = finance.preview_billing_adjustment(
                order_id=str(self.order_id),
                payload={"billing_action": "refund", "amount_cents": 0},
            )
        self.assertTrue(preview["blocked"])
        self.assertIn("order_payment_source_not_authoritative", preview["blocked_reasons"])

    def test_admin_finance_amounts_read_authoritative_cent_fields_as_dollars(self):
        self.assertEqual(
            admin_control_service._order_amount_value({"amount_total_cents": 5000}),
            50.0,
        )
        self.assertTrue(
            admin_control_service._is_authoritative_paid_order(
                {"item_type": "addon", "status": "paid", "source": "stripe_webhook"}
            )
        )
        self.assertFalse(
            admin_control_service._is_authoritative_paid_order(
                {"item_type": "package", "status": "paid", "source": "admin_manual"}
            )
        )

    def test_succeeded_full_refund_revokes_package_access(self):
        with (
            patch.object(finance, "get_database", return_value=self.database),
            patch.object(finance, "write_audit_log", return_value="audit-1"),
            patch.object(
                finance.stripe_admin_operations_service,
                "refund_payment",
                return_value={
                    "refund_id": "re_full",
                    "amount": 320000,
                    "currency": "usd",
                    "status": "succeeded",
                },
            ),
        ):
            result = finance.apply_billing_adjustment(
                order_id=str(self.order_id),
                payload={
                    "billing_action": "refund",
                    "amount_cents": 0,
                    "reason": "Verified refund before production",
                    "confirmed": True,
                },
                actor=ACTOR,
            )
        order = self.database["orders"].find_one({"_id": self.order_id})
        entitlement = self.database["project_entitlements"].find_one({"_id": self.entitlement_id})
        project = self.database["projects"].find_one({"_id": self.project_id})
        self.assertEqual(order["status"], "refunded")
        self.assertEqual(entitlement["status"], "revoked")
        self.assertFalse(entitlement["access_enabled"])
        self.assertEqual(project["status"], "payment_refunded")
        self.assertTrue(result["access_result"]["revoked"])

    def test_partial_refund_preserves_access(self):
        with (
            patch.object(finance, "get_database", return_value=self.database),
            patch.object(finance, "write_audit_log", return_value="audit-1"),
            patch.object(
                finance.stripe_admin_operations_service,
                "refund_payment",
                return_value={
                    "refund_id": "re_partial",
                    "amount": 10000,
                    "currency": "usd",
                    "status": "succeeded",
                },
            ),
        ):
            result = finance.apply_billing_adjustment(
                order_id=str(self.order_id),
                payload={
                    "billing_action": "refund",
                    "amount_cents": 10000,
                    "reason": "Verified partial refund before production",
                    "confirmed": True,
                },
                actor=ACTOR,
            )
        order = self.database["orders"].find_one({"_id": self.order_id})
        entitlement = self.database["project_entitlements"].find_one({"_id": self.entitlement_id})
        self.assertEqual(order["status"], "partially_refunded")
        self.assertEqual(entitlement["status"], "active")
        self.assertFalse(result["access_result"]["revoked"])

    def test_customer_credit_records_non_cash_event_without_revoking_access(self):
        with (
            patch.object(finance, "get_database", return_value=self.database),
            patch.object(finance, "write_audit_log", return_value="audit-1"),
            patch.object(
                finance.stripe_admin_operations_service,
                "create_customer_credit",
                return_value={
                    "balance_transaction_id": "cbtxn_1",
                    "amount": 5000,
                    "currency": "usd",
                    "type": "customer_balance_credit",
                },
            ),
        ):
            result = finance.apply_billing_adjustment(
                order_id=str(self.order_id),
                payload={
                    "billing_action": "customer_credit",
                    "amount_cents": 5000,
                    "description": "Service recovery credit",
                    "reason": "CEO approved service recovery credit",
                    "confirmed": True,
                },
                actor=ACTOR,
            )
        entitlement = self.database["project_entitlements"].find_one({"_id": self.entitlement_id})
        events = list(self.database["finance_events"].find({"event_type": "credit_recorded"}))
        self.assertEqual(entitlement["status"], "active")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["amount_cents"], 5000)
        self.assertFalse(result["access_result"]["revoked"])

    def test_paid_addon_activation_requires_order_and_updates_entitlement(self):
        addon_order_id = ObjectId()
        addon_order = {
            "_id": addon_order_id,
            "user_id": self.user_id,
            "email": "customer@example.com",
            "project_id": self.project_id,
            "package_code": "legacy_plus",
            "addon_code": "extra_storage",
            "purchase_code": "extra_storage",
            "item_type": "addon",
            "source": "stripe_webhook",
            "status": "paid",
            "payment_verified_at": datetime.now(UTC),
            "stripe_session_id": "cs_addon",
            "stripe_payment_intent_id": "pi_addon",
        }
        self.database["orders"].documents.append(deepcopy(addon_order))
        with (
            patch.object(paid_addon, "get_database", return_value=self.database),
            patch.object(paid_addon, "write_audit_log", return_value="audit-1"),
        ):
            result = paid_addon.activate_paid_addon_order(
                order=addon_order,
                actor=ACTOR,
                reason="Verified paid storage purchase",
                idempotency_key="addon-activation-1",
            )
        self.assertTrue(result["activated"])
        entitlement = self.database["project_entitlements"].find_one({"_id": self.entitlement_id})
        self.assertIn("extra_storage", entitlement["active_addons"])
        self.assertEqual(entitlement["paid_addon_sources"][0]["order_id"], str(addon_order_id))

    def test_paid_addon_activation_rejects_manual_payment_sources(self):
        addon_order = {
            "_id": ObjectId(),
            "user_id": self.user_id,
            "email": "customer@example.com",
            "project_id": self.project_id,
            "addon_code": "extra_storage",
            "item_type": "addon",
            "source": "admin_manual",
            "status": "paid",
            "payment_verified_at": datetime.now(UTC),
        }
        with patch.object(paid_addon, "get_database", return_value=self.database):
            with self.assertRaisesRegex(ValueError, "not authoritative"):
                paid_addon.activate_paid_addon_order(
                    order=addon_order,
                    actor=ACTOR,
                    reason="Manual source must be rejected",
                    idempotency_key="addon-manual-source",
                )

    def test_manual_service_controls_cannot_toggle_catalog_addons(self):
        before = {
            "project": {"package_code": "legacy_plus"},
            "order": {},
            "entitlement": {"active_addons": []},
            "service_controls": {"active_addons": []},
        }
        with self.assertRaisesRegex(ValueError, "authoritative paid Stripe order"):
            admin_control_service._apply_service_control_payload_to_preview(
                before=before,
                payload={"add_addons": ["extra_storage"]},
            )

    def test_payroll_ledger_requires_review_approval_and_external_reference(self):
        with (
            patch.object(finance, "get_database", return_value=self.database),
            patch.object(finance, "write_audit_log", return_value="audit-1"),
        ):
            created = finance.apply_payroll_control(
                payroll_run_id="payroll-2026-08",
                payload={
                    "payroll_action": "create_draft",
                    "period_start": "2026-08-01",
                    "period_end": "2026-08-31",
                    "total_amount_cents": 125000,
                    "reason": "Create August payroll ledger",
                    "confirmed": True,
                },
                actor=ACTOR,
            )
            self.assertEqual(created["payroll_run"]["status"], "draft")
            finance.apply_payroll_control(
                payroll_run_id="payroll-2026-08",
                payload={"payroll_action": "submit_for_review", "reason": "Ready for review", "confirmed": True},
                actor=ACTOR,
            )
            finance.apply_payroll_control(
                payroll_run_id="payroll-2026-08",
                payload={"payroll_action": "approve", "reason": "CEO approval", "confirmed": True},
                actor=ACTOR,
            )
            with self.assertRaisesRegex(ValueError, "external_payment_reference_required"):
                finance.apply_payroll_control(
                    payroll_run_id="payroll-2026-08",
                    payload={"payroll_action": "mark_processed", "reason": "Record processing", "confirmed": True},
                    actor=ACTOR,
                )
            processed = finance.apply_payroll_control(
                payroll_run_id="payroll-2026-08",
                payload={
                    "payroll_action": "mark_processed",
                    "external_reference": "provider-batch-77",
                    "reason": "Record external processing",
                    "confirmed": True,
                },
                actor=ACTOR,
            )
        self.assertEqual(processed["payroll_run"]["status"], "processed")
        self.assertFalse(processed["bank_transfer_initiated"])

    def test_finance_exports_distinguish_addon_revenue_and_tax_review_status(self):
        self.database["orders"].documents.append(
            {
                "_id": ObjectId(),
                "email": "customer@example.com",
                "project_id": self.project_id,
                "package_code": "digital_legacy_portrait",
                "addon_code": "extra_storage",
                "item_type": "addon",
                "source": "stripe_webhook",
                "status": "paid",
                "amount_total_cents": 5000,
                "created_at": datetime.now(UTC),
            }
        )
        self.database["finance_events"].documents.append(
            {
                "_id": ObjectId(),
                "event_type": "payment_captured",
                "amount": 3200.0,
                "occurred_at": datetime(2026, 8, 31, 18, 30, tzinfo=UTC),
            }
        )
        self.database["finance_events"].documents.append(
            {
                "_id": ObjectId(),
                "event_type": "payment_captured",
                "amount": 99.0,
                "occurred_at": datetime(2026, 9, 1, 0, 0, tzinfo=UTC),
            }
        )
        self.database["payroll_runs"].documents.append(
            {
                "_id": ObjectId(),
                "payroll_run_id": "payroll-export-august",
                "period_end": "2026-08-31",
                "status": "processed",
                "total_amount": 1250.0,
            }
        )
        with (
            patch.object(finance, "get_database", return_value=self.database),
            patch.object(finance, "write_audit_log", return_value="audit-export") as audit_export,
        ):
            performance = finance.generate_finance_export(report_type="package_performance_report")
            tax = finance.generate_finance_export(
                report_type="tax_export",
                period_start="2026-08-01",
                period_end="2026-08-31",
                actor=ACTOR,
            )
            payroll = finance.generate_finance_export(
                report_type="payroll_report",
                period_start="2026-08-01",
                period_end="2026-08-31",
            )
        buckets = {item["product_code"]: item for item in performance["records"]}
        self.assertIn("extra_storage", buckets)
        self.assertEqual(buckets["extra_storage"]["gross_revenue"], 50.0)
        self.assertFalse(tax["summary"]["filing_ready"])
        self.assertIn("tax professional", tax["summary"]["notice"])
        self.assertEqual(tax["summary"]["record_count"], 1)
        self.assertEqual(payroll["summary"]["record_count"], 1)
        self.assertEqual(audit_export.call_args.kwargs["action"], "finance_export.generated")

    def test_addon_checkout_binds_exact_catalog_price_to_project_metadata(self):
        project = self.database["projects"].documents[0]
        user = self.database["users"].documents[0]
        with (
            patch.object(stripe_ops, "get_database", return_value=self.database),
            patch.object(stripe_ops, "validate_paid_addon_purchase_target", return_value=project),
            patch.object(stripe_ops, "_require_stripe_secret_key"),
            patch.object(stripe_ops, "_ensure_stripe_customer_for_user", return_value={"id": "cus_1"}),
            patch.object(
                stripe_ops.stripe.Price,
                "retrieve",
                return_value={
                    "id": "price_extra_storage",
                    "currency": "usd",
                    "unit_amount": 5000,
                    "product": {
                        "name": "Extra Storage",
                        "metadata": {"addon_code": "extra_storage"},
                    },
                },
            ),
            patch.object(
                stripe_ops.stripe.checkout.Session,
                "create",
                return_value={
                    "id": "cs_extra_storage",
                    "url": "https://checkout.stripe.com/c/pay/cs_extra_storage",
                },
            ) as create_session,
            patch.object(stripe_ops, "_audit"),
        ):
            result = stripe_ops.create_paid_addon_checkout(
                ACTOR,
                customer_email=user["email"],
                project_id=str(self.project_id),
                addon_code="extra_storage",
                price_id="price_extra_storage",
                reason="Verified customer add-on checkout",
                idempotency_key="checkout-extra-storage-1",
            )
        parameters = create_session.call_args.kwargs
        self.assertEqual(parameters["metadata"]["project_id"], str(self.project_id))
        self.assertEqual(parameters["metadata"]["addon_code"], "extra_storage")
        self.assertEqual(parameters["line_items"], [{"price": "price_extra_storage", "quantity": 1}])
        self.assertEqual(result["payment_activation"], "stripe_webhook_then_manual_fulfillment")

    def test_recurring_addon_checkout_is_not_misclassified_as_maintenance(self):
        result = maintenance.sync_maintenance_checkout_event(
            {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_addon_subscription",
                        "mode": "subscription",
                        "subscription": "sub_addon",
                        "metadata": {
                            "item_type": "addon",
                            "project_id": str(self.project_id),
                            "addon_code": "extra_storage",
                        },
                    }
                },
            }
        )
        self.assertFalse(result["updated"])
        self.assertEqual(result["reason"], "paid_addon_checkout_not_maintenance")

    def test_canceled_recurring_addon_subscription_revokes_entitlement(self):
        addon_order_id = ObjectId()
        self.database["orders"].documents.append(
            {
                "_id": addon_order_id,
                "user_id": self.user_id,
                "email": "customer@example.com",
                "project_id": self.project_id,
                "addon_code": "extra_storage",
                "purchase_code": "extra_storage",
                "item_type": "addon",
                "source": "stripe_webhook",
                "status": "paid",
                "stripe_subscription_id": "sub_addon_fixture",
                "addon_entitlement_status": "active",
            }
        )
        entitlement = self.database["project_entitlements"].documents[0]
        entitlement["active_addons"] = ["extra_storage"]
        entitlement["paid_addon_sources"] = [
            {"order_id": str(addon_order_id), "addon_code": "extra_storage"}
        ]
        event = {
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_addon_fixture",
                    "status": "canceled",
                    "metadata": {
                        "item_type": "addon",
                        "project_id": str(self.project_id),
                        "addon_code": "extra_storage",
                    },
                }
            },
        }
        with (
            patch.object(paid_addon, "get_database", return_value=self.database),
            patch.object(paid_addon, "write_audit_log", return_value="audit-1"),
        ):
            result = maintenance.sync_maintenance_subscription_event(event)
        stored_entitlement = self.database["project_entitlements"].find_one({"_id": self.entitlement_id})
        stored_order = self.database["orders"].find_one({"_id": addon_order_id})
        self.assertTrue(result["updated"])
        self.assertTrue(result["access_result"]["revoked"])
        self.assertNotIn("extra_storage", stored_entitlement["active_addons"])
        self.assertEqual(stored_order["addon_subscription_status"], "canceled")
        self.assertEqual(stored_order["addon_entitlement_status"], "revoked")

    def test_current_stripe_invoice_parent_shape_updates_recurring_addon(self):
        addon_order_id = ObjectId()
        self.database["orders"].documents.append(
            {
                "_id": addon_order_id,
                "project_id": self.project_id,
                "addon_code": "extra_storage",
                "item_type": "addon",
                "source": "stripe_webhook",
                "status": "paid",
                "stripe_subscription_id": "sub_parent_shape",
                "payment_verified_at": datetime.now(UTC),
                "fulfillment_status": "fulfillment_complete",
                "addon_entitlement_status": "revoked",
            }
        )
        event = {
            "type": "invoice.paid",
            "data": {
                "object": {
                    "id": "in_parent_shape",
                    "status": "paid",
                    "billing_reason": "subscription_cycle",
                    "currency": "usd",
                    "amount_paid": 5000,
                    "payments": {
                        "data": [
                            {
                                "payment": {
                                    "type": "payment_intent",
                                    "payment_intent": "pi_parent_shape",
                                }
                            }
                        ]
                    },
                    "parent": {
                        "subscription_details": {
                            "subscription": "sub_parent_shape",
                            "metadata": {
                                "item_type": "addon",
                                "addon_code": "extra_storage",
                                "project_id": str(self.project_id),
                            },
                        }
                    },
                }
            },
        }
        with (
            patch.object(paid_addon, "get_database", return_value=self.database),
            patch.object(paid_addon, "write_audit_log", return_value="audit-1"),
        ):
            result = maintenance.sync_maintenance_invoice_event(event)
        stored_order = self.database["orders"].find_one({"_id": addon_order_id})
        stored_entitlement = self.database["project_entitlements"].find_one({"_id": self.entitlement_id})
        recurring_events = list(
            self.database["finance_events"].find({"stripe_invoice_id": "in_parent_shape"})
        )
        self.assertTrue(result["updated"])
        self.assertEqual(result["type"], "paid_addon_subscription")
        self.assertEqual(stored_order["addon_subscription_status"], "active")
        self.assertEqual(stored_order["addon_subscription_invoice_id"], "in_parent_shape")
        self.assertEqual(stored_order["stripe_payment_intent_id"], "pi_parent_shape")
        self.assertIn("extra_storage", stored_entitlement["active_addons"])
        self.assertEqual(len(recurring_events), 1)
        self.assertEqual(recurring_events[0]["amount_cents"], 5000)


if __name__ == "__main__":
    unittest.main()
