import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from app.routes import stripe_webhooks


class FakeUpdateResult:
    def __init__(self, upserted_id=None):
        self.upserted_id = upserted_id


class FakeStripeEventsCollection:
    def __init__(self):
        self.docs: dict[str, dict] = {}
        self.indexes: dict[str, dict] = {}

    def create_index(self, keys, name, unique=False, sparse=False):
        self.indexes[name] = {
            "keys": keys,
            "unique": unique,
            "sparse": sparse,
        }

    def update_one(self, query, update, upsert=False):
        event_id = query.get("event_id")
        current = self.docs.get(event_id)
        if current is None and upsert:
            current = {"event_id": event_id}
            current.update(update.get("$setOnInsert", {}))
            self.docs[event_id] = current
            return FakeUpdateResult(upserted_id=event_id)
        if current is None:
            return FakeUpdateResult()
        current.update(update.get("$set", {}))
        for key in update.get("$unset", {}):
            current.pop(key, None)
        return FakeUpdateResult()

    def find_one_and_update(self, query, update, return_document=None):
        del return_document
        event_id = query.get("event_id")
        current = self.docs.get(event_id)
        if current is None:
            return None
        if not self._matches_query(current, query):
            return None
        current.update(update.get("$set", {}))
        return dict(current)

    def _matches_query(self, current, query):
        for key, expected in query.items():
            if key == "event_id":
                if current.get("event_id") != expected:
                    return False
                continue
            if key == "$or":
                if not any(self._matches_query(current, item) for item in expected):
                    return False
                continue
            if isinstance(expected, dict):
                if "$exists" in expected:
                    exists = key in current
                    if exists != bool(expected["$exists"]):
                        return False
                    continue
                if "$lt" in expected:
                    value = current.get(key)
                    if value is None or not (value < expected["$lt"]):
                        return False
                    continue
            if current.get(key) != expected:
                return False
        return True


class StripeWebhookPersistenceTests(unittest.TestCase):
    def test_ensure_stripe_event_indexes_creates_unique_event_id_index(self):
        events = FakeStripeEventsCollection()
        db = {"stripe_events": events}
        with patch.object(stripe_webhooks, "get_database", return_value=db):
            stripe_webhooks.ensure_stripe_event_indexes()
        self.assertIn("event_id_1", events.indexes)
        self.assertTrue(events.indexes["event_id_1"]["unique"])

    def test_claim_and_process_event_is_idempotent_and_minimizes_payload_storage(self):
        events = FakeStripeEventsCollection()
        now = datetime.now(timezone.utc)
        event = {
            "id": "evt_123",
            "type": "checkout.session.completed",
            "livemode": False,
            "created": 1710000000,
            "api_version": "2024-01-01",
            "data": {
                "object": {
                    "object": "checkout.session",
                    "id": "cs_test_123",
                    "customer": "cus_123",
                    "subscription": "sub_123",
                    "payment_intent": "pi_123",
                    "customer_email": "should-not-be-stored@example.com",
                }
            },
            "request": {"id": "req_123", "idempotency_key": "idem_123"},
        }

        should_process, claim_token = stripe_webhooks._claim_event_processing(
            events,
            event=event,
            now=now,
        )
        self.assertTrue(should_process)
        self.assertTrue(claim_token)

        stored = events.docs["evt_123"]
        self.assertNotIn("raw", stored)
        self.assertNotIn("customer_email", stored)
        self.assertEqual(stored["checkout_session_id"], "cs_test_123")

        stripe_webhooks._mark_event_processed(
            events,
            event_id="evt_123",
            claim_token=claim_token,
            order_result={"order_id": "order-1"},
            maintenance_result={"updated": True},
            now=now,
        )
        self.assertIn("processed_at", events.docs["evt_123"])
        self.assertNotIn("processing_claim", events.docs["evt_123"])

        duplicate_should_process, _ = stripe_webhooks._claim_event_processing(
            events,
            event=event,
            now=now,
        )
        self.assertFalse(duplicate_should_process)

    def test_stale_processing_claim_can_be_reclaimed(self):
        events = FakeStripeEventsCollection()
        started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        events.docs["evt_stale"] = {
            "event_id": "evt_stale",
            "processing_claim": "old-claim",
            "processing_started_at": started_at,
        }
        event = {"id": "evt_stale", "type": "checkout.session.completed"}
        now = started_at.replace(minute=started_at.minute + 30)

        should_process, claim_token = stripe_webhooks._claim_event_processing(
            events,
            event=event,
            now=now,
        )
        self.assertTrue(should_process)
        self.assertNotEqual(claim_token, "old-claim")


if __name__ == "__main__":
    unittest.main()
