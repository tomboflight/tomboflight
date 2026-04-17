from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock

from fastapi import HTTPException, status


@dataclass
class _LockoutState:
    failures: int = 0
    locked_until: datetime | None = None


_REQUEST_BUCKETS: dict[tuple[str, str], deque[datetime]] = defaultdict(deque)
_LOCKOUTS: dict[tuple[str, str], _LockoutState] = {}
_STATE_LOCK = Lock()


def _utcnow() -> datetime:
    return datetime.now(UTC)


def enforce_rate_limit(*, scope: str, key: str, limit: int, window_seconds: int) -> None:
    if limit <= 0 or window_seconds <= 0:
        return
    now = _utcnow()
    window_start = now - timedelta(seconds=window_seconds)
    bucket_key = (str(scope or "").strip().lower(), str(key or "").strip().lower())
    with _STATE_LOCK:
        bucket = _REQUEST_BUCKETS[bucket_key]
        while bucket and bucket[0] < window_start:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again shortly.",
            )
        bucket.append(now)


def enforce_lockout(*, scope: str, key: str) -> None:
    lock_key = (str(scope or "").strip().lower(), str(key or "").strip().lower())
    with _STATE_LOCK:
        state = _LOCKOUTS.get(lock_key)
        if not state or not state.locked_until:
            return
        if state.locked_until <= _utcnow():
            state.locked_until = None
            state.failures = 0
            return
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Try again after the lockout period.",
        )


def record_failure(
    *,
    scope: str,
    key: str,
    lockout_threshold: int,
    lockout_seconds: int,
) -> bool:
    if lockout_threshold <= 0:
        return False
    lock_key = (str(scope or "").strip().lower(), str(key or "").strip().lower())
    with _STATE_LOCK:
        state = _LOCKOUTS.get(lock_key) or _LockoutState()
        state.failures += 1
        if lockout_seconds > 0 and state.failures >= lockout_threshold:
            state.locked_until = _utcnow() + timedelta(seconds=lockout_seconds)
        _LOCKOUTS[lock_key] = state
        return bool(state.locked_until)


def clear_failures(*, scope: str, key: str) -> None:
    lock_key = (str(scope or "").strip().lower(), str(key or "").strip().lower())
    with _STATE_LOCK:
        _LOCKOUTS.pop(lock_key, None)

