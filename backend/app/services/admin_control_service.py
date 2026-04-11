from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId

from app.config import settings
from app.core.package_mapping import resolve_package_identity
from app.core.package_catalog import get_package, get_package_control_profile, normalize_package_code
from app.database import get_database
from app.services.mint_policy_service import describe_project_mint_eligibility
from app.services.package_provisioning_service import (
    auto_provision_paid_order_by_id,
    link_unlinked_paid_orders,
    repair_missing_entitlements,
    repair_missing_lanes,
)
from app.services.project_entitlement_service import (
    get_project_entitlement,
    upsert_project_entitlement,
)
from app.services.workspace_access_service import count_workspace_uploads

ALLOWED_LANES = {"portrait", "household", "network", "organization"}
BUILD_READY_STATUSES = {"build_ready", "in_production", "qa_review", "client_review", "delivered", "archived"}
INTAKE_APPROVED_PHASES = {"intake_approved", "build_started", "quality_review", "client_review", "delivery_complete", "delivered", "archived"}
PAID_ORDER_STATUSES = {"paid", "succeeded", "complete", "completed"}
OBJECT_ID_WRAPPER_PATTERN = re.compile(r"""^ObjectId\((["']?)([0-9a-fA-F]{24})\1\)$""")


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


def _to_object_id(value: str) -> ObjectId | None:
    object_id_hex = _extract_object_id_hex(value)
    return ObjectId(object_id_hex) if object_id_hex else None


def _normalize_object_id(value: Any) -> str:
    if isinstance(value, ObjectId):
        return str(value)
    normalized = _normalize(value)
    object_id_hex = _extract_object_id_hex(normalized)
    return object_id_hex or normalized


def _extract_object_id_hex(value: Any) -> str | None:
    if isinstance(value, ObjectId):
        return str(value)
    normalized = _normalize(value)
    if not normalized:
        return None
    if ObjectId.is_valid(normalized):
        return str(ObjectId(normalized))
    wrapped = OBJECT_ID_WRAPPER_PATTERN.match(normalized)
    if wrapped and ObjectId.is_valid(wrapped.group(2)):
        return str(ObjectId(wrapped.group(2)))
    return None


def _coerce_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=UTC)
        except Exception:
            return None
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return None
        if candidate.endswith("Z"):
            candidate = f"{candidate[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        except ValueError:
            return None
    return None


def _project_by_id(project_id: str) -> dict[str, Any] | None:
    db = _db()
    oid = _to_object_id(project_id)
    if oid is not None:
        document = db["projects"].find_one({"_id": oid})
        if document is not None:
            return document
    return db["projects"].find_one({"id": project_id})


def _order_by_id(order_id: str) -> dict[str, Any] | None:
    db = _db()
    oid = _to_object_id(order_id)
    if oid is not None:
        return db["orders"].find_one({"_id": oid})
    return None


def _project_id_candidates(project_id: str) -> list[Any]:
    values: list[Any] = [project_id]
    oid = _to_object_id(project_id)
    if oid is not None:
        values.append(oid)
        oid_text = str(oid)
        values.append(f'ObjectId("{oid_text}")')
        values.append(f"ObjectId('{oid_text}')")
    return values


def _is_paid_package_order(order: dict[str, Any] | None) -> bool:
    if not isinstance(order, dict):
        return False
    item_type = _normalize(order.get("item_type") or "package").lower()
    status_value = _normalize(order.get("status")).lower()
    return item_type == "package" and status_value in PAID_ORDER_STATUSES


def _latest_linked_order(project_id: str) -> dict[str, Any] | None:
    db = _db()
    cursor = db["orders"].find({"project_id": {"$in": _project_id_candidates(project_id)}}).sort("created_at", -1)
    for item in cursor:
        if _is_paid_package_order(item):
            return item
    return None


