from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from pymongo.collection import Collection

from app.database import get_database

COLLECTION = "intake_submissions"

PIPELINE_STATUSES = {
    "build_ready",
    "in_production",
    "qa_review",
    "client_review",
    "delivered",
    "archived",
}
LOCKED_STATUSES = {"submitted", "in_review", "approved"} | PIPELINE_STATUSES
REVIEWABLE_STATUSES = {"submitted", "in_review", "approved", "rejected"} | PIPELINE_STATUSES


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _oid(value: str) -> ObjectId:
    return ObjectId(value)


def _collection() -> Collection:
    db = get_database()
    return db[COLLECTION]


def _coerce_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None
    return None


def _normalize_submission_document(doc: dict[str, Any]) -> dict[str, Any]:
    out = dict(doc)

    status = str(out.get("status") or "submitted").strip().lower()
    out["status"] = status

    out["review_locked"] = bool(
        out.get("review_locked")
        if out.get("review_locked") is not None
        else status in LOCKED_STATUSES
    )

    out["household"] = out.get("household") or {}
    out["family_map"] = out.get("family_map") or {}
    out["uploads"] = out.get("uploads") or {}
    out["consent"] = out.get("consent") or {}
    out["review"] = out.get("review") or {}

    out["submitted_at"] = _coerce_datetime(
        out.get("submitted_at") or out.get("created_at")
    )
    out["review_started_at"] = _coerce_datetime(out.get("review_started_at"))
    out["reviewed_at"] = _coerce_datetime(out.get("reviewed_at"))
    out["provisioned_at"] = _coerce_datetime(out.get("provisioned_at"))

    out["reviewed_by"] = out.get("reviewed_by")
    out["review_notes"] = out.get("review_notes") or ""
    out["approval_notes"] = out.get("approval_notes") or ""
    out["rejection_reason"] = out.get("rejection_reason") or ""

    out["family_root_id"] = out.get("family_root_id")
    out["household_id"] = out.get("household_id")
    out["project_id"] = out.get("project_id")
    out["provisioned_by"] = out.get("provisioned_by")
    out["production_notes"] = out.get("production_notes") or ""

    out["created_at"] = _coerce_datetime(out.get("created_at")) or _now()
    out["updated_at"] = _coerce_datetime(out.get("updated_at")) or out["created_at"]

    return out


def _serialize(doc: dict[str, Any]) -> dict[str, Any]:
    out = _normalize_submission_document(doc)

    out["id"] = str(out.pop("_id"))

    if "user_id" in out and isinstance(out["user_id"], ObjectId):
        out["user_id"] = str(out["user_id"])

    return out


def create_intake_submission(
    *,
    user_id: str,
    email: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    col = _collection()
    now = _now()

    latest = col.find_one(
        {"user_id": _oid(user_id)},
        sort=[("created_at", -1)],
    )

    if latest:
        latest_normalized = _normalize_submission_document(latest)
        if str(latest_normalized.get("status", "")).lower() in LOCKED_STATUSES:
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
        "family_root_id": None,
        "household_id": None,
        "project_id": None,
        "provisioned_at": None,
        "provisioned_by": None,
        "production_notes": "",
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

    if status_normalized == "submitted":
        update_doc["submitted_at"] = now
        update_doc["review_locked"] = True
    elif status_normalized == "in_review":
        update_doc["review_started_at"] = now
        update_doc["review_locked"] = True
    elif status_normalized == "approved":
        update_doc["reviewed_at"] = now
        update_doc["review_locked"] = True
    elif status_normalized == "rejected":
        update_doc["reviewed_at"] = now
        update_doc["review_locked"] = False
    elif status_normalized in PIPELINE_STATUSES:
        update_doc["review_locked"] = True

    col.update_one({"_id": oid}, {"$set": update_doc})

    saved = col.find_one({"_id": oid})
    if not saved:
        raise RuntimeError("Failed to fetch updated intake submission.")

    return _serialize(saved)