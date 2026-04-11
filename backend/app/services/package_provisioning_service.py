from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

from app.core.package_mapping import resolve_package_identity
from app.database import get_database
from app.services.mint_policy_service import describe_project_mint_eligibility
from app.services.project_entitlement_service import get_project_entitlement, upsert_project_entitlement

logger = logging.getLogger(__name__)

PAID_ORDER_STATUSES = {"paid", "succeeded", "complete", "completed"}
BUILD_READY_STATUSES = {"build_ready", "in_production", "qa_review", "client_review", "delivered", "archived"}
APPROVED_PHASES = {"intake_approved", "build_started", "quality_review", "client_review", "delivery_complete", "delivered", "archived"}


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _normalize_email(value: Any) -> str:
    return _normalize(value).lower()


def _now() -> datetime:
    return datetime.now(UTC)


def _db():
    db = get_database()
    if db is None:
        raise ValueError("Database is not connected.")
    return db


def _to_object_id(value: Any) -> ObjectId | None:
    normalized = _normalize(value)
    if normalized and ObjectId.is_valid(normalized):
        return ObjectId(normalized)
    if isinstance(value, ObjectId):
        return value
    return None


def _project_identity_candidates(project_id: str) -> list[Any]:
    values: list[Any] = [project_id]
    oid = _to_object_id(project_id)
    if oid is not None:
        values.append(oid)
    return values


def _is_paid_package_order(order: dict[str, Any] | None) -> bool:
    if not isinstance(order, dict):
        return False
    item_type = _normalize(order.get("item_type") or "package").lower()
    status = _normalize(order.get("status")).lower()
    return item_type == "package" and status in PAID_ORDER_STATUSES


def _is_approved_build_ready_project(project: dict[str, Any] | None) -> bool:
    if not isinstance(project, dict):
        return False
    status = _normalize(project.get("status")).lower()
    phase = _normalize(project.get("phase")).lower()
    return status in BUILD_READY_STATUSES or phase in APPROVED_PHASES