def _latest_user_order_for_project(project: dict[str, Any]) -> dict[str, Any] | None:
    db = _db()
    owner_email = _normalize_email(project.get("owner_email"))
    owner_user_id = _normalize(project.get("owner_user_id"))

    query_filters: list[dict[str, Any]] = []
    if owner_email:
        query_filters.append({"email": owner_email})
    if owner_user_id:
        oid = _to_object_id(owner_user_id)
        if oid is not None:
            query_filters.append({"user_id": oid})
        query_filters.append({"user_id": owner_user_id})
    if not query_filters:
        return None

    cursor = db["orders"].find({"$or": query_filters}).sort("created_at", -1)
    for item in cursor:
        if _is_paid_package_order(item):
            return item
    return None


def _resolve_project_order_context(project_id: str, preferred_order_id: str = "") -> tuple[dict[str, Any], dict[str, Any] | None]:
    project = _project_by_id(project_id)
    if project is None:
        raise ValueError("Project not found.")

    order: dict[str, Any] | None = None
    if preferred_order_id:
        order = _order_by_id(preferred_order_id)
    if order is None:
        order = _latest_linked_order(_normalize(project.get("_id")))
    if order is None:
        order = _latest_user_order_for_project(project)
    return project, order


def _repair_order_document(
    *,
    order: dict[str, Any],
    project_id_text: str,
) -> dict[str, Any]:
    db = _db()
    updates: dict[str, Any] = {}

    project_oid = _to_object_id(project_id_text)
    if project_oid is not None:
        existing_project_oid = _to_object_id(_normalize(order.get("project_id")))
        if existing_project_oid != project_oid or not isinstance(order.get("project_id"), ObjectId):
            updates["project_id"] = project_oid

    existing_user_id = order.get("user_id")
    if not isinstance(existing_user_id, ObjectId):
        coerced_user_id = _to_object_id(_normalize(existing_user_id))
        if coerced_user_id is not None:
            updates["user_id"] = coerced_user_id

    for field_name in ("created_at", "updated_at"):
        raw_value = order.get(field_name)
        if isinstance(raw_value, datetime):
            continue
        coerced = _coerce_datetime(raw_value)
        if coerced is not None:
            updates[field_name] = coerced

    if updates:
        db["orders"].update_one({"_id": order.get("_id")}, {"$set": updates})
        order.update(updates)

    return {
        "order_id": _normalize(order.get("_id")),
        "updated_fields": sorted(updates.keys()),
    }


def _repair_entitlement_document(
    *,
    project_id_text: str,
    lane: str,
) -> dict[str, Any]:
    db = _db()
    collection = db["project_entitlements"]
    entitlement = collection.find_one({"project_id": {"$in": _project_id_candidates(project_id_text)}})
    if entitlement is None:
        return {"found": False, "updated_fields": []}

    updates: dict[str, Any] = {}
    if _normalize(entitlement.get("project_id")) != project_id_text:
        updates["project_id"] = project_id_text

    entitlement_lane = _normalize(entitlement.get("package_lane")).lower()
    if entitlement_lane not in ALLOWED_LANES and lane in ALLOWED_LANES:
        updates["package_lane"] = lane

    datetime_fields = (
        "purchased_at",
        "delivered_at",
        "created_at",
        "updated_at",
        "maintenance_scheduled_start_at",
        "maintenance_started_at",
        "maintenance_renews_at",
        "maintenance_current_period_start",
        "maintenance_current_period_end",
    )
    for field_name in datetime_fields:
        raw_value = entitlement.get(field_name)
        if isinstance(raw_value, datetime):
            continue
        coerced = _coerce_datetime(raw_value)
        if coerced is not None:
            updates[field_name] = coerced

    if updates:
        updates["updated_at"] = _now()
        collection.update_one({"_id": entitlement["_id"]}, {"$set": updates})

    return {
        "found": True,
        "updated_fields": sorted(updates.keys()),
    }


