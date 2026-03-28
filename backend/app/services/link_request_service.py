from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

from app.database import get_database
from app.schemas.link_request import LinkRequestCreate


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def _normalize_id(value: Any) -> str:
    return str(value or "").strip()


def list_link_requests() -> list[dict]:
    db = get_database()
    if db is None:
        return []

    return list(db.link_requests.find().sort("created_at", -1))


def create_link_request(
    payload: LinkRequestCreate,
    *,
    requested_by: str,
    requested_by_user_id: str | None = None,
) -> dict:
    db = get_database()
    data = payload.model_dump()
    data["status"] = "pending"
    data["requested_by"] = str(requested_by or "").strip() or "Unknown User"
    data["requested_by_user_id"] = (
        str(requested_by_user_id).strip() if requested_by_user_id else None
    )
    data["created_at"] = _utcnow_iso()
    data["updated_at"] = data["created_at"]

    if db is None:
        data["_id"] = "local-link-request-preview"
        return data

    existing = db.link_requests.find_one(
        {
            "source_household_id": data["source_household_id"],
            "target_household_id": data["target_household_id"],
            "source_key": data["source_key"],
            "target_key": data["target_key"],
            "status": "pending",
        }
    )
    if existing is not None:
        return existing

    result = db.link_requests.insert_one(data)
    data["_id"] = result.inserted_id
    return data


def get_link_request_by_id(request_id: str) -> dict | None:
    db = get_database()
    if db is None:
        return None

    try:
        return db.link_requests.find_one({"_id": ObjectId(request_id)})
    except Exception:
        return None


def approve_link_request(
    request_id: str,
    approved_by: str,
    approval_notes: str | None = None,
) -> dict | None:
    db = get_database()
    if db is None:
        return None

    try:
      object_id = ObjectId(request_id)
    except Exception:
      return None

    request = db.link_requests.find_one({"_id": object_id})
    if request is None:
        return None

    db.link_requests.update_one(
        {"_id": object_id},
        {
            "$set": {
                "status": "approved",
                "approved_by": approved_by,
                "approved_at": _utcnow_iso(),
                "approval_notes": approval_notes,
                "updated_at": _utcnow_iso(),
            }
        },
    )

    existing_link = db.household_links.find_one(
        {
            "$or": [
                {
                    "source_household_id": request["source_household_id"],
                    "target_household_id": request["target_household_id"],
                },
                {
                    "source_household_id": request["target_household_id"],
                    "target_household_id": request["source_household_id"],
                },
            ]
        }
    )

    if existing_link is None:
        household_link = {
            "source_household_id": request["source_household_id"],
            "target_household_id": request["target_household_id"],
            "relationship_type": "linked_household",
            "link_status": "approved",
            "linked_by_key": request["source_key"],
            "source_key": request["source_key"],
            "target_key": request["target_key"],
            "created_at": _utcnow_iso(),
            "updated_at": _utcnow_iso(),
        }
        db.household_links.insert_one(household_link)

    return db.link_requests.find_one({"_id": object_id})


def reject_link_request(
    request_id: str,
    rejected_by: str,
    rejection_notes: str | None = None,
) -> dict | None:
    db = get_database()
    if db is None:
        return None

    try:
        object_id = ObjectId(request_id)
    except Exception:
        return None

    request = db.link_requests.find_one({"_id": object_id})
    if request is None:
        return None

    db.link_requests.update_one(
        {"_id": object_id},
        {
            "$set": {
                "status": "rejected",
                "rejected_by": rejected_by,
                "rejected_at": _utcnow_iso(),
                "rejection_notes": rejection_notes,
                "updated_at": _utcnow_iso(),
            }
        },
    )

    return db.link_requests.find_one({"_id": object_id})