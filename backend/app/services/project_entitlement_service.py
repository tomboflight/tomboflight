from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, cast

from bson import ObjectId
from pymongo.collection import Collection
from pymongo.errors import OperationFailure

from app.core.package_catalog import get_package_control_profile
from app.core.package_mapping import resolve_package_identity
from app.database import get_database
from app.services.project_membership_service import list_accessible_project_ids
from app.services.entitlement_service import (
    compute_upgrade_quote,
    resolve_project_entitlements,
)

MAINTENANCE_START_DELAY_DAYS = 30
MAINTENANCE_MONTHLY_PERIOD_DAYS = 30


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
        "project_id": _normalize_identifier(document.get("project_id")),
        "user_id": _normalize_identifier(document.get("user_id")),
        "package_code": package_code or document.get("package_code"),
        "package_name": document.get("package_name") or resolved.get("display_name"),
        "package_lane": document.get("package_lane"),
        "active_addons": active_addons,
        "maintenance_plan": document.get("maintenance_plan"),
        "maintenance_status": document.get("maintenance_status"),
        "maintenance_scheduled_start_at": document.get("maintenance_scheduled_start_at"),
        "maintenance_started_at": document.get("maintenance_started_at"),
        "maintenance_renews_at": document.get("maintenance_renews_at"),
        "maintenance_current_period_start": document.get("maintenance_current_period_start"),
        "maintenance_current_period_end": document.get("maintenance_current_period_end"),
        "maintenance_stripe_subscription_id": document.get("maintenance_stripe_subscription_id"),
        "maintenance_stripe_customer_id": document.get("maintenance_stripe_customer_id"),
        "maintenance_stripe_status": document.get("maintenance_stripe_status"),
        "purchased_at": document.get("purchased_at"),
        "delivered_at": document.get("delivered_at"),
        "status": document.get("status"),
        "resolved_entitlements": resolved,
        "created_at": document.get("created_at"),
        "updated_at": document.get("updated_at"),
    }


def _normalize_identifier(value: Any) -> str:
    if isinstance(value, ObjectId):
        return str(value)
    return str(value or "").strip()


def _coerce_object_id(value: Any) -> ObjectId | None:
    if isinstance(value, ObjectId):
        return value
    normalized = str(value or "").strip()
    if ObjectId.is_valid(normalized):
        return ObjectId(normalized)
    return None


def _project_id_candidates(project_id: str) -> list[Any]:
    normalized = str(project_id or "").strip()
    candidates: list[Any] = []
    if normalized:
        candidates.append(normalized)
    oid = _coerce_object_id(normalized)
    if oid is not None:
        candidates.append(oid)
        oid_text = str(oid)
        candidates.append(f'ObjectId("{oid_text}")')
        candidates.append(f"ObjectId('{oid_text}')")
    return candidates


def _user_id_candidates(user_id: str) -> list[Any]:
    normalized = str(user_id or "").strip()
    candidates: list[Any] = []
    if normalized:
        candidates.append(normalized)
    oid = _coerce_object_id(normalized)
    if oid is not None:
        candidates.append(oid)
    return candidates


def _compute_maintenance_fields(
    maintenance_plan: str,
    purchased_at: datetime | None,
) -> tuple[str, datetime | None, datetime | None, datetime | None, datetime | None]:
    plan = str(maintenance_plan or "").strip().lower()
    if plan in {"annual"}:
        plan = "yearly"
    if plan in {"not_started", "pending_delivery", "unselected"}:
        plan = "none"

    if plan in {"", "none"}:
        return "not_started", None, None, None, None

    start_basis = purchased_at or _utcnow()
    scheduled_start = start_basis + timedelta(days=MAINTENANCE_START_DELAY_DAYS)
    now = _utcnow()
    if now < scheduled_start:
        return "scheduled", scheduled_start, None, None, None

    period_start = scheduled_start
    if plan == "yearly":
        period_end = period_start + timedelta(days=365)
    else:
        period_end = period_start + timedelta(days=MAINTENANCE_MONTHLY_PERIOD_DAYS)
    return "active", scheduled_start, period_start, period_end, period_end