def _package_fields_from_context(project: dict[str, Any], order: dict[str, Any] | None) -> dict[str, Any]:
    raw_code = _normalize(
        project.get("package_code")
        or project.get("package_slug")
        or project.get("package_type")
        or (order or {}).get("package_code")
        or (order or {}).get("package_slug")
    )
    package_identity = resolve_package_identity(
        raw_code,
        package_name=project.get("package_name") or (order or {}).get("package_name"),
    )
    normalized_code = _normalize(package_identity.get("package_code")) or normalize_package_code(raw_code)
    package_slug = _normalize(package_identity.get("package_slug")) or normalized_code
    package = get_package(normalized_code) or {}
    lane = _normalize(package_identity.get("lane") or package.get("package_lane") or project.get("project_lane"))
    if lane not in ALLOWED_LANES:
        lane = "unknown"

    package_name = _normalize(
        package_identity.get("display_name")
        or project.get("package_name")
        or (order or {}).get("package_name")
        or package.get("display_name")
        or normalized_code
    )
    return {
        "package_code": normalized_code or "unknown",
        "package_slug": package_slug or normalized_code or "unknown",
        "package_name": package_name or "Unknown Package",
        "project_lane": lane,
    }


def _serialize_order(order: dict[str, Any] | None) -> dict[str, Any] | None:
    if not order:
        return None
    return {
        "id": _normalize(order.get("_id")),
        "email": _normalize(order.get("email")) or None,
        "user_id": _normalize_object_id(order.get("user_id")) or None,
        "status": _normalize(order.get("status")) or None,
        "package_code": normalize_package_code(_normalize(order.get("package_code") or order.get("package_slug"))),
        "package_name": _normalize(order.get("package_name")) or None,
        "project_id": _normalize_object_id(order.get("project_id")) or None,
        "billing_plan": _normalize(order.get("billing_plan")) or "one_time",
        "created_at": order.get("created_at"),
    }


def _serialize_project(project: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _normalize(project.get("_id") or project.get("id")),
        "name": _normalize(project.get("name") or project.get("project_name")) or "Project",
        "owner_user_id": _normalize(project.get("owner_user_id")) or None,
        "owner_email": _normalize_email(project.get("owner_email")) or None,
        "package_code": normalize_package_code(_normalize(project.get("package_code") or project.get("package_slug"))),
        "package_slug": normalize_package_code(_normalize(project.get("package_slug") or project.get("package_code"))),
        "package_name": _normalize(project.get("package_name")) or None,
        "project_lane": _normalize(project.get("project_lane")) or None,
        "status": _normalize(project.get("status")) or None,
        "phase": _normalize(project.get("phase")) or None,
        "family_id": _normalize(project.get("family_id")) or None,
        "updated_at": project.get("updated_at"),
    }


def sync_package(*, project_id: str, order_id: str = "") -> dict[str, Any]:
    db = _db()
    project, order = _resolve_project_order_context(project_id, preferred_order_id=order_id)
    package_fields = _package_fields_from_context(project, order)
    project_doc_id = _to_object_id(_normalize(project.get("_id")))
    if project_doc_id is None:
        raise ValueError("Invalid project identifier.")

    db["projects"].update_one(
        {"_id": project_doc_id},
        {
            "$set": {
                "package_code": package_fields["package_code"],
                "package_slug": package_fields["package_slug"],
                "package_type": package_fields["package_code"],
                "package_name": package_fields["package_name"],
                "updated_at": _now(),
            }
        },
    )
    if order is not None:
        db["orders"].update_one(
            {"_id": order["_id"]},
            {
                "$set": {
                    "package_code": package_fields["package_code"],
                    "package_slug": package_fields["package_slug"],
                    "package_name": package_fields["package_name"],
                }
            },
        )

    refreshed_project, refreshed_order = _resolve_project_order_context(
        _normalize(project.get("_id")),
        preferred_order_id=_normalize((order or {}).get("_id")),
    )
    return {
        "project": _serialize_project(refreshed_project),
        "order": _serialize_order(refreshed_order),
        "package": package_fields,
    }


