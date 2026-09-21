import unittest
from datetime import datetime, timedelta, timezone
from typing import Any, cast
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.routes import stripe_webhooks


class FakeUpdateResult:
    def __init__(
        self,
        *,
        upserted_id=None,
        matched_count: int = 0,
        modified_count: int = 0,
    ):
        self.upserted_id = upserted_id
        self.matched_count = matched_count
        self.modified_count = modified_count


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
        if current is None or not self._matches_query(current, query):
            return FakeUpdateResult()

        before = dict(current)
        current.update(update.get("$set", {}))
        for key in update.get("$unset", {}):
            current.pop(key, None)
        return FakeUpdateResult(
            matched_count=1,
            modified_count=int(before != current),
        )

    def find_one(self, query, projection=None):
        event_id = query.get("event_id")
        current = self.docs.get(event_id)
        if current is None or not self._matches_query(current, query):
            return None
        if not projection:
            return dict(current)
        return {
            key: value
            for key, value in current.items()
            if key == "_id" or bool(projection.get(key))
        }

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


class FakeRequest:
    def __init__(self, *, headers=None, chunks=None):
        self.headers = dict(headers or {})
        self._chunks = list(chunks or [])
        self.stream_started = False

    async def stream(self):
        self.stream_started = True
        for chunk in self._chunks:
            yield chunk