def upsert_project_entitlement(
    *,
    project_id: str,
    user_id: str,
    package_code: str,
    active_addons: list[str] | None = None,
    maintenance_plan: str = "none",
    purchased_at: datetime | None = None,
    delivered_at: datetime | None = None,
    status: str = "active",
    maintenance_stripe_subscription_id: str | None = None,
    maintenance_stripe_customer_id: str | None = None,
    maintenance_stripe_status: str | None = None,
    maintenance_current_period_start: datetime | None = None,
    maintenance_current_period_end: datetime | None = None,
) -> dict[str, Any] | None:
    collection = _collection()
    project_oid = _coerce_object_id(project_id)
    user_oid = _coerce_object_id(user_id)
    if project_oid is None:
        raise ValueError("project_id must be a valid ObjectId.")
    if user_oid is None:
        raise ValueError("user_id must be a valid ObjectId.")

    identity = resolve_package_identity(package_code)
    canonical_package_code = str(identity.get("package_code") or package_code).strip()
    resolved = resolve_project_entitlements(canonical_package_code, active_addons or [])
    maintenance_defaults = get_package_control_profile(canonical_package_code) or {}
    normalized_plan = str(maintenance_plan or "").strip().lower() or str(
        maintenance_defaults.get("maintenance_default") or "none"
    )
    maintenance_status, maintenance_scheduled_start_at, maintenance_started_at, maintenance_renews_at, computed_period_end = (
        _compute_maintenance_fields(normalized_plan, purchased_at)
    )
    period_start = maintenance_started_at
    period_end = maintenance_current_period_end or computed_period_end

    existing = cast(
        dict[str, Any] | None,
        collection.find_one({"project_id": {"$in": _project_id_candidates(str(project_oid))}}),
    )
    now = _utcnow()

    document: dict[str, Any] = {
        "project_id": project_oid,
        "user_id": user_oid,
        "package_code": resolved.get("package_code") or canonical_package_code,
        "package_name": resolved.get("display_name") or identity.get("display_name") or canonical_package_code,
        "package_lane": resolved.get("package_lane") or identity.get("lane"),
        "active_addons": active_addons or [],
        "maintenance_plan": normalized_plan,
        "maintenance_status": maintenance_status,
        "maintenance_scheduled_start_at": maintenance_scheduled_start_at,
        "maintenance_started_at": maintenance_started_at,
        "maintenance_renews_at": maintenance_renews_at,
        "maintenance_current_period_start": maintenance_current_period_start or period_start,
        "maintenance_current_period_end": period_end,
        "maintenance_stripe_subscription_id": maintenance_stripe_subscription_id,
        "maintenance_stripe_customer_id": maintenance_stripe_customer_id,
        "maintenance_stripe_status": maintenance_stripe_status,
        "purchased_at": purchased_at,
        "delivered_at": delivered_at,
        "status": status,
        "resolved_entitlements": resolved,
        "updated_at": now,
    }

    if existing:
        collection.update_one(
            {"_id": existing["_id"]},
            {"$set": document},
        )
    else:
        document["created_at"] = now
        collection.insert_one(document)

    saved = cast(
        dict[str, Any] | None,
        collection.find_one({"project_id": {"$in": _project_id_candidates(str(project_oid))}}),
    )
    return _serialize(saved)


def get_project_entitlement(project_id: str) -> dict[str, Any] | None:
    collection = _collection()
    candidates = _project_id_candidates(project_id)
    if not candidates:
        return None
    document = cast(
        dict[str, Any] | None,
        collection.find_one({"project_id": {"$in": candidates}}),
    )
    return _serialize(document)