def assign_lane(*, project_id: str) -> dict[str, Any]:
    db = _db()
    project = _project_by_id(project_id)
    if project is None:
        raise ValueError("Project not found.")

    package_fields = _package_fields_from_context(project, None)
    lane = package_fields["project_lane"]
    if lane not in ALLOWED_LANES:
        raise ValueError("Unable to resolve lane for the project package.")

    project_doc_id = _to_object_id(_normalize(project.get("_id")))
    if project_doc_id is None:
        raise ValueError("Invalid project identifier.")
    db["projects"].update_one(
        {"_id": project_doc_id},
        {"$set": {"project_lane": lane, "updated_at": _now()}},
    )

    entitlement = get_project_entitlement(_normalize(project.get("_id")))
    if entitlement:
        db["project_entitlements"].update_one(
            {"project_id": _normalize(project.get("_id"))},
            {"$set": {"package_lane": lane, "updated_at": _now()}},
        )

    return {"project_id": _normalize(project.get("_id")), "project_lane": lane, "entitlement_updated": bool(entitlement)}


def link_order_to_project(*, order_id: str, project_id: str = "") -> dict[str, Any]:
    db = _db()
    order = _order_by_id(order_id)
    if order is None:
        raise ValueError("Order not found.")

    project: dict[str, Any] | None = None
    if project_id:
        project = _project_by_id(project_id)
    else:
        email = _normalize_email(order.get("email"))
        user_id = _normalize(order.get("user_id"))
        filters: list[dict[str, Any]] = []
        if email:
            filters.append({"owner_email": email})
        if user_id:
            filters.append({"owner_user_id": user_id})
        if not filters:
            raise ValueError("Order has no identity fields for project matching.")
        project = db["projects"].find_one({"$or": filters}, sort=[("updated_at", -1)])

    if project is None:
        raise ValueError("Matching project not found.")

    project_id_str = _normalize(project.get("_id") or project.get("id"))
    if not project_id_str:
        raise ValueError("Project id is invalid.")

    owner_email = _normalize_email(project.get("owner_email"))
    order_email = _normalize_email(order.get("email"))
    if owner_email and order_email and owner_email != order_email:
        raise ValueError("Order email does not match project owner email.")

    project_value: Any = project_id_str
    project_oid = _to_object_id(project_id_str)
    if project_oid is not None:
        project_value = project_oid
    db["orders"].update_one({"_id": order["_id"]}, {"$set": {"project_id": project_value}})
    try:
        auto_provision_paid_order_by_id(_normalize(order.get("_id")))
    except Exception:
        pass

    return {
        "order_id": _normalize(order.get("_id")),
        "project_id": project_id_str,
        "linked": True,
    }


def generate_entitlement(*, project_id: str, order_id: str = "", force: bool = True) -> dict[str, Any]:
    project, order = _resolve_project_order_context(project_id, preferred_order_id=order_id)
    project_id_str = _normalize(project.get("_id"))
    existing = get_project_entitlement(project_id_str)
    if existing and not force:
        return {"entitlement": existing, "created": False, "regenerated": False}

    package_fields = _package_fields_from_context(project, order)
    control_profile = get_package_control_profile(package_fields["package_code"]) or {}
    plan_default = _normalize(control_profile.get("maintenance_default")) or "none"

    billing_plan = _normalize((order or {}).get("billing_plan")).lower()
    if billing_plan in {"monthly", "yearly"}:
        maintenance_plan = billing_plan
    elif billing_plan in {"none", "one_time"}:
        maintenance_plan = "none"
    else:
        maintenance_plan = plan_default

    delivered_at = project.get("updated_at") if _normalize(project.get("status")).lower() == "delivered" else None
    purchased_at = (order or {}).get("created_at")
    user_id = _normalize(project.get("owner_user_id") or (order or {}).get("user_id"))

    entitlement = upsert_project_entitlement(
        project_id=project_id_str,
        user_id=user_id or "unknown",
        package_code=package_fields["package_code"],
        active_addons=list((existing or {}).get("active_addons") or []),
        maintenance_plan=maintenance_plan,
        purchased_at=purchased_at,
        delivered_at=delivered_at,
        status="active",
    )
    if entitlement:
        _db()["project_entitlements"].update_one(
            {"project_id": project_id_str},
            {"$set": {"package_lane": package_fields["project_lane"], "updated_at": _now()}},
        )

    return {
        "entitlement": get_project_entitlement(project_id_str),
        "created": existing is None,
        "regenerated": existing is not None,
    }


