# app/services/intake_submission_service.py

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Any

from bson import ObjectId
from pymongo.collection import Collection

from app.database import get_database

COLLECTION = "intake_submissions"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _oid(value: str) -> ObjectId:
    return ObjectId(value)


def _serialize(doc: dict[str, Any]) -> dict[str, Any]:
    """Mongo -> JSON-safe"""
    out = dict(doc)
    out["id"] = str(out.pop("_id"))
    # normalize common ids
    if "user_id" in out and isinstance(out["user_id"], ObjectId):
        out["user_id"] = str(out["user_id"])
    return out


def create_intake_submission(
    *,
    user_id: str,
    email: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Create a submitted intake record.

    payload expected keys:
      - package_slug (str)
      - package_name (str)
      - household (dict)
      - family_map (dict)
      - review (dict)
      - uploads (dict) OPTIONAL
      - consent (dict) OPTIONAL
    """
    db = get_database()
    col: Collection = db[COLLECTION]

    now = _now()

    record: dict[str, Any] = {
        "user_id": _oid(user_id),
        "email": email,
        "package_slug": payload["package_slug"],
        "package_name": payload["package_name"],
        "status": "submitted",
        "household": payload["household"],
        "family_map": payload["family_map"],
        # ✅ NEW: optional steps stored if provided
        "uploads": payload.get("uploads", {}) or {},
        "consent": payload.get("consent", {}) or {},
        "review": payload["review"],
        "created_at": now,
        "updated_at": now,
    }

    result = col.insert_one(record)

    saved = col.find_one({"_id": result.inserted_id})
    if not saved:
        # This should basically never happen, but it makes type-checkers happy
        # and gives a real error if Mongo ever fails to return the record.
        raise RuntimeError("Failed to fetch saved intake submission after insert.")

    return _serialize(saved)


def get_latest_for_user(user_id: str) -> Optional[dict[str, Any]]:
    db = get_database()
    col: Collection = db[COLLECTION]

    doc = col.find_one(
        {"user_id": _oid(user_id)},
        sort=[("created_at", -1)],
    )
    return _serialize(doc) if doc else None


def list_for_user(user_id: str, limit: int = 10) -> list[dict[str, Any]]:
    db = get_database()
    col: Collection = db[COLLECTION]

    cursor = (
        col.find({"user_id": _oid(user_id)})
        .sort("created_at", -1)
        .limit(int(limit))
    )
    return [_serialize(d) for d in cursor]


def get_by_id(submission_id: str) -> Optional[dict[str, Any]]:
    db = get_database()
    col: Collection = db[COLLECTION]

    try:
        oid = _oid(submission_id)
    except Exception:
        return None

    doc = col.find_one({"_id": oid})
    return _serialize(doc) if doc else None