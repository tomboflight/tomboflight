from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
from threading import Lock

from fastapi import HTTPException, status
from pymongo import ASCENDING, ReturnDocument

from app.config import settings
from app.database import get_database


RATE_LIMIT_COLLECTION = "auth_rate_limit_state"


@dataclass
class _LockoutState:
    failures: int = 0
    locked_until: datetime | None = None


_REQUEST_BUCKETS: dict[tuple[str, str], deque[datetime]] = defaultdict(deque)
_LOCKOUTS: dict[tuple[str, str], _LockoutState] = {}
_STATE_LOCK = Lock()


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _normalized_scope_and_key(scope: str, key: str) -> tuple[str, str]:
    return (
        str(scope or "").strip().lower(),
        str(key or "").strip().lower(),
    )


def _principal_hash(scope: str, key: str) -> str:
    normalized_scope, normalized_key = _normalized_scope_and_key(scope, key)
    payload = f"{normalized_scope}:{normalized_key}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _shared_backend_enabled() -> bool:
    return bool(settings.is_production_environment)


def _shared_collection():
    return get_database()[RATE_LIMIT_COLLECTION]


def ensure_rate_limit_indexes() -> None:
    collection = _shared_collection()
    collection.create_index(
        [("expires_at", ASCENDING)],
        name="auth_rate_limit_expiry_ttl",
        expireAfterSeconds=0,
    )
    collection.create_index(
        [("kind", ASCENDING), ("scope", ASCENDING), ("updated_at", ASCENDING)],
        name="auth_rate_limit_scope_state",
    )


def _too_many_requests(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=message,
    )


def _enforce_memory_rate_limit(
    *,
    scope: str,
    key: str,
    limit: int,
    window_seconds: int,
) -> None:
    now = _utcnow()
    window_start = now - timedelta(seconds=window_seconds)
    bucket_key = _normalized_scope_and_key(scope, key)
    with _STATE_LOCK:
        bucket = _REQUEST_BUCKETS[bucket_key]
        while bucket and bucket[0] < window_start:
            bucket.popleft()
        if len(bucket) >= limit:
            raise _too_many_requests("Too many requests. Please try again shortly.")
        bucket.append(now)


def enforce_rate_limit(*, scope: str, key: str, limit: int, window_seconds: int) -> None:
    if limit <= 0 or window_seconds <= 0:
        return
    if not _shared_backend_enabled():
        _enforce_memory_rate_limit(
            scope=scope,
            key=key,
            limit=limit,
            window_seconds=window_seconds,
        )
        return

    now = _utcnow()
    normalized_scope, _ = _normalized_scope_and_key(scope, key)
    principal_hash = _principal_hash(scope, key)
    window_number = int(now.timestamp()) // int(window_seconds)
    expires_at = datetime.fromtimestamp(
        (window_number + 2) * int(window_seconds),
        tz=UTC,
    )
    document = _shared_collection().find_one_and_update(
        {"_id": f"bucket:{principal_hash}:{window_number}"},
        {
            "$inc": {"count": 1},
            "$set": {"updated_at": now},
            "$setOnInsert": {
                "kind": "request_bucket",
                "scope": normalized_scope,
                "principal_hash": principal_hash,
                "window_number": window_number,
                "expires_at": expires_at,
                "created_at": now,
            },
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    ) or {}
    if int(document.get("count") or 0) > int(limit):
        raise _too_many_requests("Too many requests. Please try again shortly.")


def _enforce_memory_lockout(*, scope: str, key: str) -> None:
    lock_key = _normalized_scope_and_key(scope, key)
    with _STATE_LOCK:
        state = _LOCKOUTS.get(lock_key)
        if not state or not state.locked_until:
            return
        if state.locked_until <= _utcnow():
            state.locked_until = None
            state.failures = 0
            return
        raise _too_many_requests(
            "Too many failed attempts. Try again after the lockout period."
        )


def enforce_lockout(*, scope: str, key: str) -> None:
    if not _shared_backend_enabled():
        _enforce_memory_lockout(scope=scope, key=key)
        return

    now = _utcnow()
    document_id = f"lockout:{_principal_hash(scope, key)}"
    document = _shared_collection().find_one({"_id": document_id}) or {}
    locked_until = document.get("locked_until")
    if isinstance(locked_until, datetime) and locked_until > now:
        raise _too_many_requests(
            "Too many failed attempts. Try again after the lockout period."
        )
    if isinstance(locked_until, datetime) and locked_until <= now:
        _shared_collection().update_one(
            {"_id": document_id, "locked_until": locked_until},
            {"$set": {"failures": 0, "locked_until": None, "updated_at": now}},
        )


def _record_memory_failure(
    *,
    scope: str,
    key: str,
    lockout_threshold: int,
    lockout_seconds: int,
) -> bool:
    lock_key = _normalized_scope_and_key(scope, key)
    with _STATE_LOCK:
        state = _LOCKOUTS.get(lock_key) or _LockoutState()
        state.failures += 1
        if lockout_seconds > 0 and state.failures >= lockout_threshold:
            state.locked_until = _utcnow() + timedelta(seconds=lockout_seconds)
        _LOCKOUTS[lock_key] = state
        return bool(state.locked_until)


def record_failure(
    *,
    scope: str,
    key: str,
    lockout_threshold: int,
    lockout_seconds: int,
) -> bool:
    if lockout_threshold <= 0:
        return False
    if not _shared_backend_enabled():
        return _record_memory_failure(
            scope=scope,
            key=key,
            lockout_threshold=lockout_threshold,
            lockout_seconds=lockout_seconds,
        )

    now = _utcnow()
    normalized_scope, _ = _normalized_scope_and_key(scope, key)
    principal_hash = _principal_hash(scope, key)
    document_id = f"lockout:{principal_hash}"
    expires_at = now + timedelta(seconds=max(3600, int(lockout_seconds) * 4))
    document = _shared_collection().find_one_and_update(
        {"_id": document_id},
        {
            "$inc": {"failures": 1},
            "$set": {"updated_at": now, "expires_at": expires_at},
            "$setOnInsert": {
                "kind": "failure_lockout",
                "scope": normalized_scope,
                "principal_hash": principal_hash,
                "locked_until": None,
                "created_at": now,
            },
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    ) or {}
    locked_until = document.get("locked_until")
    if isinstance(locked_until, datetime) and locked_until > now:
        return True
    if int(document.get("failures") or 0) < int(lockout_threshold):
        return False
    if lockout_seconds <= 0:
        return False

    locked_until = now + timedelta(seconds=int(lockout_seconds))
    _shared_collection().update_one(
        {"_id": document_id},
        {
            "$set": {
                "locked_until": locked_until,
                "updated_at": now,
                "expires_at": max(expires_at, locked_until + timedelta(hours=1)),
            }
        },
    )
    return True


def clear_failures(*, scope: str, key: str) -> None:
    if _shared_backend_enabled():
        _shared_collection().delete_one(
            {"_id": f"lockout:{_principal_hash(scope, key)}"}
        )
        return
    lock_key = _normalized_scope_and_key(scope, key)
    with _STATE_LOCK:
        _LOCKOUTS.pop(lock_key, None)