def repair_record(*, project_id: str, order_id: str = "") -> dict[str, Any]:
    db = _db()
    project, order = _resolve_project_order_context(project_id, preferred_order_id=order_id)
    project_id_str = _normalize(project.get("_id") or project.get("id"))
    if not project_id_str:
        raise ValueError("Project id is invalid.")

    project_doc_id = _to_object_id(project_id_str)
    if project_doc_id is None:
        raise ValueError("Project id is invalid.")

    package_fields = _package_fields_from_context(project, order)
    lane = package_fields["project_lane"]

    project_updates: dict[str, Any] = {
        "package_code": package_fields["package_code"],
        "package_slug": package_fields["package_slug"],
        "package_type": package_fields["package_code"],
        "package_name": package_fields["package_name"],
        "updated_at": _now(),
    }
    if lane in ALLOWED_LANES:
        project_updates["project_lane"] = lane

    for field_name in ("created_at", "updated_at"):
        raw_value = project.get(field_name)
        if isinstance(raw_value, datetime):
            continue
        coerced = _coerce_datetime(raw_value)
        if coerced is not None:
            project_updates[field_name] = coerced

    db["projects"].update_one({"_id": project_doc_id}, {"$set": project_updates})

    order_repair: dict[str, Any] = {"updated_fields": []}
    if order is not None and _is_paid_package_order(order):
        order_repair = _repair_order_document(
            order=order,
            project_id_text=project_id_str,
        )
    elif order is not None:
        order_repair = {
            "order_id": _normalize(order.get("_id")),
            "updated_fields": [],
            "skipped_reason": "order_not_paid_package",
        }

    entitlement_repair = _repair_entitlement_document(
        project_id_text=project_id_str,
        lane=lane,
    )
    entitlement_before = get_project_entitlement(project_id_str)
    entitlement_generation = {"created": False, "regenerated": False}
    if entitlement_before is None:
        generated = generate_entitlement(
            project_id=project_id_str,
            order_id=_normalize((order or {}).get("_id")),
            force=False,
        )
        entitlement_generation = {
            "created": bool(generated.get("created")),
            "regenerated": bool(generated.get("regenerated")),
        }

    refreshed_project, refreshed_order = _resolve_project_order_context(
        project_id_str,
        preferred_order_id=_normalize((order or {}).get("_id")),
    )
    readiness = run_readiness_check(
        project_id=project_id_str,
        order_id=_normalize((refreshed_order or {}).get("_id")),
    )

    return {
        "project": _serialize_project(refreshed_project),
        "order": _serialize_order(refreshed_order),
        "entitlement": get_project_entitlement(project_id_str),
        "repairs": {
            "project_updated_fields": sorted(project_updates.keys()),
            "order": order_repair,
            "entitlement_record": entitlement_repair,
            "entitlement_generation": entitlement_generation,
        },
        "readiness": readiness,
    }


