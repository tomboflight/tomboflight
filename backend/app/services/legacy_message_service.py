from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast

from bson import ObjectId
from pymongo.collection import Collection

from app.database import get_database
from app.schemas.legacy_message import LegacyMessageCreate, LegacyMessageUpdate


def _col(name: str) -> Collection[dict[str, Any]]:
    db = get_database()
    return cast(Collection[dict[str, Any]], db[name])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _str_id(value: Any) -> str:
    if isinstance(value, ObjectId):
        return str(value)
    return str(value or "").strip()


def _find_by_id(message_id: str) -> dict[str, Any] | None:
    col = _col("legacy_messages")
    if ObjectId.is_valid(message_id):
        doc = col.find_one({"_id": ObjectId(message_id)})
    else:
        doc = col.find_one({"_id": message_id})
    return cast(dict[str, Any] | None, doc)


def _serialize(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    if not doc:
        return None
    result = dict(doc)
    result["id"] = _str_id(doc.get("_id"))
    result.pop("_id", None)
    return result


def create_legacy_message(
    payload: LegacyMessageCreate,
    owner_user_id: str,
) -> dict[str, Any]:
    col = _col("legacy_messages")
    now = _now()
    doc: dict[str, Any] = {
        **payload.model_dump(),
        "owner_user_id": owner_user_id,
        "status": "draft",
        "created_at": now,
        "updated_at": now,
    }
    result = col.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _serialize(doc) or {}


def list_legacy_messages(project_id: str, owner_user_id: str) -> list[dict[str, Any]]:
    col = _col("legacy_messages")
    cursor = col.find({"project_id": project_id, "owner_user_id": owner_user_id}).sort("created_at", -1)
    return [_serialize(cast(dict[str, Any], doc)) for doc in cursor if doc]  # type: ignore[misc]


def get_legacy_message(message_id: str, requesting_user_id: str) -> dict[str, Any] | None:
    doc = _find_by_id(message_id)
    if not doc:
        return None

    owner = _str_id(doc.get("owner_user_id") or "")
    if owner == requesting_user_id:
        return _serialize(doc)

    # Allow released messages for named recipients
    status = str(doc.get("status") or "")
    named_recipients = list(doc.get("named_recipients") or [])
    if status == "active" and requesting_user_id in named_recipients:
        return _serialize(doc)

    raise PermissionError("Access denied to this message.")


def update_legacy_message(
    message_id: str,
    updates: LegacyMessageUpdate,
    requesting_user_id: str,
) -> dict[str, Any] | None:
    doc = _find_by_id(message_id)
    if not doc:
        raise ValueError("Legacy message not found.")

    owner = _str_id(doc.get("owner_user_id") or "")
    if owner != requesting_user_id:
        raise PermissionError("Only the owner can update this message.")

    current_status = str(doc.get("status") or "draft")
    if current_status != "draft":
        raise ValueError("Only draft messages can be updated.")

    update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
    update_data["updated_at"] = _now()

    col = _col("legacy_messages")
    if ObjectId.is_valid(message_id):
        col.update_one({"_id": ObjectId(message_id)}, {"$set": update_data})
    else:
        col.update_one({"_id": message_id}, {"$set": update_data})

    return _serialize(_find_by_id(message_id))


def delete_legacy_message(message_id: str, requesting_user_id: str) -> bool:
    doc = _find_by_id(message_id)
    if not doc:
        raise ValueError("Legacy message not found.")

    owner = _str_id(doc.get("owner_user_id") or "")
    if owner != requesting_user_id:
        raise PermissionError("Only the owner can delete this message.")

    current_status = str(doc.get("status") or "draft")
    if current_status != "draft":
        raise ValueError("Only draft messages can be deleted.")

    col = _col("legacy_messages")
    if ObjectId.is_valid(message_id):
        col.delete_one({"_id": ObjectId(message_id)})
    else:
        col.delete_one({"_id": message_id})
    return True


def activate_legacy_message(message_id: str, requesting_user_id: str) -> dict[str, Any] | None:
    doc = _find_by_id(message_id)
    if not doc:
        raise ValueError("Legacy message not found.")

    owner = _str_id(doc.get("owner_user_id") or "")
    if owner != requesting_user_id:
        raise PermissionError("Only the owner can activate this message.")

    current_status = str(doc.get("status") or "draft")
    if current_status != "draft":
        raise ValueError("Only draft messages can be activated.")

    col = _col("legacy_messages")
    now = _now()
    if ObjectId.is_valid(message_id):
        col.update_one({"_id": ObjectId(message_id)}, {"$set": {"status": "active", "updated_at": now}})
    else:
        col.update_one({"_id": message_id}, {"$set": {"status": "active", "updated_at": now}})

    return _serialize(_find_by_id(message_id))
