"""Client review service.

Records customer approval and revision-request decisions for projects
in client_review state.  No mint, certificate, delivery, Stripe, or
email side effects are triggered here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from app.database import get_database


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _oid(value: str) -> ObjectId:
    return ObjectId(value)


REVIEW_COLLECTION = "client_reviews"


def _serialize(doc: dict[str, Any]) -> dict[str, Any]:
    out = dict(doc)
    out["id"] = str(out.pop("_id", ""))
    for field in ("user_id", "project_id", "family_id"):
        if field in out and isinstance(out[field], ObjectId):
            out[field] = str(out[field])
    return out


def get_latest_review(project_id: str) -> dict[str, Any] | None:
    """Return the most recent client review record for a project, or None."""
    db = get_database()
    if db is None:
        return None
    doc = (
        db[REVIEW_COLLECTION]
        .find({"project_id": project_id})
        .sort("created_at", -1)
        .limit(1)
    )
    result = list(doc)
    if not result:
        return None
    return _serialize(result[0])


def get_review_by_id(review_id: str) -> dict[str, Any] | None:
    db = get_database()
    if db is None:
        return None
    if not ObjectId.is_valid(review_id):
        return None
    doc = db[REVIEW_COLLECTION].find_one({"_id": _oid(review_id)})
    return _serialize(doc) if doc else None


def create_approval(
    *,
    project_id: str,
    user_id: str,
    user_email: str,
    version: str,
    comments: str,
    public_safe_consent: bool,
) -> dict[str, Any]:
    """Record a customer approval decision.

    Does NOT issue a certificate, trigger delivery, or modify the mint record.
    """
    db = get_database()
    if db is None:
        raise RuntimeError("Database is not connected.")

    now = _now()
    payload: dict[str, Any] = {
        "project_id": project_id,
        "user_id": user_id,
        "user_email": user_email.strip().lower(),
        "decision": "approved",
        "version": _normalize(version) or "1",
        "comments": _normalize(comments),
        "public_safe_consent": bool(public_safe_consent),
        "created_at": now,
        "updated_at": now,
    }

    result = db[REVIEW_COLLECTION].insert_one(payload)
    payload["_id"] = result.inserted_id
    return _serialize(payload)


def create_revision_request(
    *,
    project_id: str,
    user_id: str,
    user_email: str,
    version: str,
    comments: str,
) -> dict[str, Any]:
    """Record a customer revision request.

    Does NOT change project workflow state, mint records, or billing.
    The production team must read this record and act on it manually.
    """
    db = get_database()
    if db is None:
        raise RuntimeError("Database is not connected.")

    if not _normalize(comments):
        raise ValueError("Revision comments are required when requesting revisions.")

    now = _now()
    payload: dict[str, Any] = {
        "project_id": project_id,
        "user_id": user_id,
        "user_email": user_email.strip().lower(),
        "decision": "revision_requested",
        "version": _normalize(version) or "1",
        "comments": _normalize(comments),
        "public_safe_consent": False,
        "created_at": now,
        "updated_at": now,
    }

    result = db[REVIEW_COLLECTION].insert_one(payload)
    payload["_id"] = result.inserted_id
    return _serialize(payload)