def run_readiness_check(*, project_id: str, order_id: str = "") -> dict[str, Any]:
    project, order = _resolve_project_order_context(project_id, preferred_order_id=order_id)
    project_id_str = _normalize(project.get("_id"))
    entitlement = get_project_entitlement(project_id_str)
    package_fields = _package_fields_from_context(project, order)
    project_identity = resolve_package_identity(project.get("package_slug") or project.get("package_code"))
    order_identity = resolve_package_identity((order or {}).get("package_slug") or (order or {}).get("package_code"))
    entitlement_identity = resolve_package_identity((entitlement or {}).get("package_code"))

    project_package_code = _normalize(project_identity.get("package_code")) or normalize_package_code(_normalize(project.get("package_code") or project.get("package_slug")))
    order_package_code = _normalize(order_identity.get("package_code")) or normalize_package_code(_normalize((order or {}).get("package_code") or (order or {}).get("package_slug")))
    entitlement_package_code = _normalize(entitlement_identity.get("package_code")) or normalize_package_code(_normalize((entitlement or {}).get("package_code")))
    package_synced = bool(project_package_code and order_package_code and project_package_code == order_package_code == package_fields["package_code"])
    if entitlement:
        package_synced = package_synced and entitlement_package_code == package_fields["package_code"]

    lane_value = _normalize(project.get("project_lane")).lower()
    entitlement_lane = _normalize((entitlement or {}).get("package_lane")).lower()
    lane_assigned = lane_value in ALLOWED_LANES and (not entitlement or entitlement_lane == lane_value)

    linked_project_id = _normalize_object_id((order or {}).get("project_id"))
    order_linked = bool(order and linked_project_id and linked_project_id == _normalize_object_id(project_id_str))
    entitlement_exists = entitlement is not None

    upload_count = count_workspace_uploads(project_id=project_id_str)
    uploads_present = upload_count > 0

    status_ready = _normalize(project.get("status")).lower() in BUILD_READY_STATUSES
    phase_ready = _normalize(project.get("phase")).lower() in INTAKE_APPROVED_PHASES
    mint_eligibility = describe_project_mint_eligibility(project)

    control_profile = get_package_control_profile(package_fields["package_code"]) or {}
    launch_policy = dict(control_profile.get("launch_policy") or {})
    allows_automatic_anchor = bool(launch_policy.get("allows_automatic_anchor"))
    mint_review_ready = bool(
        allows_automatic_anchor
        and status_ready
        and phase_ready
        and package_synced
        and lane_assigned
        and order_linked
        and entitlement_exists
    )
    mint_eligible = bool(mint_eligibility.get("eligible") and mint_review_ready and uploads_present)
    package_normalized = bool(
        package_fields["package_code"] != "unknown"
        and _normalize(project.get("package_slug"))
        and _normalize(project.get("package_code"))
    )

    return {
        "project_id": project_id_str,
        "package_normalized": package_normalized,
        "package_synced": package_synced,
        "lane_assigned": lane_assigned,
        "order_linked": order_linked,
        "entitlement_exists": entitlement_exists,
        "uploads_present": uploads_present,
        "build_ready": status_ready,
        "intake_approved": phase_ready,
        "mint_review_ready": mint_review_ready,
        "mint_eligible": mint_eligible,
        "mint_readiness_computed": True,
        "summary": {
            "package_normalized": "yes" if package_normalized else "no",
            "package_synced": "yes" if package_synced else "no",
            "lane_assigned": "yes" if lane_assigned else "no",
            "order_linked": "yes" if order_linked else "no",
            "entitlement_exists": "yes" if entitlement_exists else "no",
            "mint_eligible": "yes" if mint_eligible else "no",
        },
        "mint_policy": mint_eligibility.get("mint_policy"),
        "mint_reasons": mint_eligibility.get("reasons") or [],
    }


def repair_all_missing_entitlements(*, limit: int = 200) -> dict[str, Any]:
    return repair_missing_entitlements(limit=limit)


def repair_all_missing_lanes(*, limit: int = 200) -> dict[str, Any]:
    return repair_missing_lanes(limit=limit)


def link_all_unlinked_paid_orders(*, limit: int = 200) -> dict[str, Any]:
    return link_unlinked_paid_orders(limit=limit)


def enable_mint_review(*, project_id: str, order_id: str = "") -> dict[str, Any]:
    db = _db()
    readiness = run_readiness_check(project_id=project_id, order_id=order_id)
    if not readiness.get("mint_review_ready"):
        raise ValueError("Project is not ready for mint review.")

    project_doc_id = _to_object_id(_normalize(project_id))
    if project_doc_id is None:
        raise ValueError("Project id is invalid.")

    db["projects"].update_one(
        {"_id": project_doc_id},
        {
            "$set": {
                "mint_review_ready": True,
                "mint_review_ready_at": _now(),
                "mint_review_state": "ready",
            }
        },
    )

    auto_mint_allowed = bool(settings.nft_auto_mint_on_review_enabled)
    return {
        "project_id": _normalize(project_id),
        "mint_review_ready": True,
        "auto_mint_allowed": auto_mint_allowed,
        "auto_mint_executed": False,
    }


