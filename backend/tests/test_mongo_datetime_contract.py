from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

from bson import BSON
from bson.codec_options import CodecOptions
from fastapi import HTTPException

from app import database
from app.services import rate_limit_service


class _FakeAdmin:
    def command(self, name: str) -> dict[str, int]:
        if name != "ping":
            raise AssertionError(f"Unexpected MongoDB admin command: {name}")
        return {"ok": 1}


class _FakeDatabase:
    def command(self, name: str) -> dict[str, int]:
        if name != "ping":
            raise AssertionError(f"Unexpected MongoDB database command: {name}")
        return {"ok": 1}


class _FakeMongoClient:
    def __init__(self) -> None:
        self.admin = _FakeAdmin()
        self.database = _FakeDatabase()
        self.closed = False

    def __getitem__(self, name: str) -> _FakeDatabase:
        if not name:
            raise AssertionError("Database name must be configured")
        return self.database

    def close(self) -> None:
        self.closed = True


class _LockoutCollection:
    def __init__(self, locked_until: datetime) -> None:
        self.locked_until = locked_until

    def find_one(self, query: dict[str, Any]) -> dict[str, Any]:
        return {
            "_id": query["_id"],
            "failures": 5,
            "locked_until": self.locked_until,
        }

    def update_one(self, query: dict[str, Any], update: dict[str, Any]) -> None:
        raise AssertionError(
            f"An active lockout must not be cleared: query={query}, update={update}"
        )


class MongoDatetimeContractTests(unittest.TestCase):
    def tearDown(self) -> None:
        existing_client = database.client
        database.client = None
        database.db = None
        database._last_connection_attempt_monotonic = 0.0
        if existing_client is not None:
            existing_client.close()

    def test_application_mongo_client_enables_timezone_aware_decoding(self) -> None:
        fake_client = _FakeMongoClient()

        with patch.object(database.settings, "mongodb_uri", "mongodb://localhost:27017"), patch.object(
            database.settings,
            "mongodb_db_name",
            "tomb_of_light_test",
        ), patch.object(
            database,
            "MongoClient",
            return_value=fake_client,
        ) as mongo_client:
            connected = database._connect_to_mongo_unlocked(force=True)

        self.assertIs(connected, fake_client.database)
        self.assertTrue(mongo_client.call_args.kwargs["tz_aware"])
        self.assertEqual(mongo_client.call_count, 1)

    def test_bson_round_trip_returns_aware_utc_datetime_with_application_codec(self) -> None:
        source = datetime(2026, 9, 21, 12, 30, 45, 123000, tzinfo=UTC)
        payload = BSON.encode({"timestamp": source})

        default_decoded = payload.decode()["timestamp"]
        aware_decoded = payload.decode(
            codec_options=CodecOptions(tz_aware=True, tzinfo=UTC)
        )["timestamp"]

        self.assertIsNone(default_decoded.tzinfo)
        self.assertIsNotNone(aware_decoded.tzinfo)
        self.assertEqual(aware_decoded, source)
        self.assertLess(aware_decoded, source + timedelta(seconds=1))

    def test_persisted_lockout_compares_against_aware_utc_now(self) -> None:
        future = datetime.now(UTC) + timedelta(minutes=10)
        persisted = BSON.encode({"locked_until": future}).decode(
            codec_options=CodecOptions(tz_aware=True, tzinfo=UTC)
        )["locked_until"]
        collection = _LockoutCollection(persisted)

        with patch.object(
            rate_limit_service,
            "_shared_backend_enabled",
            return_value=True,
        ), patch.object(
            rate_limit_service,
            "_shared_collection",
            return_value=collection,
        ):
            with self.assertRaises(HTTPException) as raised:
                rate_limit_service.enforce_lockout(
                    scope="signin",
                    key="customer@example.com",
                )

        self.assertEqual(raised.exception.status_code, 429)

    def test_persisted_kernel_execution_timestamp_supports_staleness_comparison(self) -> None:
        old_started_at = datetime.now(UTC) - timedelta(minutes=30)
        persisted = BSON.encode(
            {"execution_started_at": old_started_at}
        ).decode(
            codec_options=CodecOptions(tz_aware=True, tzinfo=UTC)
        )["execution_started_at"]
        stale_before = datetime.now(UTC) - timedelta(minutes=15)

        self.assertLessEqual(persisted, stale_before)


if __name__ == "__main__":
    unittest.main()
