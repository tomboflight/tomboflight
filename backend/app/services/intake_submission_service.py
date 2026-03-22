from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from pymongo.collection import Collection

from app.database import get_database

COLLECTION = "intake_submissions"

LOCKED_STATUSES = {"submitted", "in_review", "approved"}
REVIEWABLE_STATUSES = {"submitted", "in_review", "approved", "rejected"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _oid(value: str) -> ObjectId:
    return ObjectId(value)


def _serialize(doc: dict[str, Any]) -> dict[str, Any]:
    out = dict(doc)
    out["id"] = str(out.pop("_id"))

    if "user_id" in out and isinstance(out["user_id"], ObjectId):
        out["user_id"] = str(out["user_id"])

    return out


def _collection() -> Collection:
    db = get_database()
    return db[COLLECTION]


def create_intake_submission(
    *,
    user_id: str,
    email: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Create a submitted intake record.

    Rules:
    - one active locked submission at a time per user
    - allowed to submit again only when no locked submission exists
      or after rejection flow is handled manually
    """
    col = _collection()
    now = _now()

    latest = col.find_one(
        {"user_id": _oid(user_id)},
        sort=[("created_at", -1)],
    )

    if latest and str(latest.get("status", "")).lower() in LOCKED_STATUSES:
        raise ValueError(
            "An intake submission is already submitted or under review for this account."
        )

    status = str(payload.get("status") or "submitted").strip().lower()
    review_locked = status in LOCKED_STATUSES

    record: dict[str, Any] = {
        "user_id": _oid(user_id),
        "email": str(email).strip().lower(),
        "package_slug": payload["package_slug"],
        "package_name": payload["package_name"],
        "status": status,
        "review_locked": review_locked,
        "household": payload["household"],
        "family_map": payload["family_map"],
        "uploads": payload.get("uploads", {}) or {},
        "consent": payload.get("consent", {}) or {},
        "review": payload["review"],
        "submitted_at": now if status == "submitted" else None,
        "review_started_at": None,
        "reviewed_at": None,
        "reviewed_by": None,
        "review_notes": "",
        "approval_notes": "",
        "rejection_reason": "",
        "created_at": now,
        "updated_at": now,
    }

    result = col.insert_one(record)
    saved = col.find_one({"_id": result.inserted_id})
    if not saved:
        raise RuntimeError("Failed to fetch saved intake submission after insert.")

    return _serialize(saved)


def get_latest_for_user(user_id: str) -> Optional[dict[str, Any]]:
    col = _collection()

    doc = col.find_one(
        {"user_id": _oid(user_id)},
        sort=[("created_at", -1)],
    )
    return _serialize(doc) if doc else None


def list_for_user(user_id: str, limit: int = 10) -> list[dict[str, Any]]:
    col = _collection()

    cursor = (
        col.find({"user_id": _oid(user_id)})
        .sort("created_at", -1)
        .limit(int(limit))
    )
    return [_serialize(d) for d in cursor]


def get_by_id(submission_id: str) -> Optional[dict[str, Any]]:
    col = _collection()

    try:
        oid = _oid(submission_id)
    except Exception:
        return None

    doc = col.find_one({"_id": oid})
    return _serialize(doc) if doc else None


def list_all(limit: int = 50, status: Optional[str] = None) -> list[dict[str, Any]]:
    col = _collection()

    query: dict[str, Any] = {}
    if status:
        query["status"] = str(status).strip().lower()

    cursor = (
        col.find(query)
        .sort("created_at", -1)
        .limit(int(limit))
    )
    return [_serialize(d) for d in cursor]


def update_status(
    *,
    submission_id: str,
    new_status: str,
    reviewed_by: str,
    review_notes: str = "",
    approval_notes: str = "",
    rejection_reason: str = "",
) -> dict[str, Any]:
    col = _collection()

    try:
        oid = _oid(submission_id)
    except Exception:
        raise ValueError("Invalid submission id.")

    existing = col.find_one({"_id": oid})
    if not existing:
        raise ValueError("Intake submission not found.")

    status_normalized = str(new_status).strip().lower()
    if status_normalized not in REVIEWABLE_STATUSES:
        raise ValueError("Invalid intake submission status.")

    now = _now()

    update_doc: dict[str, Any] = {
        "status": status_normalized,
        "updated_at": now,
        "reviewed_by": reviewed_by,
        "review_notes": review_notes or "",
        "approval_notes": approval_notes or "",
        "rejection_reason": rejection_reason or "",
    }

    if status_normalized == "in_review":
        update_doc["review_started_at"] = now
        update_doc["review_locked"] = True

    elif status_normalized == "approved":
        update_doc["reviewed_at"] = now
        update_doc["review_locked"] = True

    elif status_normalized == "rejected":
        update_doc["reviewed_at"] = now
        update_doc["review_locked"] = False

    elif status_normalized == "submitted":
        update_doc["submitted_at"] = now
        update_doc["review_locked"] = True

    col.update_one({"_id": oid}, {"$set": update_doc})

    saved = col.find_one({"_id": oid})
    if not saved:
        raise RuntimeError("Failed to fetch updated intake submission.")

    return _serialize(saved)