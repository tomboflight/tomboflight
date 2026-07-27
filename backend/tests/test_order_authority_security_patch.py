import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError

from app.dependencies import auth as auth_dependencies
from app.dependencies.auth import require_any_permission
from app.schemas.order import AdminManualOrderCreate, PublicCheckoutOrderCreate
from app.services import order_service


class _InsertResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class FakeOrdersCollection:
    def __init__(self, seed=None):
        self.docs = [dict(item) for item in (seed or [])]
        self._next = 1

    def _match(self, query, item):
        for key, expected in (query or {}).items():
            if item.get(key) != expected:
                return False
        return True

    def find_one(self, query, sort=None):  # noqa: ARG002
        for item in self.docs:
            if self._match(query, item):
                return dict(item)
        return None

    def insert_one(self, document):
        payload = dict(document)
        payload.setdefault("_id", f"order-{self._next}")
        self._next += 1
        self.docs.append(payload)
        return _InsertResult(payload["_id"])

    def update_one(self, query, update):
        for index, item in enumerate(self.docs):
            if self._match(query, item):
                updated = dict(item)
                updated.update((update or {}).get("$set") or {})
                self.docs[index] = updated
                return

    def index_information(self):
        return {}

    def create_index(self, *args, **kwargs):  # noqa: ARG002
        return None


def _paid_checkout_session(
    *,
    session_id="cs_test_paid_1",
    email="customer@example.com",
    package_code="legacy_plus",
    product_name="Legacy Plus",
    unit_amount=320000,
    currency="usd",
    payment_status="paid",
    status="complete",
):
    return {
        "id": session_id,
        "object": "checkout.session",
        "status": status,
        "payment_status": payment_status,
        "amount_total": unit_amount,
        "currency": currency,
        "customer_email": email,
        "customer_details": {"email": email, "name": "Customer One"},
        "metadata": {"package_code": package_code, "user_id": "507f1f77bcf86cd799439012"},
        "line_items": {
            "data": [
                {
                    "description": product_name,
                    "price": {
                        "id": "price_tol_legacy_plus",
                        "currency": currency,
                        "unit_amount": unit_amount,
                        "product": {
                            "id": "prod_tol_legacy_plus",
                            "name": product_name,
                            "metadata": {"package_code": package_code},
                        },
                    },
                }
            ]
        },
    }


