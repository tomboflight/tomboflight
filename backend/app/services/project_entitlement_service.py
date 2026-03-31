from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, cast

from pymongo.collection import Collection

from app.database import get_database
from app.services.entitlement_service import (
    compute_upgrade_quote,
    resolve_project_entitlements,
)


def _collection() -> Collection[dict[str, Any]]:
    db = get_database()
    return cast(Collection[dict[str, Any]], db["project_entitlements"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _serialize(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if not document:
        return None

    package_code = str(document.get("package_code") or "").strip()
    active_addons = list(document.get("active_addons", []))

    try:
        resolved = resolve_project_entitlements(package_code, active_addons)
    except Exception:
        resolved = document.get("resolved_entitlements") or {}

    return {
        "id": str(document.get("_id")),
        "project_id": document.get("project_id"),
        "user_id": document.get("user_id"),
        "package_code": package_code or document.get("package_code"),
        "package_name": document.get("package_name") or resolved.get("display_name"),
        "package_lane": document.get("package_lane"),
        "active_addons": active_addons,
        "maintenance_plan": document.get("maintenance_plan"),
        "maintenance_status": document.get("maintenance_status"),
        "maintenance_started_at": document.get("maintenance_started_at"),
        "maintenance_renews_at": document.get("maintenance_renews_at"),
        "delivered_at": document.get("delivered_at"),
        "status": document.get("status"),
        "resolved_entitlements": resolved,
        "created_at": document.get("created_at"),
        "updated_at": document.get("updated_at"),
    }


def _compute_maintenance_fields(
    maintenance_plan: str,
    delivered_at: datetime | None,
) -> tuple[str, datetime | None, datetime | None]:
    plan = str(maintenance_plan or "").strip().lower()

    if (
        plan in {"", "not_started", "pending_delivery", "unselected"}
        or delivered_at is None
    ):
        return "not_started", None, None

    if plan == "lifetime":
        return "active", delivered_at, None

    if plan in {"annual", "yearly"}:
        return "active", delivered_at, delivered_at + timedelta(days=365)

    return "active", delivered_at, delivered_at + timedelta(days=30)


def upsert_project_entitlement(
    *,
    project_id: str,
    user_id: str,
    package_code: str,
    active_addons: list[str] | None = None,
    maintenance_plan: str = "not_started",
    delivered_at: datetime | None = None,
    status: str = "active",
) -> dict[str, Any] | None:
    collection = _collection()

    resolved = resolve_project_entitlements(package_code, active_addons or [])
    maintenance_status, maintenance_started_at, maintenance_renews_at = (
        _compute_maintenance_fields(maintenance_plan, delivered_at)
    )

    existing = cast(
        dict[str, Any] | None,
        collection.find_one({"project_id": project_id}),
    )
    now = _utcnow()

    document: dict[str, Any] = {
        "project_id": project_id,
        "user_id": user_id,
        "package_code": resolved.get("package_code") or package_code,
        "package_name": resolved.get("display_name") or package_code,
        "package_lane": resolved.get("package_lane"),
        "active_addons": active_addons or [],
        "maintenance_plan": maintenance_plan,
        "maintenance_status": maintenance_status,
        "maintenance_started_at": maintenance_started_at,
        "maintenance_renews_at": maintenance_renews_at,
        "delivered_at": delivered_at,
        "status": status,
        "resolved_entitlements": resolved,
        "updated_at": now,
    }

    if existing:
        collection.update_one(
            {"project_id": project_id},
            {"$set": document},
        )
    else:
        document["created_at"] = now
        collection.insert_one(document)

    saved = cast(
        dict[str, Any] | None,
        collection.find_one({"project_id": project_id}),
    )
    return _serialize(saved)


def get_project_entitlement(project_id: str) -> dict[str, Any] | None:
    collection = _collection()
    document = cast(
        dict[str, Any] | None,
        collection.find_one({"project_id": project_id}),
    )
    return _serialize(document)


def list_user_project_entitlements(
    user_id: str,
    *,
    active_only: bool = True,
) -> list[dict[str, Any]]:
    collection = _collection()

    query: dict[str, Any] = {"user_id": user_id}
    if active_only:
        query["status"] = "active"

    cursor = collection.find(query).sort("updated_at", -1)

    return [
        serialized
        for serialized in (_serialize(cast(dict[str, Any], document)) for document in cursor)
        if serialized is not None
    ]


def list_project_entitlements(
    *,
    active_only: bool = False,
    limit: int = 100,
    search: str = "",
) -> list[dict[str, Any]]:
    collection = _collection()

    normalized_search = str(search or "").strip()
    query: dict[str, Any] = {}
    if active_only:
        query["status"] = "active"

    if normalized_search:
        regex = {"$regex": re.escape(normalized_search), "$options": "i"}
        query["$or"] = [
            {"project_id": regex},
            {"user_id": regex},
            {"package_code": regex},
            {"package_name": regex},
            {"package_lane": regex},
        ]

    cursor = collection.find(query).sort("updated_at", -1).limit(max(1, min(limit, 500)))

    return [
        serialized
        for serialized in (_serialize(cast(dict[str, Any], document)) for document in cursor)
        if serialized is not None
    ]


def get_upgrade_quote_for_project(
    project_id: str,
    to_package_code: str,
) -> dict[str, Any]:
    current = get_project_entitlement(project_id)
    if not current:
        raise ValueError("Project entitlement not found.")

    quote = compute_upgrade_quote(current["package_code"], to_package_code)
    quote["project_id"] = project_id
    return quote
