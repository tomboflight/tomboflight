from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

from app.core.role_catalog import normalize_project_member_role
from app.core.state_catalog import ACTIVE_OR_UNSET_RECORD_STATES, is_active_record_state
from app.database import get_database



def _now() -> datetime:
    return datetime.now(UTC)



def _normalize_value(value: Any) -> str:
    return str(value or "").strip()



def _normalize_email(value: Any) -> str:
    return _normalize_value(value).lower()



def _project_id(project: dict[str, Any] | str) -> str:
    if isinstance(project, dict):
        return _normalize_value(project.get("_id") or project.get("id"))
    return _normalize_value(project)



def _collection():
    db = get_database()
    if db is None:
        return None
    return db["project_members"]



def list_accessible_project_ids(
    *,
    user_id: str = "",
    email: str = "",
    active_only: bool = True,
) -> list[str]:
    collection = _collection()
    normalized_user_id = _normalize_value(user_id)
    normalized_email = _normalize_email(email)
    if collection is None or (not normalized_user_id and not normalized_email):
        return []

    filters: list[dict[str, Any]] = []
    if normalized_user_id:
        filters.append({"user_id": normalized_user_id})
    if normalized_email:
        filters.append({"email": normalized_email})

    query: dict[str, Any] = {"$or": filters}
    if active_only:
        query["status"] = {"$in": sorted(ACTIVE_OR_UNSET_RECORD_STATES)}

    seen: set[str] = set()
    project_ids: list[str] = []
    for membership in collection.find(query, {"project_id": 1}).sort("updated_at", -1):
        project_id = _normalize_value(membership.get("project_id"))
        if project_id and project_id not in seen:
            seen.add(project_id)
            project_ids.append(project_id)
    return project_ids



def get_project_member(
    project_id: str,
    *,
    user_id: str = "",
    email: str = "",
    active_only: bool = True,
) -> dict[str, Any] | None:
    collection = _collection()
    normalized_project_id = _normalize_value(project_id)
    normalized_user_id = _normalize_value(user_id)
    normalized_email = _normalize_email(email)
    if collection is None or not normalized_project_id:
        return None

    filters: list[dict[str, Any]] = []
    if normalized_user_id:
        filters.append({"user_id": normalized_user_id})
    if normalized_email:
        filters.append({"email": normalized_email})
    if not filters:
        return None

    query: dict[str, Any] = {"project_id": normalized_project_id, "$or": filters}
    membership = collection.find_one(query, sort=[("updated_at", -1), ("created_at", -1)])
    if membership is None:
        return None
    if active_only and not is_active_record_state(membership.get("status") or "active"):
        return None
    return membership



def get_project_access_snapshot(
    project: dict[str, Any] | None,
    *,
    user_id: str = "",
    email: str = "",
) -> dict[str, Any]:
    normalized_user_id = _normalize_value(user_id)
    normalized_email = _normalize_email(email)
    project_id = _project_id(project or {})
    owner_user_id = _normalize_value((project or {}).get("owner_user_id"))
    owner_email = _normalize_email((project or {}).get("owner_email"))

    membership = None
    if project_id and (normalized_user_id or normalized_email):
        membership = get_project_member(
            project_id,
            user_id=normalized_user_id,
            email=normalized_email,
            active_only=True,
        )

    if membership is not None:
        return {
            "project_id": project_id,
            "accessible": True,
            "via": "project_members",
            "member_role": normalize_project_member_role(membership.get("member_role"), default="viewer"),
            "member_status": _normalize_value(membership.get("status") or "active"),
            "owner_user_id": owner_user_id,
            "owner_email": owner_email,
            "membership": membership,
        }

    owner_access = bool(
        (normalized_user_id and normalized_user_id == owner_user_id)
        or (normalized_email and normalized_email == owner_email)
    )
    return {
        "project_id": project_id,
        "accessible": owner_access,
        "via": "owner_fallback" if owner_access else "",
        "member_role": "owner" if owner_access else "",
        "member_status": "active" if owner_access else "",
        "owner_user_id": owner_user_id,
        "owner_email": owner_email,
        "membership": None,
    }



def has_project_access(
    project: dict[str, Any] | None,
    *,
    user_id: str = "",
    email: str = "",
) -> bool:
    return bool(
        get_project_access_snapshot(project, user_id=user_id, email=email).get("accessible")
    )



def ensure_project_member(
    *,
    project_id: str,
    user_id: str = "",
    email: str = "",
    member_role: str = "viewer",
    status: str = "active",
) -> dict[str, Any] | None:
    collection = _collection()
    normalized_project_id = _normalize_value(project_id)
    normalized_user_id = _normalize_value(user_id)
    normalized_email = _normalize_email(email)
    if not normalized_project_id or collection is None:
        return None
    if not normalized_user_id and not normalized_email:
        return None

    role_code = normalize_project_member_role(member_role, default="viewer")
    query_filters: list[dict[str, Any]] = []
    if normalized_user_id:
        query_filters.append({"user_id": normalized_user_id})
    if normalized_email:
        query_filters.append({"email": normalized_email})

    query: dict[str, Any] = {"project_id": normalized_project_id, "$or": query_filters}
    now = _now()
    update: dict[str, Any] = {
        "$set": {
            "project_id": normalized_project_id,
            "user_id": normalized_user_id or None,
            "email": normalized_email or None,
            "member_role": role_code,
            "status": _normalize_value(status) or "active",
            "updated_at": now,
        },
        "$setOnInsert": {"created_at": now},
    }
    collection.update_one(query, update, upsert=True)
    return get_project_member(
        normalized_project_id,
        user_id=normalized_user_id,
        email=normalized_email,
        active_only=False,
    )



def ensure_project_owner_membership(project: dict[str, Any]) -> dict[str, Any] | None:
    return ensure_project_member(
        project_id=_project_id(project),
        user_id=_normalize_value(project.get("owner_user_id")),
        email=_normalize_email(project.get("owner_email")),
        member_role="owner",
        status="active",
    )