def project_workspace_snapshot(project_id: str) -> dict[str, Any]:
    project, order = _resolve_project_order_context(project_id)
    project_id_str = _normalize(project.get("_id"))
    entitlement = get_project_entitlement(project_id_str)
    readiness = run_readiness_check(project_id=project_id_str)

    related_orders = []
    db = _db()
    owner_email = _normalize_email(project.get("owner_email"))
    if owner_email:
        cursor = db["orders"].find({"email": owner_email}).sort("created_at", -1).limit(10)
        related_orders = [_serialize_order(item) for item in cursor if _serialize_order(item)]

    return {
        "project": _serialize_project(project),
        "order": _serialize_order(order),
        "entitlement": entitlement,
        "readiness": readiness,
        "related_orders": related_orders,
    }


def admin_console_overview(*, limit: int = 20) -> dict[str, Any]:
    db = _db()
    users_total = int(db["users"].count_documents({}))
    active_projects = int(db["projects"].count_documents({"status": {"$ne": "archived"}}))
    paid_orders = int(db["orders"].count_documents({"status": {"$in": list(PAID_ORDER_STATUSES)}}))

    project_ids = [
        _normalize(item.get("_id"))
        for item in db["projects"].find({}, {"_id": 1})
    ]
    entitlement_project_ids = {
        _normalize(item.get("project_id"))
        for item in db["project_entitlements"].find({}, {"project_id": 1})
        if _normalize(item.get("project_id"))
    }
    missing_entitlements = [project_id for project_id in project_ids if project_id and project_id not in entitlement_project_ids]

    mismatches: list[dict[str, Any]] = []
    mint_ready_count = 0
    priority_repairs = {
        "paid_order_without_project_link": [],
        "project_without_entitlement": [],
        "package_without_lane": [],
        "mint_eligible_blocked": [],
    }

    for project in db["projects"].find({}).sort("updated_at", -1).limit(500):
        project_id = _normalize(project.get("_id"))
        readiness = run_readiness_check(project_id=project_id)
        if readiness.get("mint_review_ready"):
            mint_ready_count += 1
        if not readiness.get("package_synced") or not readiness.get("lane_assigned") or not readiness.get("order_linked") or not readiness.get("entitlement_exists"):
            mismatches.append(
                {
                    "project_id": project_id,
                    "project_name": _normalize(project.get("name") or project.get("project_name")) or "Project",
                    "summary": readiness.get("summary"),
                }
            )
        if not readiness.get("entitlement_exists"):
            priority_repairs["project_without_entitlement"].append(project_id)
        if not readiness.get("lane_assigned"):
            priority_repairs["package_without_lane"].append(project_id)
        if readiness.get("mint_review_ready") and not readiness.get("mint_eligible"):
            priority_repairs["mint_eligible_blocked"].append(project_id)

    for order in db["orders"].find({"status": {"$in": list(PAID_ORDER_STATUSES)}}).sort("created_at", -1).limit(500):
        if _normalize(order.get("project_id")):
            continue
        priority_repairs["paid_order_without_project_link"].append(
            {
                "order_id": _normalize(order.get("_id")),
                "email": _normalize_email(order.get("email")) or None,
                "package_name": _normalize(order.get("package_name")) or None,
            }
        )

    return {
        "summary": {
            "total_users": users_total,
            "total_active_projects": active_projects,
            "paid_orders": paid_orders,
            "missing_entitlements": len(missing_entitlements),
            "mint_ready_projects": mint_ready_count,
            "projects_with_data_mismatch": len(mismatches),
        },
        "priority_repairs": {
            "paid_order_without_project_link": priority_repairs["paid_order_without_project_link"][:limit],
            "project_without_entitlement": priority_repairs["project_without_entitlement"][:limit],
            "package_without_lane": priority_repairs["package_without_lane"][:limit],
            "mint_eligible_blocked": priority_repairs["mint_eligible_blocked"][:limit],
        },
        "mismatches": mismatches[:limit],
    }
