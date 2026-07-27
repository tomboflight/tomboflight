import unittest
from datetime import UTC, datetime
from unittest.mock import patch

from bson import ObjectId

from contextlib import contextmanager

from app.services import audit_log_service
from app.services import manual_fulfillment_service as mfs
from app.services import order_service


@contextmanager
def use_db(db):
    with (
        patch.object(mfs, "get_database", return_value=db),
        patch.object(audit_log_service, "get_database", return_value=db),
    ):
        yield


class _Cursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def sort(self, *args, **kwargs):  # noqa: ARG002
        return self

    def limit(self, n):
        self._docs = self._docs[:n]
        return self

    def __iter__(self):
        return iter(self._docs)


class FakeCollection:
    def __init__(self, seed=None):
        self.docs = [dict(d) for d in (seed or [])]

    def _match(self, query, item):
        for key, expected in (query or {}).items():
            if isinstance(expected, dict) and "$in" in expected:
                if item.get(key) not in expected["$in"]:
                    return False
            elif item.get(key) != expected:
                return False
        return True

    def find_one(self, query, sort=None):  # noqa: ARG002
        for item in self.docs:
            if self._match(query, item):
                return dict(item)
        return None

    def find(self, query):
        return _Cursor(dict(i) for i in self.docs if self._match(query, i))

    def update_one(self, query, update):
        for index, item in enumerate(self.docs):
            if self._match(query, item):
                updated = dict(item)
                updated.update((update or {}).get("$set") or {})
                self.docs[index] = updated
                return

    def insert_one(self, document):
        payload = dict(document)
        payload.setdefault("_id", ObjectId())
        self.docs.append(payload)

        class _Result:
            inserted_id = payload["_id"]

        return _Result()


class FakeDb:
    def __init__(self, collections):
        self._collections = collections

    def __getitem__(self, name):
        return self._collections.setdefault(name, FakeCollection())

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return self[name]


USER_ID = ObjectId()
ORDER_ID = ObjectId()

ADMIN = {"_id": "admin-1", "email": "l.robinson@tomboflight.com", "full_name": "Larry Robinson"}


def _paid_order(**overrides):
    order = {
        "_id": ORDER_ID,
        "user_id": USER_ID,
        "email": "customer@example.com",
        "package_code": "legacy_plus",
        "package_slug": "legacy_plus",
        "package_name": "Legacy Plus",
        "price_label": "$3,200",
        "item_type": "package",
        "billing_plan": "one_time",
        "source": "stripe_webhook",
        "status": "paid",
        "stripe_session_id": "cs_test_1",
        "fulfillment_status": mfs.FULFILLMENT_PENDING,
        "created_at": datetime.now(UTC),
    }
    order.update(overrides)
    return order


