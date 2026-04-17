from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.database import get_database



def _normalize(value: Any) -> str:
    return str(value or "").strip()



def _normalize_email(value: Any) -> str:
    return _normalize(value).lower()



def _now() -> datetime:
    return datetime.now(UTC)



def _project_members_collection():
    db = get_database()
    if db is None:
        return None
    return db["project_members"]



def get_project_member(project_id: str, user_id: str) -> dict[str, Any] | None:
    collection = _project_members_collection()
    normalized_project_id = _normalize(project_id)
    normalized_user_id = _normalize(user_id)
    if collection is None or not normalized_project_id or not normalized_user_id:
        return None
    return collection.find_one(
        {
            "project_id": normalized_project_id,
            "user_id": normalized_user_id,
            "status": {"$ne": "suspended"},
        }
    )



def list_project_members(project_id: str) -> list[dict[str, Any]]:
    collection = _project_members_collection()
    normalized_project_id = _normalize(project_id)
    if collection is None or not normalized_project_id:
        return []
    return list(collection.find({"project_id": normalized_project_id}).sort("created_at", 1))



def is_project_member(project_id: str, user_id: str, user_email: str = "") -> bool:
    collection = _project_members_collection()
    normalized_project_id = _normalize(project_id)
    normalized_user_id = _normalize(user_id)
    normalized_email = _normalize_email(user_email)
    if collection is None or not normalized_project_id:
        return False

    filters: list[dict[str, Any]] = []
    if normalized_user_id:
        filters.append({"user_id": normalized_user_id})
    if normalized_email:
        filters.append({"user_email": normalized_email})

    if not filters:
        return False

    return (
        collection.find_one(
            {
                "project_id": normalized_project_id,
                "$or": filters,
                "status": {"$ne": "suspended"},
            },
            {"_id": 1},
        )
        is not None
    )



def upsert_project_owner_member(*, project_id: str, user_id: str, user_email: str) -> None:
    collection = _project_members_collection()
    normalized_project_id = _normalize(project_id)
    normalized_user_id = _normalize(user_id)
    normalized_email = _normalize_email(user_email)
    if (
        collection is None
        or not normalized_project_id
        or not normalized_user_id
        or not normalized_email
    ):
        return

    now = _now()
    collection.update_one(
        {
            "project_id": normalized_project_id,
            "user_id": normalized_user_id,
        },
        {
            "$set": {
                "project_id": normalized_project_id,
                "user_id": normalized_user_id,
                "user_email": normalized_email,
                "role": "owner",
                "status": "active",
                "updated_at": now,
            },
            "$setOnInsert": {
                "created_at": now,
                "joined_at": now,
                "invited_by": normalized_user_id,
            },
        },
        upsert=True,
    )