class OrderAuthoritySecurityTests(unittest.TestCase):
    def setUp(self):
        self.user = {
            "_id": "507f1f77bcf86cd799439012",
            "email": "customer@example.com",
            "stripe_customer_id": "cus_123",
        }

    def test_public_schema_rejects_source_admin_manual(self):
        with self.assertRaises(ValidationError):
            PublicCheckoutOrderCreate(package_code="legacy_plus", source="admin_manual")

    def test_public_schema_rejects_paid_order_status(self):
        with self.assertRaises(ValidationError):
            PublicCheckoutOrderCreate(package_code="legacy_plus", order_status="paid")

    def test_public_schema_rejects_browser_package_name_and_price(self):
        with self.assertRaises(ValidationError):
            PublicCheckoutOrderCreate(
                package_code="legacy_plus",
                package_name="Forged Name",
                price_label="$1.00",
            )

    def test_invalid_unpaid_session_creates_no_paid_order_project_entitlement_or_maintenance(self):
        orders = FakeOrdersCollection()
        payload = SimpleNamespace(package_code="legacy_plus", stripe_session_id="cs_test_unpaid")
        unpaid_session = _paid_checkout_session(payment_status="unpaid")
        with (
            patch.object(order_service, "_get_orders_collection", return_value=orders),
            patch.object(order_service, "_retrieve_checkout_session", return_value=unpaid_session),
            patch.object(order_service, "_attach_project_to_paid_package_order") as attach_mock,
            patch.object(order_service, "apply_package_purchase_to_project") as apply_mock,
            patch.object(order_service, "_schedule_maintenance_start") as maintenance_mock,
        ):
            with self.assertRaises(ValueError):
                order_service.create_order_for_user(self.user, payload)
        self.assertEqual(len([d for d in orders.docs if d.get("status") == "paid"]), 0)
        attach_mock.assert_not_called()
        apply_mock.assert_not_called()
        maintenance_mock.assert_not_called()

    def test_unpaid_stripe_session_cannot_provision(self):
        orders = FakeOrdersCollection()
        payload = SimpleNamespace(package_code="legacy_plus", stripe_session_id="cs_test_unpaid")
        unpaid_session = _paid_checkout_session(payment_status="unpaid")
        with (
            patch.object(order_service, "_get_orders_collection", return_value=orders),
            patch.object(order_service, "_retrieve_checkout_session", return_value=unpaid_session),
            patch.object(order_service, "_attach_project_to_paid_package_order") as attach_mock,
        ):
            with self.assertRaises(ValueError):
                order_service.create_order_for_user(self.user, payload)
        attach_mock.assert_not_called()

    def test_invalid_request_creates_no_project(self):
        orders = FakeOrdersCollection()
        payload = SimpleNamespace(package_code="legacy_plus", stripe_session_id="cs_test_no_project")
        unpaid_session = _paid_checkout_session(payment_status="unpaid", session_id="cs_test_no_project")
        with (
            patch.object(order_service, "_get_orders_collection", return_value=orders),
            patch.object(order_service, "_retrieve_checkout_session", return_value=unpaid_session),
            patch.object(order_service, "create_project_from_paid_order") as create_project_mock,
        ):
            with self.assertRaises(ValueError):
                order_service.create_order_for_user(self.user, payload)
        create_project_mock.assert_not_called()

    def test_invalid_request_creates_no_entitlement(self):
        orders = FakeOrdersCollection()
        payload = SimpleNamespace(package_code="legacy_plus", stripe_session_id="cs_test_no_entitlement")
        unpaid_session = _paid_checkout_session(payment_status="unpaid", session_id="cs_test_no_entitlement")
        with (
            patch.object(order_service, "_get_orders_collection", return_value=orders),
            patch.object(order_service, "_retrieve_checkout_session", return_value=unpaid_session),
            patch.object(order_service, "apply_package_purchase_to_project") as apply_mock,
        ):
            with self.assertRaises(ValueError):
                order_service.create_order_for_user(self.user, payload)
        apply_mock.assert_not_called()

    def test_invalid_request_creates_no_maintenance_record(self):
        orders = FakeOrdersCollection()
        payload = SimpleNamespace(package_code="legacy_plus", stripe_session_id="cs_test_no_maintenance")
        unpaid_session = _paid_checkout_session(payment_status="unpaid", session_id="cs_test_no_maintenance")
        with (
            patch.object(order_service, "_get_orders_collection", return_value=orders),
            patch.object(order_service, "_retrieve_checkout_session", return_value=unpaid_session),
            patch.object(order_service, "_schedule_maintenance_start") as maintenance_mock,
        ):
            with self.assertRaises(ValueError):
                order_service.create_order_for_user(self.user, payload)
        maintenance_mock.assert_not_called()

    def test_expired_stripe_session_cannot_provision(self):
        orders = FakeOrdersCollection()
        payload = SimpleNamespace(package_code="legacy_plus", stripe_session_id="cs_test_expired")
        expired_session = _paid_checkout_session(status="expired")
        with (
            patch.object(order_service, "_get_orders_collection", return_value=orders),
            patch.object(order_service, "_retrieve_checkout_session", return_value=expired_session),
            patch.object(order_service, "_attach_project_to_paid_package_order") as attach_mock,
        ):
            with self.assertRaises(ValueError):
                order_service.create_order_for_user(self.user, payload)
        attach_mock.assert_not_called()

    def test_unknown_product_or_price_cannot_provision(self):
        orders = FakeOrdersCollection()
        payload = SimpleNamespace(package_code="legacy_plus", stripe_session_id="cs_test_unknown")
        unknown_product_session = _paid_checkout_session(
            package_code="unknown_package",
            product_name="Unknown Product",
            unit_amount=None,
        )
        with (
            patch.object(order_service, "_get_orders_collection", return_value=orders),
            patch.object(order_service, "_retrieve_checkout_session", return_value=unknown_product_session),
        ):
            with self.assertRaises(ValueError):
                order_service.create_order_for_user(self.user, payload)

    def test_product_price_mismatch_cannot_provision(self):
        orders = FakeOrdersCollection()
        payload = SimpleNamespace(package_code="legacy_plus", stripe_session_id="cs_test_mismatch")
        mismatch_session = _paid_checkout_session(unit_amount=100)
        with (
            patch.object(order_service, "_get_orders_collection", return_value=orders),
            patch.object(order_service, "_retrieve_checkout_session", return_value=mismatch_session),
        ):
            with self.assertRaises(ValueError):
                order_service.create_order_for_user(self.user, payload)

    def test_customer_email_mismatch_cannot_provision(self):
        orders = FakeOrdersCollection()
        payload = SimpleNamespace(package_code="legacy_plus", stripe_session_id="cs_test_email_mismatch")
        mismatch_email_session = _paid_checkout_session(email="another@example.com")
        with (
            patch.object(order_service, "_get_orders_collection", return_value=orders),
            patch.object(order_service, "_retrieve_checkout_session", return_value=mismatch_email_session),
        ):
            with self.assertRaises(ValueError):
                order_service.create_order_for_user(self.user, payload)

    def test_verified_paid_session_provisions_correct_package_exactly_once(self):
        orders = FakeOrdersCollection()
        payload = SimpleNamespace(package_code="legacy_plus", stripe_session_id="cs_test_paid_one")
        session = _paid_checkout_session(session_id="cs_test_paid_one")
        with (
            patch.object(order_service, "_get_orders_collection", return_value=orders),
            patch.object(order_service, "_retrieve_checkout_session", return_value=session),
            patch.object(order_service, "manual_fulfillment_mode_enabled", return_value=False),
            patch.object(
                order_service,
                "_attach_project_to_paid_package_order",
                side_effect=lambda **kwargs: kwargs["order_doc"],
            ) as attach_mock,
            patch.object(order_service, "_trigger_package_provisioning") as provisioning_mock,
        ):
            first = order_service.create_order_for_user(self.user, payload)
            second = order_service.create_order_for_user(self.user, payload)
        self.assertEqual(first["package_code"], "legacy_plus")
        self.assertEqual(second["id"], first["id"])
        self.assertEqual(attach_mock.call_count, 1)
        self.assertEqual(provisioning_mock.call_count, 1)
        self.assertEqual(len([d for d in orders.docs if d.get("stripe_session_id") == "cs_test_paid_one"]), 1)

    def test_manual_fulfillment_mode_records_paid_order_without_auto_provisioning(self):
        orders = FakeOrdersCollection()
        payload = SimpleNamespace(package_code="legacy_plus", stripe_session_id="cs_test_manual_one")
        session = _paid_checkout_session(session_id="cs_test_manual_one")
        with (
            patch.object(order_service, "_get_orders_collection", return_value=orders),
            patch.object(order_service, "_retrieve_checkout_session", return_value=session),
            patch.object(order_service, "manual_fulfillment_mode_enabled", return_value=True),
            patch.object(order_service, "_attach_project_to_paid_package_order") as attach_mock,
            patch.object(order_service, "_trigger_package_provisioning") as provisioning_mock,
        ):
            first = order_service.create_order_for_user(self.user, payload)
            second = order_service.create_order_for_user(self.user, payload)
        self.assertEqual(first["status"], "paid")
        self.assertEqual(first["source"], "stripe_verified")
        self.assertEqual(first["fulfillment_status"], order_service.FULFILLMENT_PENDING)
        self.assertIsNone(first["project_id"])
        self.assertEqual(second["id"], first["id"])
        attach_mock.assert_not_called()
        provisioning_mock.assert_not_called()

    def test_manual_fulfillment_mode_webhook_records_pending_fulfillment(self):
        orders = FakeOrdersCollection()
        event = {
            "type": "checkout.session.completed",
            "data": {"object": {"id": "cs_test_manual_evt"}},
        }
        session = _paid_checkout_session(session_id="cs_test_manual_evt")
        with (
            patch.object(order_service, "_get_orders_collection", return_value=orders),
            patch.object(order_service, "_retrieve_checkout_session", return_value=session),
            patch.object(order_service, "_get_user_by_email", return_value=self.user),
            patch.object(order_service, "store_stripe_customer_reference"),
            patch.object(order_service, "manual_fulfillment_mode_enabled", return_value=True),
            patch.object(order_service, "_attach_project_to_paid_package_order") as attach_mock,
            patch.object(order_service, "_trigger_package_provisioning") as provisioning_mock,
        ):
            result = order_service.upsert_order_from_stripe_event(event)
        attach_mock.assert_not_called()
        provisioning_mock.assert_not_called()
        stored = orders.find_one({"stripe_session_id": "cs_test_manual_evt"})
        self.assertIsNotNone(stored)
        self.assertEqual(stored["status"], "paid")
        self.assertEqual(stored["fulfillment_status"], order_service.FULFILLMENT_PENDING)
        self.assertIsNone(result.get("project_id"))

    def test_repeated_webhook_delivery_is_idempotent(self):
        orders = FakeOrdersCollection()
        event = {
            "type": "checkout.session.completed",
            "data": {"object": {"id": "cs_test_evt"}},
        }
        session = _paid_checkout_session(session_id="cs_test_evt")
        with (
            patch.object(order_service, "_get_orders_collection", return_value=orders),
            patch.object(order_service, "_retrieve_checkout_session", return_value=session),
            patch.object(order_service, "_get_user_by_email", return_value=self.user),
            patch.object(order_service, "store_stripe_customer_reference"),
            patch.object(
                order_service,
                "_attach_project_to_paid_package_order",
                side_effect=lambda **kwargs: kwargs["order_doc"],
            ),
            patch.object(order_service, "_trigger_package_provisioning"),
        ):
            first = order_service.upsert_order_from_stripe_event(event)
            second = order_service.upsert_order_from_stripe_event(event)
        self.assertFalse(first.get("existing"))
        self.assertTrue(second.get("existing"))
        self.assertEqual(len([d for d in orders.docs if d.get("stripe_session_id") == "cs_test_evt"]), 1)

    def test_existing_historical_orders_remain_unchanged(self):
        keith_order = {
            "_id": "order-keith-1",
            "user_id": "507f1f77bcf86cd799439099",
            "email": "keith.goffigan@example.com",
            "package_code": "legacy_snapshot",
            "status": "paid",
            "source": "stripe_webhook",
        }
        keith_upgrade = {
            "_id": "order-keith-upgrade-1",
            "user_id": "507f1f77bcf86cd799439099",
            "email": "keith.goffigan@example.com",
            "package_code": "legacy_plus",
            "status": "paid",
            "source": "admin_manual",
        }
        larry_order = {
            "_id": "order-larry-1",
            "user_id": "507f1f77bcf86cd799439199",
            "email": "larry.robinson@example.com",
            "package_code": "digital_legacy_portrait",
            "status": "paid",
            "source": "stripe_webhook",
        }
        orders = FakeOrdersCollection(seed=[keith_order, keith_upgrade, larry_order])
        baseline = copy.deepcopy(orders.docs)
        payload = SimpleNamespace(package_code="legacy_plus", stripe_session_id="cs_test_unpaid_hist")
        unpaid_session = _paid_checkout_session(payment_status="unpaid", session_id="cs_test_unpaid_hist")
        with (
            patch.object(order_service, "_get_orders_collection", return_value=orders),
            patch.object(order_service, "_retrieve_checkout_session", return_value=unpaid_session),
        ):
            with self.assertRaises(ValueError):
                order_service.create_order_for_user(self.user, payload)
        self.assertEqual(orders.docs[:3], baseline[:3])
        self.assertEqual(orders.docs[0]["email"], "keith.goffigan@example.com")
        self.assertEqual(orders.docs[1]["package_code"], "legacy_plus")

    def test_larry_mint_record_remains_unchanged(self):
        mint_record = {
            "_id": "mint-larry-1",
            "owner_email": "larry.robinson@example.com",
            "project_id": "project-larry-1",
            "token_status": "canonical_minted",
        }
        baseline = copy.deepcopy(mint_record)
        orders = FakeOrdersCollection()
        payload = SimpleNamespace(package_code="legacy_plus", stripe_session_id="cs_test_unpaid_larry")
        unpaid_session = _paid_checkout_session(payment_status="unpaid", session_id="cs_test_unpaid_larry")
        with (
            patch.object(order_service, "_get_orders_collection", return_value=orders),
            patch.object(order_service, "_retrieve_checkout_session", return_value=unpaid_session),
        ):
            with self.assertRaises(ValueError):
                order_service.create_order_for_user(self.user, payload)
        self.assertEqual(mint_record, baseline)

    def test_customer_cannot_access_admin_manual_order_route(self):
        dependency = require_any_permission(["admin.control.billing", "admin.orders.repair"])
        request = SimpleNamespace(path_params={}, query_params={})
        with patch.object(
            auth_dependencies,
            "_get_or_resolve_access_context",
            return_value={"permissions": {"user.read"}},
        ):
            with self.assertRaises(HTTPException) as exc:
                dependency(
                    request=request,
                    current_user={
                        "_id": "507f1f77bcf86cd799439012",
                        "email": "customer@example.com",
                    },
                )
        self.assertEqual(exc.exception.status_code, 403)

    def test_manual_order_requires_permission_reason_idempotency_and_audit_event(self):
        dependency = require_any_permission(["admin.control.billing", "admin.orders.repair"])
        request = SimpleNamespace(path_params={}, query_params={})
        with patch.object(
            auth_dependencies,
            "_get_or_resolve_access_context",
            return_value={"permissions": {"admin.control.billing"}},
        ):
            resolved = dependency(
                request=request,
                current_user={
                    "_id": "507f1f77bcf86cd799439001",
                    "email": "finance@example.com",
                },
            )
        self.assertEqual(resolved["email"], "finance@example.com")

        with self.assertRaises(ValidationError):
            AdminManualOrderCreate(
                customer_email="customer@example.com",
                package_code="legacy_plus",
                authorization_source="finance_ticket",
                idempotency_key="idem-key-99999",
            )
        with self.assertRaises(ValidationError):
            AdminManualOrderCreate(
                customer_email="customer@example.com",
                package_code="legacy_plus",
                reason="manual reconciliation",
                authorization_source="finance_ticket",
            )

        orders = FakeOrdersCollection()
        payload = AdminManualOrderCreate(
            customer_email="customer@example.com",
            package_code="legacy_plus",
            reason="approved finance correction",
            authorization_source="finance_ticket_123",
            idempotency_key="idem-key-12345678",
        )
        with (
            patch.object(order_service, "_get_orders_collection", return_value=orders),
            patch.object(order_service, "_get_user_by_email", return_value=self.user),
            patch.object(
                order_service,
                "_attach_project_to_paid_package_order",
                side_effect=lambda **kwargs: kwargs["order_doc"],
            ),
            patch.object(order_service, "_trigger_package_provisioning"),
            patch("app.services.audit_log_service.write_audit_log") as audit_mock,
        ):
            result = order_service.create_manual_order_for_admin(
                {
                    "_id": "507f1f77bcf86cd799439001",
                    "email": "finance@example.com",
                    "full_name": "Finance Admin",
                },
                payload,
            )
        self.assertEqual(result["status"], "paid")
        self.assertEqual(audit_mock.call_count, 1)
        self.assertEqual(len(orders.docs), 1)

    def test_admin_manual_schema_forbids_administrative_metadata_outside_contract(self):
        with self.assertRaises(ValidationError):
            AdminManualOrderCreate(
                customer_email="customer@example.com",
                package_code="legacy_plus",
                reason="manual fix",
                authorization_source="finance_ticket",
                idempotency_key="idem-key-12345678",
                order_status="paid",
            )


if __name__ == "__main__":
    unittest.main()