class ManualFulfillmentQueueTests(unittest.TestCase):
    def _fake_db(self, orders=None, users=None, entitlements=None):
        return FakeDb(
            {
                "orders": FakeCollection(orders or []),
                "users": FakeCollection(
                    users
                    if users is not None
                    else [{"_id": USER_ID, "email": "customer@example.com", "full_name": "Customer One"}]
                ),
                "project_entitlements": FakeCollection(entitlements or []),
                "audit_logs": FakeCollection(),
            }
        )

    def test_queue_lists_open_verified_orders_only(self):
        db = self._fake_db(
            orders=[
                _paid_order(),
                _paid_order(
                    _id=ObjectId(),
                    stripe_session_id="cs_done",
                    fulfillment_status=mfs.FULFILLMENT_COMPLETE,
                ),
                _paid_order(
                    _id=ObjectId(),
                    stripe_session_id=None,
                    source="customer_checkout_pending",
                    status="pending_confirmation",
                    fulfillment_status=None,
                ),
            ]
        )
        with use_db(db):
            result = mfs.list_manual_fulfillment_queue()
        self.assertEqual(result["count"], 1)
        item = result["items"][0]
        self.assertEqual(item["order_id"], str(ORDER_ID))
        self.assertEqual(item["customer_name"], "Customer One")
        self.assertEqual(item["next_required_action"], "verify_payment")
        self.assertEqual(item["entitlement_status"], "no_project")

    def test_action_requires_reason_and_idempotency_key(self):
        db = self._fake_db(orders=[_paid_order()])
        with use_db(db):
            with self.assertRaises(ValueError):
                mfs.execute_fulfillment_action(
                    ADMIN, order_id=str(ORDER_ID), action="start_fulfillment", reason="", idempotency_key="k" * 8
                )
            with self.assertRaises(ValueError):
                mfs.execute_fulfillment_action(
                    ADMIN, order_id=str(ORDER_ID), action="start_fulfillment", reason="valid reason", idempotency_key="short"
                )

    def test_verify_payment_uses_server_side_stripe_session(self):
        db = self._fake_db(orders=[_paid_order()])
        session = {"payment_status": "paid", "amount_total": 320000, "currency": "usd", "payment_intent": "pi_1"}
        with (
            use_db(db),
            patch.object(order_service, "_retrieve_checkout_session", return_value=session),
        ):
            result = mfs.execute_fulfillment_action(
                ADMIN, order_id=str(ORDER_ID), action="verify_payment", reason="CEO review", idempotency_key="verify-key-1"
            )
        self.assertTrue(result["verified"])
        stored = db["orders"].find_one({"_id": ORDER_ID})
        self.assertTrue(stored.get("payment_verified_at"))
        self.assertEqual(stored.get("stripe_payment_intent_id"), "pi_1")
        audit_actions = [d["action"] for d in db["audit_logs"].docs]
        self.assertEqual(audit_actions, ["manual_fulfillment.verify_payment"])

    def test_verify_payment_rejects_unpaid_stripe_session(self):
        db = self._fake_db(orders=[_paid_order()])
        session = {"payment_status": "unpaid"}
        with (
            use_db(db),
            patch.object(order_service, "_retrieve_checkout_session", return_value=session),
        ):
            with self.assertRaises(ValueError):
                mfs.execute_fulfillment_action(
                    ADMIN, order_id=str(ORDER_ID), action="verify_payment", reason="CEO review", idempotency_key="verify-key-2"
                )
        stored = db["orders"].find_one({"_id": ORDER_ID})
        self.assertFalse(stored.get("payment_verified_at"))

    def test_assign_package_requires_verified_payment(self):
        db = self._fake_db(orders=[_paid_order()])
        with use_db(db):
            with self.assertRaises(ValueError):
                mfs.execute_fulfillment_action(
                    ADMIN, order_id=str(ORDER_ID), action="assign_package", reason="provision", idempotency_key="assign-key-1"
                )

    def test_assign_package_provisions_once_and_is_idempotent(self):
        project_id = ObjectId()
        db = self._fake_db(orders=[_paid_order(payment_verified_at=datetime.now(UTC))])

        def fake_attach(**kwargs):
            doc = dict(kwargs["order_doc"])
            doc["project_id"] = project_id
            db["orders"].update_one({"_id": doc["_id"]}, {"$set": {"project_id": project_id}})
            return doc

        with (
            use_db(db),
            patch.object(order_service, "_attach_project_to_paid_package_order", side_effect=fake_attach) as attach_mock,
            patch.object(order_service, "_trigger_package_provisioning") as provision_mock,
        ):
            first = mfs.execute_fulfillment_action(
                ADMIN, order_id=str(ORDER_ID), action="assign_package", reason="provision", idempotency_key="assign-key-2"
            )
            second = mfs.execute_fulfillment_action(
                ADMIN, order_id=str(ORDER_ID), action="assign_package", reason="provision", idempotency_key="assign-key-2"
            )
        self.assertTrue(first["provisioned"])
        self.assertEqual(first["project_id"], str(project_id))
        self.assertTrue(second.get("already_provisioned"))
        self.assertEqual(attach_mock.call_count, 1)
        self.assertEqual(provision_mock.call_count, 1)

    def test_complete_fulfillment_requires_provisioned_project(self):
        db = self._fake_db(orders=[_paid_order(payment_verified_at=datetime.now(UTC))])
        with use_db(db):
            with self.assertRaises(ValueError):
                mfs.execute_fulfillment_action(
                    ADMIN, order_id=str(ORDER_ID), action="complete_fulfillment", reason="done", idempotency_key="complete-1"
                )

    def test_complete_fulfillment_records_actor_and_is_idempotent(self):
        db = self._fake_db(
            orders=[
                _paid_order(
                    payment_verified_at=datetime.now(UTC),
                    project_id=ObjectId(),
                    fulfillment_status=mfs.FULFILLMENT_IN_PROGRESS,
                )
            ]
        )
        with use_db(db):
            first = mfs.execute_fulfillment_action(
                ADMIN, order_id=str(ORDER_ID), action="complete_fulfillment", reason="fulfilled", idempotency_key="complete-2"
            )
            second = mfs.execute_fulfillment_action(
                ADMIN, order_id=str(ORDER_ID), action="complete_fulfillment", reason="fulfilled", idempotency_key="complete-2"
            )
        self.assertEqual(first["fulfillment_status"], mfs.FULFILLMENT_COMPLETE)
        self.assertTrue(second.get("already_complete"))
        stored = db["orders"].find_one({"_id": ORDER_ID})
        self.assertEqual(stored["fulfillment_completed_by"], "l.robinson@tomboflight.com")
        audit_actions = [d["action"] for d in db["audit_logs"].docs]
        self.assertEqual(audit_actions.count("manual_fulfillment.complete_fulfillment"), 1)

    def test_escalate_mismatch_marks_order(self):
        db = self._fake_db(orders=[_paid_order()])
        with use_db(db):
            result = mfs.execute_fulfillment_action(
                ADMIN, order_id=str(ORDER_ID), action="escalate_mismatch", reason="amount mismatch", idempotency_key="escalate-1"
            )
        self.assertEqual(result["fulfillment_status"], mfs.FULFILLMENT_ESCALATED)
        stored = db["orders"].find_one({"_id": ORDER_ID})
        self.assertEqual(stored["fulfillment_escalation_reason"], "amount mismatch")

    def test_rejects_action_on_non_authoritative_order(self):
        db = self._fake_db(orders=[_paid_order(source="customer_checkout_pending")])
        with use_db(db):
            with self.assertRaises(ValueError):
                mfs.execute_fulfillment_action(
                    ADMIN, order_id=str(ORDER_ID), action="verify_payment", reason="check", idempotency_key="reject-1"
                )


if __name__ == "__main__":
    unittest.main()