def _normalize_order_document(order: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    identity = resolve_package_identity(
        order.get("package_slug") or order.get("package_code"),
        package_name=order.get("package_name"),
    )
    updates: dict[str, Any] = {
        "package_code": identity["package_code"],
        "package_slug": identity["package_slug"],
        "package_name": identity["display_name"],
    }
    unknown = not bool(identity.get("known"))
    if unknown:
        logger.warning("Unknown package value encountered while normalizing an order document.")
    changed = False
    for key, value in updates.items():
        if _normalize(order.get(key)) != _normalize(value):
            changed = True
            order[key] = value
    if changed:
        _db()["orders"].update_one({"_id": order["_id"]}, {"$set": updates})
    return identity, changed


def _normalize_project_document(
    project: dict[str, Any],
    *,
    preferred_package_value: Any = "",
    preferred_package_name: Any = "",
) -> tuple[dict[str, Any], bool]:
    identity = resolve_package_identity(
        preferred_package_value
        or project.get("package_slug")
        or project.get("package_code")
        or project.get("package_type"),
        package_name=preferred_package_name or project.get("package_name"),
    )
    lane = identity.get("lane") or _normalize(project.get("project_lane")) or "unknown"
    updates: dict[str, Any] = {
        "package_code": identity["package_code"],
        "package_slug": identity["package_slug"],
        "package_type": identity["package_code"],
        "package_name": identity["display_name"],
        "project_lane": lane,
        "updated_at": _now(),
    }
    unknown = not bool(identity.get("known"))
    if unknown:
        logger.warning("Unknown package value encountered while normalizing a project document.")
    changed = False
    for key, value in updates.items():
        if _normalize(project.get(key)) != _normalize(value):
            changed = True
            project[key] = value
    if changed:
        project_oid = _to_object_id(project.get("_id"))
        if project_oid is not None:
            _db()["projects"].update_one({"_id": project_oid}, {"$set": updates})
    return identity, changed


def _ensure_entitlement(
    *,
    project: dict[str, Any],
    package_code: str,
    package_lane: str,
    package_name: str,
    purchased_at: Any = None,
) -> bool:
    project_id = _normalize(project.get("_id") or project.get("id"))
    if not project_id:
        return False

    existing = get_project_entitlement(project_id) or {}
    user_id = _normalize(project.get("owner_user_id")) or _normalize(existing.get("user_id")) or "unknown"
    entitlement = upsert_project_entitlement(
        project_id=project_id,
        user_id=user_id,
        package_code=package_code,
        active_addons=list(existing.get("active_addons") or []),
        maintenance_plan=_normalize(existing.get("maintenance_plan")) or "none",
        purchased_at=purchased_at if isinstance(purchased_at, datetime) else None,
        delivered_at=existing.get("delivered_at"),
        status=_normalize(existing.get("status")) or "active",
    )
    if entitlement is not None:
        _db()["project_entitlements"].update_one(
            {"project_id": project_id},
            {"$set": {"package_lane": package_lane, "package_name": package_name, "updated_at": _now()}},
        )
    return entitlement is not None


def _find_matching_project_for_order(order: dict[str, Any], package_code: str) -> dict[str, Any] | None:
    db = _db()
    email = _normalize_email(order.get("email"))
    user_id_value = order.get("user_id")
    user_id_text = _normalize(user_id_value)
    user_id_oid = _to_object_id(user_id_value)
    query_filters: list[dict[str, Any]] = []
    if email:
        query_filters.append({"owner_email": email})
    if user_id_text:
        query_filters.append({"owner_user_id": user_id_text})
    if user_id_oid is not None:
        query_filters.append({"owner_user_id": str(user_id_oid)})
    if not query_filters:
        return None

    candidates = list(db["projects"].find({"$or": query_filters}).sort("updated_at", -1).limit(50))
    approved = [item for item in candidates if _is_approved_build_ready_project(item)]
    if not approved:
        return None
    for project in approved:
        project_identity = resolve_package_identity(project.get("package_slug") or project.get("package_code"))
        if _normalize(project_identity.get("package_code")) == _normalize(package_code):
            return project
    return approved[0] if approved else None


def _link_order_to_project(order: dict[str, Any], project: dict[str, Any]) -> bool:
    project_id = _normalize(project.get("_id") or project.get("id"))
    if not project_id:
        return False
    current = _normalize(order.get("project_id"))
    if current == project_id:
        return False
    value: Any = project_id
    oid = _to_object_id(project_id)
    if oid is not None:
        value = oid
    _db()["orders"].update_one({"_id": order["_id"]}, {"$set": {"project_id": value}})
    order["project_id"] = value
    return True


def auto_provision_paid_order(order: dict[str, Any]) -> dict[str, Any]:
    package_normalized = False
    lane_assigned = False
    order_linked = False
    entitlement_present = False
    mint_readiness_computed = False

    if not _is_paid_package_order(order):
        return {
            "package_normalized": False,
            "lane_assigned": False,
            "order_linked": False,
            "entitlement_present": False,
            "mint_readiness_computed": False,
        }

    identity, order_changed = _normalize_order_document(order)
    package_normalized = order_changed or bool(identity.get("known"))

    project: dict[str, Any] | None = None
    project_id = _normalize(order.get("project_id"))
    if project_id:
        project = _db()["projects"].find_one({"_id": {"$in": _project_identity_candidates(project_id)}})
        if project is None:
            project = _db()["projects"].find_one({"id": project_id})
    if project is None:
        project = _find_matching_project_for_order(order, _normalize(identity.get("package_code")))
    if project is None:
        return {
            "package_normalized": package_normalized,
            "lane_assigned": False,
            "order_linked": False,
            "entitlement_present": False,
            "mint_readiness_computed": False,
        }

    order_linked = _link_order_to_project(order, project)

    _, project_changed = _normalize_project_document(
        project,
        preferred_package_value=identity.get("package_slug") or identity.get("package_code"),
        preferred_package_name=identity.get("display_name"),
    )
    lane_assigned = project_changed or bool(_normalize(project.get("project_lane")))

    entitlement_present = _ensure_entitlement(
        project=project,
        package_code=_normalize(identity.get("package_code")),
        package_lane=_normalize(identity.get("lane")),
        package_name=_normalize(identity.get("display_name")),
        purchased_at=order.get("created_at"),
    )

    try:
        describe_project_mint_eligibility(project)
        mint_readiness_computed = True
    except Exception:
        mint_readiness_computed = False

    logger.info("auto_provision_paid_order completed.")

    return {
        "package_normalized": package_normalized,
        "lane_assigned": lane_assigned,
        "order_linked": order_linked,
        "entitlement_present": entitlement_present,
        "mint_readiness_computed": mint_readiness_computed,
    }


def auto_provision_paid_order_by_id(order_id: str) -> dict[str, Any]:
    oid = _to_object_id(order_id)
    if oid is None:
        raise ValueError("Order id is invalid.")
    order = _db()["orders"].find_one({"_id": oid})
    if order is None:
        raise ValueError("Order not found.")
    return auto_provision_paid_order(order)


def repair_missing_lanes(*, limit: int = 200) -> dict[str, Any]:
    """Repair projects with missing/unknown lane and return scan + repaired ids."""
    db = _db()
    repaired_project_ids: list[str] = []
    scanned = 0
    for project in db["projects"].find({"$or": [{"project_lane": {"$exists": False}}, {"project_lane": ""}, {"project_lane": "unknown"}, {"project_lane": None}]}).limit(max(1, min(limit, 1000))):
        scanned += 1
        _, changed = _normalize_project_document(project)
        if changed:
            repaired_project_ids.append(_normalize(project.get("_id")))
    return {"scanned": scanned, "repaired_project_ids": repaired_project_ids}


def link_unlinked_paid_orders(*, limit: int = 200) -> dict[str, Any]:
    """Link unlinked paid package orders and return scan + linked order ids."""
    db = _db()
    linked_order_ids: list[str] = []
    processed = 0
    cursor = db["orders"].find(
        {
            "item_type": "package",
            "status": {"$in": list(PAID_ORDER_STATUSES)},
            "$or": [{"project_id": {"$exists": False}}, {"project_id": None}, {"project_id": ""}],
        }
    ).sort("created_at", -1).limit(max(1, min(limit, 1000)))
    for order in cursor:
        processed += 1
        result = auto_provision_paid_order(order)
        if result.get("order_linked"):
            linked_order_ids.append(_normalize(order.get("_id")))
    return {"scanned": processed, "linked_order_ids": linked_order_ids}


def repair_missing_entitlements(*, limit: int = 200) -> dict[str, Any]:
    """Backfill missing project entitlements and return scan + repaired project ids."""
    db = _db()
    entitlement_project_ids = {
        _normalize(item.get("project_id"))
        for item in db["project_entitlements"].find({}, {"project_id": 1})
        if _normalize(item.get("project_id"))
    }
    repaired_project_ids: list[str] = []
    processed = 0
    for project in db["projects"].find({}).sort("updated_at", -1).limit(max(1, min(limit, 1000))):
        project_id = _normalize(project.get("_id"))
        if not project_id or project_id in entitlement_project_ids:
            continue
        processed += 1
        identity, _ = _normalize_project_document(project)
        order = db["orders"].find_one(
            {
                "item_type": "package",
                "status": {"$in": list(PAID_ORDER_STATUSES)},
                "$or": [
                    {"project_id": {"$in": _project_identity_candidates(project_id)}},
                    {"email": _normalize_email(project.get("owner_email"))},
                ],
            },
            sort=[("created_at", -1)],
        )
        ensured = _ensure_entitlement(
            project=project,
            package_code=_normalize(identity.get("package_code")),
            package_lane=_normalize(identity.get("lane")),
            package_name=_normalize(identity.get("display_name")),
            purchased_at=(order or {}).get("created_at"),
        )
        if ensured:
            repaired_project_ids.append(project_id)
    return {"scanned": processed, "repaired_project_ids": repaired_project_ids}