def list_user_project_entitlements(
    user_id: str,
    *,
    active_only: bool = True,
) -> list[dict[str, Any]]:
    collection = _collection()
    project_ids = list_accessible_project_ids(user_id=user_id)

    or_filters: list[dict[str, Any]] = []
    user_id_values = _user_id_candidates(user_id)
    if user_id_values:
        or_filters.append({"user_id": {"$in": user_id_values}})
    if project_ids:
        project_id_values: list[Any] = []
        for project_id in project_ids:
            for candidate in _project_id_candidates(project_id):
                if candidate not in project_id_values:
                    project_id_values.append(candidate)
        if project_id_values:
            or_filters.append({"project_id": {"$in": project_id_values}})

    if not or_filters:
        return []

    query: dict[str, Any] = {"$or": or_filters}
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
        search_filters: list[dict[str, Any]] = [
            {"package_code": regex},
            {"package_name": regex},
            {"package_lane": regex},
        ]
        oid = _coerce_object_id(normalized_search)
        if oid is not None:
            search_filters.extend(
                [
                    {"project_id": oid},
                    {"user_id": oid},
                ]
            )
        query["$or"] = search_filters

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


def update_project_entitlement_maintenance(
    *,
    project_id: str,
    maintenance_plan: str | None = None,
    maintenance_status: str | None = None,
    maintenance_scheduled_start_at: datetime | None = None,
    maintenance_started_at: datetime | None = None,
    maintenance_renews_at: datetime | None = None,
    maintenance_current_period_start: datetime | None = None,
    maintenance_current_period_end: datetime | None = None,
    maintenance_stripe_subscription_id: str | None = None,
    maintenance_stripe_customer_id: str | None = None,
    maintenance_stripe_status: str | None = None,
) -> dict[str, Any] | None:
    collection = _collection()
    candidates = _project_id_candidates(project_id)
    if not candidates:
        return None
    existing = cast(
        dict[str, Any] | None,
        collection.find_one({"project_id": {"$in": candidates}}),
    )
    if not existing:
        return None

    updates: dict[str, Any] = {"updated_at": _utcnow()}
    if maintenance_plan is not None:
        updates["maintenance_plan"] = maintenance_plan
    if maintenance_status is not None:
        updates["maintenance_status"] = maintenance_status
    if maintenance_scheduled_start_at is not None:
        updates["maintenance_scheduled_start_at"] = maintenance_scheduled_start_at
    if maintenance_started_at is not None:
        updates["maintenance_started_at"] = maintenance_started_at
    if maintenance_renews_at is not None:
        updates["maintenance_renews_at"] = maintenance_renews_at
    if maintenance_current_period_start is not None:
        updates["maintenance_current_period_start"] = maintenance_current_period_start
    if maintenance_current_period_end is not None:
        updates["maintenance_current_period_end"] = maintenance_current_period_end
    if maintenance_stripe_subscription_id is not None:
        updates["maintenance_stripe_subscription_id"] = maintenance_stripe_subscription_id
    if maintenance_stripe_customer_id is not None:
        updates["maintenance_stripe_customer_id"] = maintenance_stripe_customer_id
    if maintenance_stripe_status is not None:
        updates["maintenance_stripe_status"] = maintenance_stripe_status

    collection.update_one({"_id": existing["_id"]}, {"$set": updates})
    saved = cast(
        dict[str, Any] | None,
        collection.find_one({"_id": existing["_id"]}),
    )
    return _serialize(saved)


def ensure_project_entitlement_indexes() -> None:
    """Create indexes on the project_entitlements collection.

    project_id is queried on every workspace capability check.  Without an
    index the query performs a full collection scan, which causes API request
    timeouts as the collection grows.
    """
    collection = _collection()
    existing = collection.index_information()

    def _ensure_index(
        keys: list[tuple[str, int]],
        *,
        name: str,
        unique: bool = False,
        sparse: bool = False,
    ) -> None:
        if name in existing:
            return
        try:
            collection.create_index(keys, name=name, unique=unique, sparse=sparse)
        except OperationFailure:
            return

    _ensure_index([("project_id", 1)], name="project_id_1")
    _ensure_index([("project_id", 1), ("status", 1)], name="project_id_1_status_1")
    _ensure_index([("user_id", 1)], name="user_id_1")
    _ensure_index([("status", 1)], name="status_1")