class StripeWebhookPersistenceTests(unittest.TestCase):
    def test_ensure_stripe_event_indexes_creates_unique_event_id_index(self):
        events = FakeStripeEventsCollection()
        db = {"stripe_events": events}
        with patch.object(stripe_webhooks, "get_database", return_value=db):
            stripe_webhooks.ensure_stripe_event_indexes()
        self.assertIn("event_id_1", events.indexes)
        self.assertTrue(events.indexes["event_id_1"]["unique"])

    def test_claim_and_process_event_distinguishes_completed_duplicate(self):
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

        claim_state, claim_token = stripe_webhooks._claim_event_processing(
            cast(Any, events),
            event=event,
            now=now,
        )
        self.assertEqual(claim_state, "claimed")
        self.assertTrue(claim_token)

        stored = events.docs["evt_123"]
        self.assertNotIn("raw", stored)
        self.assertNotIn("customer_email", stored)
        self.assertEqual(stored["checkout_session_id"], "cs_test_123")

        committed = stripe_webhooks._mark_event_processed(
            cast(Any, events),
            event_id="evt_123",
            claim_token=claim_token,
            order_result={"order_id": "order-1"},
            maintenance_result={"updated": True},
            now=now,
        )
        self.assertTrue(committed)
        self.assertIn("processed_at", events.docs["evt_123"])
        self.assertNotIn("processing_claim", events.docs["evt_123"])

        duplicate_state, _ = stripe_webhooks._claim_event_processing(
            cast(Any, events),
            event=event,
            now=now,
        )
        self.assertEqual(duplicate_state, "completed")

    def test_active_processing_claim_is_not_reported_as_completed_duplicate(self):
        events = FakeStripeEventsCollection()
        now = datetime.now(timezone.utc)
        event = {"id": "evt_active", "type": "checkout.session.completed"}

        first_state, first_claim = stripe_webhooks._claim_event_processing(
            cast(Any, events),
            event=event,
            now=now,
        )
        second_state, second_claim = stripe_webhooks._claim_event_processing(
            cast(Any, events),
            event=event,
            now=now + timedelta(seconds=10),
        )

        self.assertEqual(first_state, "claimed")
        self.assertTrue(first_claim)
        self.assertEqual(second_state, "in_progress")
        self.assertEqual(second_claim, "")

    def test_stale_processing_claim_can_be_reclaimed(self):
        events = FakeStripeEventsCollection()
        started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        events.docs["evt_stale"] = {
            "event_id": "evt_stale",
            "processing_claim": "old-claim",
            "processing_started_at": started_at,
        }
        event = {"id": "evt_stale", "type": "checkout.session.completed"}
        now = started_at + timedelta(minutes=30)

        claim_state, claim_token = stripe_webhooks._claim_event_processing(
            cast(Any, events),
            event=event,
            now=now,
        )
        self.assertEqual(claim_state, "claimed")
        self.assertNotEqual(claim_token, "old-claim")

    def test_failed_processing_releases_claim_for_stripe_retry(self):
        events = FakeStripeEventsCollection()
        now = datetime.now(timezone.utc)
        event = {"id": "evt_retry", "type": "checkout.session.completed"}

        claim_state, first_claim = stripe_webhooks._claim_event_processing(
            cast(Any, events),
            event=event,
            now=now,
        )
        self.assertEqual(claim_state, "claimed")
        released = stripe_webhooks._mark_event_failed(
            cast(Any, events),
            event_id="evt_retry",
            claim_token=first_claim,
            failures=["order_upsert_failed"],
            order_result={"order_id": None, "error": "order_upsert_failed"},
            maintenance_result={"updated": False},
            now=now,
        )
        self.assertTrue(released)

        stored = events.docs["evt_retry"]
        self.assertEqual(stored["processing_status"], "retryable_failure")
        self.assertNotIn("processed_at", stored)
        self.assertNotIn("processing_claim", stored)

        retry_state, retry_claim = stripe_webhooks._claim_event_processing(
            cast(Any, events),
            event=event,
            now=now,
        )
        self.assertEqual(retry_state, "claimed")
        self.assertTrue(retry_claim)
        self.assertNotEqual(retry_claim, first_claim)

    def test_completion_write_requires_owned_claim(self):
        events = FakeStripeEventsCollection()
        now = datetime.now(timezone.utc)
        events.docs["evt_lost"] = {
            "event_id": "evt_lost",
            "processing_claim": "new-owner",
            "processing_started_at": now,
        }

        committed = stripe_webhooks._mark_event_processed(
            cast(Any, events),
            event_id="evt_lost",
            claim_token="old-owner",
            order_result={"order_id": "order-1"},
            maintenance_result={"updated": False},
            now=now,
        )

        self.assertFalse(committed)
        self.assertNotIn("processed_at", events.docs["evt_lost"])

    def test_checkout_succeeds_when_either_authoritative_handler_persists_it(self):
        package_failures = stripe_webhooks._downstream_failures(
            event_type="checkout.session.completed",
            order_result={"order_id": "order-1"},
            maintenance_result={"updated": False, "reason": "not_subscription_checkout"},
        )
        maintenance_failures = stripe_webhooks._downstream_failures(
            event_type="checkout.session.completed",
            order_result={"order_id": None, "error": "not_an_approved_package"},
            maintenance_result={"updated": True, "project_id": "project-1"},
        )

        self.assertEqual(package_failures, [])
        self.assertEqual(maintenance_failures, [])

    def test_unpersisted_relevant_events_are_retryable_failures(self):
        checkout_failures = stripe_webhooks._downstream_failures(
            event_type="checkout.session.completed",
            order_result={"order_id": None, "reason": "no_matching_user"},
            maintenance_result={"updated": False, "reason": "not_subscription_checkout"},
        )
        subscription_failures = stripe_webhooks._downstream_failures(
            event_type="customer.subscription.updated",
            order_result={"order_id": None},
            maintenance_result={"updated": False, "reason": "missing_project_id"},
        )

        self.assertEqual(checkout_failures, ["no_matching_user"])
        self.assertEqual(subscription_failures, ["missing_project_id"])

    def test_in_progress_event_returns_retryable_failure_not_success(self):
        events = FakeStripeEventsCollection()
        now = datetime.now(timezone.utc)
        events.docs["evt_active"] = {
            "event_id": "evt_active",
            "processing_claim": "current-owner",
            "processing_started_at": now,
            "processing_status": "processing",
        }
        event = {"id": "evt_active", "type": "checkout.session.completed"}

        with patch.object(
            stripe_webhooks,
            "get_database",
            return_value={"stripe_events": events},
        ):
            with self.assertRaises(HTTPException) as raised:
                stripe_webhooks._process_verified_event(event)

        self.assertEqual(raised.exception.status_code, 503)
        self.assertEqual(
            raised.exception.headers,
            {"Retry-After": str(stripe_webhooks.STRIPE_WEBHOOK_RETRY_AFTER_SECONDS)},
        )

    def test_completed_event_returns_successful_duplicate_response(self):
        events = FakeStripeEventsCollection()
        now = datetime.now(timezone.utc)
        events.docs["evt_done"] = {
            "event_id": "evt_done",
            "processed_at": now,
            "processing_status": "completed",
        }
        event = {"id": "evt_done", "type": "checkout.session.completed"}

        with patch.object(
            stripe_webhooks,
            "get_database",
            return_value={"stripe_events": events},
        ), patch.object(
            stripe_webhooks,
            "upsert_order_from_stripe_event",
        ) as order_handler:
            result = stripe_webhooks._process_verified_event(event)

        self.assertTrue(result["duplicate"])
        order_handler.assert_not_called()


class StripeWebhookRequestTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_signature_is_rejected_before_body_is_read(self):
        request = FakeRequest(chunks=[b"must-not-be-read"])

        with self.assertRaises(HTTPException) as raised:
            await stripe_webhooks.stripe_webhook(cast(Any, request))

        self.assertEqual(raised.exception.status_code, 400)
        self.assertFalse(request.stream_started)

    async def test_declared_oversized_body_is_rejected_before_streaming(self):
        request = FakeRequest(
            headers={
                "content-length": str(stripe_webhooks.STRIPE_WEBHOOK_MAX_BYTES + 1)
            },
            chunks=[b"must-not-be-read"],
        )

        with self.assertRaises(HTTPException) as raised:
            await stripe_webhooks._read_webhook_body(cast(Any, request))

        self.assertEqual(raised.exception.status_code, 413)
        self.assertFalse(request.stream_started)

    async def test_streamed_body_is_bounded_even_without_content_length(self):
        request = FakeRequest(
            chunks=[
                b"a" * stripe_webhooks.STRIPE_WEBHOOK_MAX_BYTES,
                b"b",
            ]
        )

        with self.assertRaises(HTTPException) as raised:
            await stripe_webhooks._read_webhook_body(cast(Any, request))

        self.assertEqual(raised.exception.status_code, 413)
        self.assertTrue(request.stream_started)

    async def test_body_at_limit_is_accepted(self):
        payload = b"a" * stripe_webhooks.STRIPE_WEBHOOK_MAX_BYTES
        request = FakeRequest(
            headers={"content-length": str(len(payload))},
            chunks=[payload],
        )

        result = await stripe_webhooks._read_webhook_body(cast(Any, request))

        self.assertEqual(result, payload)

    async def test_verified_event_processing_is_offloaded_from_event_loop(self):
        request = FakeRequest(
            headers={
                "stripe-signature": "signed",
                "content-length": "2",
            },
            chunks=[b"{}"],
        )
        event = {"id": "evt_thread", "type": "customer.updated"}
        expected = {"received": True, "type": "customer.updated"}

        with patch.object(
            stripe_webhooks,
            "_require_setting",
            side_effect=lambda value, name: f"configured-{name}",
        ), patch.object(
            stripe_webhooks.stripe.Webhook,
            "construct_event",
            return_value=event,
        ), patch.object(
            stripe_webhooks,
            "run_in_threadpool",
            new_callable=AsyncMock,
            return_value=expected,
        ) as threadpool:
            result = await stripe_webhooks.stripe_webhook(cast(Any, request))

        self.assertEqual(result, expected)
        threadpool.assert_awaited_once_with(
            stripe_webhooks._process_verified_event,
            event,
        )


if __name__ == "__main__":
    unittest.main()
