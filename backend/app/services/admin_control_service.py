from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, Callable

from bson import ObjectId

from app.config import settings
from app.core.package_catalog import (
    canonicalize_package_identifier,
    get_package,
    get_package_control_profile,
    normalize_package_code,
)
from app.database import get_database
from app.services.audit_log_service import write_audit_log
from app.services.mint_job_service import sync_receipt_for_mint_record
from app.services.mint_policy_service import describe_project_mint_eligibility
from app.services.mint_record_service import (
    rebuild_mint_summary_for_project,
    resolve_canonical_mint_status,
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
MAX_BULK_ACTION_LIMIT = 5000
INTERNAL_ROLE_KEYS = {
    "admin",
    "super_admin",
    "root_admin",
    "platform_admin",
    "operations_admin",
    "finance_admin",
    "marketing_admin",
    "executive_technology",
    "operations",
    "finance",
    "marketing",
}

ADMIN_CONTROL_QUEUES = [
    "overview",
    "customer_cases",
    "orders",
    "projects",
    "entitlements",
    "mint_queue",
    "upload_review",
    "billing_maintenance",
    "users",
    "audit",
    "system_health",
]
ADMIN_CONTROL_TABS = [
    "identity",
    "package_lane",
    "orders_billing",
    "project",
    "entitlements",
    "uploads_verification",
    "mint_readiness",
    "audit_timeline",
]
CASE_ACTION_PERMISSIONS: dict[str, set[str]] = {
    "sync_package": {"admin.control.write"},
    "normalize_package": {"admin.control.write"},
    "assign_lane": {"admin.control.write"},
    "repair_record": {"admin.control.write"},
    "link_order_to_project": {"admin.control.billing"},
    "generate_entitlement": {"admin.control.billing"},
    "refresh_entitlement": {"admin.control.billing"},
    "run_readiness_check": {"admin.control.view"},
    "refresh_case_data": {"admin.control.view"},
    "queue_for_mint_review": {"admin.control.mint"},
    "repair_mint_status": {"admin.control.mint"},
    "rebuild_mint_summary": {"admin.control.mint"},
    "resync_mint_receipt": {"admin.control.mint"},
}
BULK_ACTION_PERMISSIONS: dict[str, set[str]] = {
    "repair-missing-entitlements": {"admin.control.billing"},
    "assign-missing-lanes": {"admin.control.write"},
    "link-unlinked-paid-orders": {"admin.control.billing"},
    "normalize-broken-package-records": {"admin.control.write"},
    "refresh-mint-readiness": {"admin.control.mint"},
    "repair-selected-records": {"admin.control.write", "admin.control.billing"},
    "repair-all-safe-records": {"admin.control.write"},
}
QUEUE_PERMISSIONS: dict[str, set[str]] = {
    "overview": {"admin.control.view"},
    "customer_cases": {"admin.control.view"},
    "projects": {"admin.control.view"},
    "system_health": {"admin.control.view"},
    "orders": {"admin.control.billing", "admin.orders.read"},
    "billing_maintenance": {"admin.control.billing"},
    "entitlements": {"admin.control.billing", "admin.entitlements.read"},
    "mint_queue": {"admin.control.mint"},
    "upload_review": {"uploads.admin.review", "verification.review"},
    "users": {"admin.users.read"},
    "audit": {"admin.audit.read"},
}
TAB_PERMISSIONS: dict[str, set[str]] = {
    "identity": {"admin.control.view"},
    "package_lane": {"admin.control.view"},
    "project": {"admin.control.view"},
    "orders_billing": {"admin.control.billing", "admin.orders.read"},
    "entitlements": {"admin.control.billing", "admin.entitlements.read"},
    "uploads_verification": {"uploads.admin.review", "verification.review"},
    "mint_readiness": {"admin.control.mint"},
    "audit_timeline": {"admin.audit.read"},
}

GUIDANCE_RULE_ALIASES = {
    "lane_not_assigned": "lane_unknown",
    "order_not_linked": "paid_order_not_linked",
    "uploads_missing": "upload_review_pending",
    "package_not_synced": "package_normalization_needed",
}

OPERATOR_GUIDANCE_RULES = {
    "missing_entitlement": {
        "title": "Entitlement record is missing",
        "rule": "Every approved project must have a project entitlement tied to its canonical package and lane.",
        "next_action": "Generate Entitlement",
        "recommended_action": "generate_entitlement",
        "severity": "critical",
    },
    "lane_unknown": {
        "title": "Lane is not assigned",
        "rule": "Mint, maintenance, and entitlement policy require a canonical lane: portrait, household, network, or organization.",
        "next_action": "Assign Lane",
        "recommended_action": "assign_lane",
        "severity": "critical",
    },
    "paid_order_not_linked": {
        "title": "Paid order is not linked to the project",
        "rule": "A paid package order must resolve to the live project before billing, entitlement, or mint readiness can be trusted.",
        "next_action": "Link Order to Project",
        "recommended_action": "link_order_to_project",
        "severity": "critical",
    },
    "package_normalization_needed": {
        "title": "Package values need normalization",
        "rule": "Admin display uses project first, then reconciles order and entitlement against the shared package catalog.",
        "next_action": "Sync Package",
        "recommended_action": "sync_package",
        "severity": "warning",
    },
    "package_unknown": {
        "title": "Package is not recognized",
        "rule": "Package slug, code, and display name must map to a known Tomb of Light package.",
        "next_action": "Normalize Package",
        "recommended_action": "normalize_package",
        "severity": "critical",
    },
    "package_missing_on_project": {
        "title": "Project package source is missing",
        "rule": "The linked project is the primary admin display source and must carry the canonical package fields.",
        "next_action": "Sync Package",
        "recommended_action": "sync_package",
        "severity": "warning",
    },
    "package_mismatch_order": {
        "title": "Project and order packages disagree",
        "rule": "The project remains primary, but the linked order must reconcile to the same package code.",
        "next_action": "Sync Package",
        "recommended_action": "sync_package",
        "severity": "critical",
    },
    "package_mismatch_entitlement": {
        "title": "Project and entitlement packages disagree",
        "rule": "Entitlement package code must match the canonical linked project package.",
        "next_action": "Refresh Entitlement",
        "recommended_action": "refresh_entitlement",
        "severity": "critical",
    },
    "lane_mismatch_entitlement": {
        "title": "Project and entitlement lanes disagree",
        "rule": "Entitlement package lane must match the canonical project lane.",
        "next_action": "Refresh Entitlement",
        "recommended_action": "refresh_entitlement",
        "severity": "critical",
    },
    "maintenance_not_started": {
        "title": "Maintenance billing has not started",
        "rule": "Packages with maintenance defaults need a started or scheduled maintenance state after entitlement is resolved.",
        "next_action": "Repair Record",
        "recommended_action": "repair_record",
        "severity": "warning",
    },
    "duplicate_admin_user_identity": {
        "title": "Customer identity overlaps with an admin identity",
        "rule": "Case selection prefers the customer record; duplicate internal identities are surfaced for audit review.",
        "next_action": "Repair Record",
        "recommended_action": "repair_record",
        "severity": "warning",
    },
    "upload_review_pending": {
        "title": "Upload review is pending",
        "rule": "Mint eligibility requires customer files to be present and reviewable before the case can advance.",
        "next_action": "Review Uploads",
        "recommended_action": "run_readiness_check",
        "severity": "warning",
    },
    "mint_blocked": {
        "title": "Mint is blocked",
        "rule": "Mint can only proceed after package, lane, order, entitlement, project phase, and upload gates pass together.",
        "next_action": "Run Readiness Check",
        "recommended_action": "run_readiness_check",
        "severity": "critical",
    },
    "mint_runtime_disabled": {
        "title": "Mint runtime is disabled",
        "rule": "The runtime flag is off, so this case can be prepared but cannot execute automatic minting.",
        "next_action": "Queue for Mint Review",
        "recommended_action": "queue_for_mint_review",
        "severity": "warning",
    },
    "project_not_build_ready": {
        "title": "Project is not build-ready",
        "rule": "Mint review requires the project status to be in an approved build-ready state.",
        "next_action": "Run Readiness Check",
        "recommended_action": "run_readiness_check",
        "severity": "info",
    },
    "project_not_intake_approved": {
        "title": "Project intake is not approved",
        "rule": "Mint review requires the project phase to pass intake approval.",
        "next_action": "Run Readiness Check",
        "recommended_action": "run_readiness_check",
        "severity": "info",
    },
}


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _normalize_email(value: Any) -> str:
    return _normalize(value).lower()


def _has_any_permission(
    permissions: set[str],
    required: set[str] | list[str] | tuple[str, ...],
) -> bool:
    required_set = {
        _normalize(permission).lower()
        for permission in required
        if _normalize(permission)
    }
    if not required_set:
        return True
    return "*" in permissions or not permissions.isdisjoint(required_set)


def admin_control_access_profile(current_user: dict[str, Any]) -> dict[str, Any]:
    access_context = current_user.get("_access_context") or {}
    role_codes = [
        _normalize(role).lower()
        for role in (access_context.get("role_codes") or [])
        if _normalize(role)
    ]
    if not role_codes:
        role_codes = [
            _normalize(current_user.get(field_name)).lower()
            for field_name in ("role", "access_tier", "department_role")
            if _normalize(current_user.get(field_name))
        ]

    permissions = {
        _normalize(permission).lower()
        for permission in (access_context.get("permissions") or [])
        if _normalize(permission)
    }

    allowed_queues = [
        queue
        for queue in ADMIN_CONTROL_QUEUES
        if _has_any_permission(permissions, QUEUE_PERMISSIONS.get(queue, {"admin.control.view"}))
    ]
    allowed_tabs = [
        tab
        for tab in ADMIN_CONTROL_TABS
        if _has_any_permission(permissions, TAB_PERMISSIONS.get(tab, {"admin.control.view"}))
    ]
    allowed_actions = [
        action
        for action in sorted(CASE_ACTION_PERMISSIONS)
        if _has_any_permission(permissions, CASE_ACTION_PERMISSIONS[action])
    ]
    allowed_bulk_actions = [
        action
        for action in sorted(BULK_ACTION_PERMISSIONS)
        if _has_any_permission(permissions, BULK_ACTION_PERMISSIONS[action])
    ]

    primary_role = next(
        (role for role in role_codes if role in INTERNAL_ROLE_KEYS),
        role_codes[0] if role_codes else _normalize(current_user.get("role")).lower() or "user",
    )

    return {
        "role_key": primary_role,
        "role_codes": role_codes,
        "permissions": sorted(permissions),
        "allowed_queues": allowed_queues,
        "allowed_tabs": allowed_tabs,
        "allowed_actions": allowed_actions,
        "allowed_bulk_actions": allowed_bulk_actions,
        "is_wildcard": "*" in permissions,
    }


def admin_control_action_allowed(
    current_user: dict[str, Any],
    action: str,
) -> bool:
    normalized_action = _normalize(action).lower()
    profile = admin_control_access_profile(current_user)
    return normalized_action in set(profile.get("allowed_actions") or [])


def admin_control_bulk_action_allowed(
    current_user: dict[str, Any],
    action: str,
) -> bool:
    normalized_action = _normalize(action).lower()
    profile = admin_control_access_profile(current_user)
    return normalized_action in set(profile.get("allowed_bulk_actions") or [])


def _now() -> datetime:
    return datetime.now(UTC)


def _actor_snapshot(actor: dict[str, Any] | None) -> dict[str, str | None]:
    if not isinstance(actor, dict):
        return {"actor_user_id": None, "actor_email": None, "actor_name": None}

    first_name = _normalize(actor.get("first_name"))
    last_name = _normalize(actor.get("last_name"))
    actor_name = _normalize(actor.get("full_name")) or " ".join(
        [first_name, last_name]
    ).strip()
    return {
        "actor_user_id": _normalize_object_id(actor.get("_id") or actor.get("id") or actor.get("user_id")) or None,
        "actor_email": _normalize_email(actor.get("email")) or None,
        "actor_name": actor_name or None,
    }


def _write_admin_action_audit(
    *,
    actor: dict[str, Any] | None,
    action: str,
    target_type: str,
    target_id: str,
    result: str = "success",
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    actor_fields = _actor_snapshot(actor)
    try:
        write_audit_log(
            actor_user_id=actor_fields["actor_user_id"],
            actor_email=actor_fields["actor_email"],
            actor_name=actor_fields["actor_name"],
            action=f"admin_control_center.{action}",
            target_type=target_type,
            target_id=target_id,
            before=before or {},
            after=after or {},
            context=context or {},
            details=details or {},
            result=result,
        )
    except Exception:
        # Admin repairs should not fail solely because audit persistence is unavailable.
        return


def _db():
    db = get_database()
    if db is None:
        raise ValueError("Database is not connected.")
    return db


def _to_object_id(value: Any) -> ObjectId | None:
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


def _document_id_candidates(value: str) -> list[Any]:
    normalized = _normalize(value)
    values: list[Any] = [normalized]
    oid = _to_object_id(normalized)
    if oid is not None:
        values.append(oid)
        oid_text = str(oid)
        values.append(f'ObjectId("{oid_text}")')
        values.append(f"ObjectId('{oid_text}')")
    return values


def _project_id_candidates(project_id: str) -> list[Any]:
    return _document_id_candidates(project_id)


def _project_is_approved(project: dict[str, Any]) -> bool:
    status_value = _normalize(project.get("status")).lower()
    phase_value = _normalize(project.get("phase")).lower()
    return status_value in BUILD_READY_STATUSES or phase_value in INTAKE_APPROVED_PHASES


def _approved_project_query() -> dict[str, Any]:
    return {
        "$or": [
            {"status": {"$in": list(BUILD_READY_STATUSES)}},
            {"phase": {"$in": list(INTAKE_APPROVED_PHASES)}},
        ]
    }


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


def _order_project_id_matches(order: dict[str, Any] | None, project_id: str) -> bool:
    if not order or not _normalize(project_id):
        return False
    project_ids = {
        _normalize_object_id(value)
        for value in _project_id_candidates(project_id)
        if _normalize_object_id(value)
    }
    order_project_id = _normalize_object_id(order.get("project_id"))
    return bool(order_project_id and order_project_id in project_ids)


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


def _resolve_project_order_context(
    project_id: str,
    preferred_order_id: str = "",
    *,
    allow_owner_order_fallback: bool = False,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    project = _project_by_id(project_id)
    if project is None:
        raise ValueError("Project not found.")

    project_id_str = _normalize(project.get("_id") or project.get("id"))
    order: dict[str, Any] | None = None
    if preferred_order_id:
        preferred_order = _order_by_id(preferred_order_id)
        if preferred_order is not None:
            if not _order_project_id_matches(preferred_order, project_id_str):
                raise ValueError("Order does not belong to the selected project.")
            order = preferred_order
    if order is None:
        order = _latest_linked_order(project_id_str)
    if order is None and allow_owner_order_fallback:
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
    user_id_text: str = "",
) -> dict[str, Any]:
    db = _db()
    collection = db["project_entitlements"]
    entitlement = collection.find_one({"project_id": {"$in": _project_id_candidates(project_id_text)}})
    if entitlement is None:
        return {"found": False, "updated_fields": []}

    updates: dict[str, Any] = {}
    project_oid = _to_object_id(project_id_text)
    existing_project_oid = _to_object_id(_normalize(entitlement.get("project_id")))
    if (
        project_oid is not None
        and (existing_project_oid != project_oid or not isinstance(entitlement.get("project_id"), ObjectId))
    ):
        updates["project_id"] = project_oid

    user_oid = _to_object_id(_normalize(user_id_text))
    existing_user_id = entitlement.get("user_id")
    existing_user_oid = _to_object_id(_normalize(existing_user_id))
    if user_oid is not None:
        if existing_user_oid != user_oid or not isinstance(existing_user_id, ObjectId):
            updates["user_id"] = user_oid
    elif not isinstance(existing_user_id, ObjectId):
        coerced_user_oid = _to_object_id(_normalize(existing_user_id))
        if coerced_user_oid is not None:
            updates["user_id"] = coerced_user_oid

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


def _source_package_snapshot(
    source: str,
    values: list[Any],
    *,
    lane: Any = "",
) -> dict[str, Any]:
    raw_values = [_normalize(value) for value in values if _normalize(value)]
    chosen = canonicalize_package_identifier(raw_values[0] if raw_values else "")
    for raw_value in raw_values:
        candidate = canonicalize_package_identifier(raw_value)
        if candidate.get("is_known"):
            chosen = candidate
            break

    package_lane = _normalize(chosen.get("package_lane")).lower()
    explicit_lane = _normalize(lane).lower()
    resolved_lane = explicit_lane if explicit_lane in ALLOWED_LANES else package_lane
    if resolved_lane not in ALLOWED_LANES:
        resolved_lane = "unknown"

    return {
        "source": source,
        "raw_values": raw_values,
        "package_code": _normalize(chosen.get("package_code")),
        "package_slug": _normalize(chosen.get("package_slug")),
        "package_name": _normalize(chosen.get("package_name")),
        "package_lane": package_lane or None,
        "lane": resolved_lane,
        "normalization_status": _normalize(chosen.get("normalization_status")) or "unknown",
        "is_known": bool(chosen.get("is_known")),
    }


def _project_lane_value(project: dict[str, Any]) -> str:
    for key in ("project_lane", "lane", "package_lane"):
        lane = _normalize(project.get(key)).lower()
        if lane in ALLOWED_LANES:
            return lane
    return ""


def _package_fields_from_context(
    project: dict[str, Any],
    order: dict[str, Any] | None,
    entitlement: dict[str, Any] | None = None,
) -> dict[str, Any]:
    project_source = _source_package_snapshot(
        "project",
        [
            project.get("package_code"),
            project.get("package_slug"),
            project.get("package_type"),
            project.get("package_name"),
        ],
        lane=_project_lane_value(project),
    )
    order_source = _source_package_snapshot(
        "order",
        [
            (order or {}).get("package_code"),
            (order or {}).get("package_slug"),
            (order or {}).get("package_type"),
            (order or {}).get("package_name"),
        ],
    )
    entitlement_source = _source_package_snapshot(
        "entitlement",
        [
            (entitlement or {}).get("package_code"),
            (entitlement or {}).get("package_slug"),
            (entitlement or {}).get("package_name"),
        ],
        lane=(entitlement or {}).get("package_lane"),
    )

    sources = {
        "project": project_source,
        "order": order_source,
        "entitlement": entitlement_source,
    }
    chosen = next(
        (
            source
            for source in (project_source, order_source, entitlement_source)
            if source.get("is_known")
        ),
        project_source,
    )

    package_code = _normalize(chosen.get("package_code"))
    package = get_package(package_code) or {}
    package_lane = _normalize(package.get("package_lane") or chosen.get("package_lane")).lower()
    explicit_project_lane = _project_lane_value(project)
    lane = explicit_project_lane or package_lane or _normalize(chosen.get("lane")).lower()
    if lane not in ALLOWED_LANES:
        lane = "unknown"

    package_name = _normalize(package.get("display_name") or chosen.get("package_name") or package_code)
    warnings: list[str] = []
    if not project_source.get("is_known") and (order_source.get("is_known") or entitlement_source.get("is_known")):
        warnings.append("package_missing_on_project")

    for source in (order_source, entitlement_source):
        source_code = _normalize(source.get("package_code"))
        if source.get("is_known") and package_code and source_code != package_code:
            warnings.append(f"package_mismatch_{source['source']}")

    for source in (entitlement_source,):
        source_lane = _normalize(source.get("lane")).lower()
        if source.get("is_known") and source_lane in ALLOWED_LANES and lane in ALLOWED_LANES and source_lane != lane:
            warnings.append(f"lane_mismatch_{source['source']}")

    normalization_status = _normalize(chosen.get("normalization_status")) or "unknown"
    if chosen is order_source and project_source.get("is_known") is False:
        normalization_status = "recovered_from_order"
    if chosen is entitlement_source and project_source.get("is_known") is False:
        normalization_status = "recovered_from_entitlement"

    return {
        "package_code": package_code or "unknown",
        "package_slug": package_code or "unknown",
        "package_name": package_name or "Unknown Package",
        "lane": lane,
        "project_lane": lane,
        "package_lane": package_lane or lane,
        "source": _normalize(chosen.get("source")) or None,
        "raw_value": (chosen.get("raw_values") or [None])[0],
        "normalization_status": normalization_status,
        "is_known": bool(chosen.get("is_known")),
        "warnings": list(dict.fromkeys(warnings)),
        "sources": sources,
    }


def _resolve_entitlement_user_id(project: dict[str, Any], order: dict[str, Any] | None) -> str:
    candidate_values = [
        project.get("owner_user_id"),
        (order or {}).get("user_id"),
    ]
    for value in candidate_values:
        oid = _to_object_id(_normalize(value))
        if oid is not None:
            return str(oid)

    owner_email = _normalize_email(project.get("owner_email"))
    if owner_email:
        user = _find_case_user(email=owner_email)
        if user is not None:
            user_id = user.get("_id")
            oid = _to_object_id(user_id)
            if oid is not None:
                return str(oid)

    return ""


def _serialize_order(order: dict[str, Any] | None) -> dict[str, Any] | None:
    if not order:
        return None
    return {
        "id": _normalize(order.get("_id")),
        "email": _normalize(order.get("email")) or None,
        "user_id": _normalize_object_id(order.get("user_id")) or None,
        "status": _normalize(order.get("status")) or None,
        "package_code": normalize_package_code(_normalize(order.get("package_code") or order.get("package_slug"))),
        "package_slug": normalize_package_code(_normalize(order.get("package_slug") or order.get("package_code"))),
        "package_name": _normalize(order.get("package_name")) or None,
        "lane": _normalize(order.get("lane") or order.get("package_lane")) or None,
        "project_id": _normalize_object_id(order.get("project_id")) or None,
        "billing_plan": _normalize(order.get("billing_plan")) or "one_time",
        "stripe_session_id": _normalize(order.get("stripe_session_id") or order.get("session_id")) or None,
        "payment_link_id": _normalize(order.get("stripe_payment_link_id") or order.get("payment_link_id")) or None,
        "subscription_id": _normalize(order.get("stripe_subscription_id") or order.get("subscription_id")) or None,
        "next_charge_date": _serialize_datetime(order.get("next_charge_date") or order.get("current_period_end")),
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
        "lane": _normalize(project.get("lane") or project.get("project_lane")) or None,
        "project_lane": _normalize(project.get("project_lane")) or None,
        "status": _normalize(project.get("status")) or None,
        "phase": _normalize(project.get("phase")) or None,
        "source": _normalize(project.get("source") or project.get("provisioning_source")) or None,
        "intake_status": _normalize(project.get("intake_status") or project.get("intake_readiness")) or None,
        "family_id": _normalize(project.get("family_id")) or None,
        "household_id": _normalize(project.get("household_id")) or None,
        "updated_at": project.get("updated_at"),
    }


def sync_package(*, project_id: str, order_id: str = "") -> dict[str, Any]:
    db = _db()
    project, order = _resolve_project_order_context(project_id, preferred_order_id=order_id)
    entitlement = get_project_entitlement(_normalize(project.get("_id")))
    package_fields = _package_fields_from_context(project, order, entitlement)
    project_doc_id = _to_object_id(_normalize(project.get("_id")))
    if project_doc_id is None:
        raise ValueError("Invalid project identifier.")

    project_updates = {
        "package_code": package_fields["package_code"],
        "package_slug": package_fields["package_slug"],
        "package_type": package_fields["package_code"],
        "package_name": package_fields["package_name"],
        "updated_at": _now(),
    }
    if package_fields["project_lane"] in ALLOWED_LANES:
        project_updates["project_lane"] = package_fields["project_lane"]

    db["projects"].update_one({"_id": project_doc_id}, {"$set": project_updates})
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

    entitlement = get_project_entitlement(_normalize(project.get("_id")))
    package_fields = _package_fields_from_context(project, None, entitlement)
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
        project_id_filter = {"$in": _project_id_candidates(_normalize(project.get("_id")))}
        db["project_entitlements"].update_one(
            {"project_id": project_id_filter},
            {"$set": {"package_lane": lane, "updated_at": _now()}},
        )
        _repair_entitlement_document(
            project_id_text=_normalize(project.get("_id")),
            lane=lane,
            user_id_text=_resolve_entitlement_user_id(project, None),
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
        project = _find_matching_approved_project_for_order(order)

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

    return {
        "order_id": _normalize(order.get("_id")),
        "project_id": project_id_str,
        "linked": True,
    }


def generate_entitlement(*, project_id: str, order_id: str = "", force: bool = True) -> dict[str, Any]:
    project, order = _resolve_project_order_context(project_id, preferred_order_id=order_id)
    project_id_str = _normalize(project.get("_id"))
    existing = get_project_entitlement(project_id_str)
    package_fields = _package_fields_from_context(project, order, existing)
    if existing and not force:
        lane = package_fields["project_lane"]
        user_id = _resolve_entitlement_user_id(project, order)
        entitlement_repair = _repair_entitlement_document(
            project_id_text=project_id_str,
            lane=lane,
            user_id_text=user_id,
        )
        return {
            "entitlement": get_project_entitlement(project_id_str),
            "created": False,
            "regenerated": False,
            "normalized_ids": entitlement_repair,
        }

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
    user_id = _resolve_entitlement_user_id(project, order)
    if not _to_object_id(user_id):
        raise ValueError(f"Unable to resolve a valid user_id for entitlement generation for project {project_id_str}.")

    entitlement = upsert_project_entitlement(
        project_id=project_id_str,
        user_id=user_id,
        package_code=package_fields["package_code"],
        active_addons=list((existing or {}).get("active_addons") or []),
        maintenance_plan=maintenance_plan,
        purchased_at=purchased_at,
        delivered_at=delivered_at,
        status="active",
    )
    if entitlement:
        project_id_filter = {"$in": _project_id_candidates(project_id_str)}
        _db()["project_entitlements"].update_one(
            {"project_id": project_id_filter},
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

    entitlement_before = get_project_entitlement(project_id_str)
    package_fields = _package_fields_from_context(project, order, entitlement_before)
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
        user_id_text=_resolve_entitlement_user_id(project, order),
    )
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
    mint_repair = rebuild_mint_summary_for_project(project_id_str)

    return {
        "project": _serialize_project(refreshed_project),
        "order": _serialize_order(refreshed_order),
        "entitlement": get_project_entitlement(project_id_str),
        "repairs": {
            "project_updated_fields": sorted(project_updates.keys()),
            "order": order_repair,
            "entitlement_record": entitlement_repair,
            "entitlement_generation": entitlement_generation,
            "mint": mint_repair,
        },
        "readiness": readiness,
    }


def repair_project_mint_status(*, project_id: str) -> dict[str, Any]:
    if not _normalize(project_id):
        raise ValueError("Project id is required.")
    return rebuild_mint_summary_for_project(project_id)


def resync_current_mint_receipt(*, project_id: str) -> dict[str, Any]:
    canonical = resolve_canonical_mint_status(project_id, include_history=False)
    mint_record_id = _normalize(canonical.get("current_mint_record_id"))
    if not mint_record_id:
        raise ValueError("Project has no mint record to sync.")
    sync_result = sync_receipt_for_mint_record(mint_record_id)
    return {
        "project_id": _normalize(project_id),
        "sync_result": sync_result,
        "canonical_mint": resolve_canonical_mint_status(project_id, include_history=True),
    }


def run_readiness_check(*, project_id: str, order_id: str = "") -> dict[str, Any]:
    project, order = _resolve_project_order_context(project_id, preferred_order_id=order_id)
    project_id_str = _normalize(project.get("_id"))
    entitlement = get_project_entitlement(project_id_str)
    package_fields = _package_fields_from_context(project, order, entitlement)

    project_package_code = normalize_package_code(_normalize(project.get("package_code") or project.get("package_slug")))
    order_package_code = normalize_package_code(_normalize((order or {}).get("package_code") or (order or {}).get("package_slug")))
    entitlement_package_code = normalize_package_code(_normalize((entitlement or {}).get("package_code")))
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
    canonical_mint = resolve_canonical_mint_status(project_id_str, include_history=False)
    mint_already_completed = bool(canonical_mint.get("is_minted"))

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
    if mint_already_completed:
        mint_review_ready = True
        mint_eligible = True
    blocking_reasons: list[str] = []
    if mint_already_completed:
        blocking_reasons = []
    elif not package_synced:
        blocking_reasons.append("package_not_synced")
    if not mint_already_completed and not lane_assigned:
        blocking_reasons.append("lane_not_assigned")
    if not mint_already_completed and not order_linked:
        blocking_reasons.append("order_not_linked")
    if not mint_already_completed and not entitlement_exists:
        blocking_reasons.append("missing_entitlement")
    if not mint_already_completed and not uploads_present:
        blocking_reasons.append("uploads_missing")
    if not mint_already_completed and not status_ready:
        blocking_reasons.append("project_not_build_ready")
    if not mint_already_completed and not phase_ready:
        blocking_reasons.append("project_not_intake_approved")
    if not mint_already_completed:
        for reason in (mint_eligibility.get("reasons") or []):
            normalized_reason = _normalize(reason)
            if normalized_reason and normalized_reason not in blocking_reasons:
                blocking_reasons.append(normalized_reason)
        for warning in package_fields.get("warnings") or []:
            normalized_warning = _normalize(warning)
            if normalized_warning and normalized_warning not in blocking_reasons:
                blocking_reasons.append(normalized_warning)

    return {
        "project_id": project_id_str,
        "package_synced": package_synced,
        "lane_assigned": lane_assigned,
        "order_linked": order_linked,
        "entitlement_exists": entitlement_exists,
        "uploads_present": uploads_present,
        "build_ready": status_ready,
        "intake_approved": phase_ready,
        "mint_review_ready": mint_review_ready,
        "mint_eligible": mint_eligible,
        "mint_already_completed": mint_already_completed,
        "canonical_mint": canonical_mint,
        "summary": {
            "package_synced": "yes" if package_synced else "no",
            "lane_assigned": "yes" if lane_assigned else "no",
            "order_linked": "yes" if order_linked else "no",
            "entitlement_exists": "yes" if entitlement_exists else "no",
            "mint_eligible": "yes" if mint_eligible else "no",
            "canonical_mint_status": canonical_mint.get("current_status") or "none",
        },
        "mint_policy": mint_eligibility.get("mint_policy"),
        "mint_reasons": mint_eligibility.get("reasons") or [],
        "blocking_reasons": blocking_reasons,
        "package": package_fields,
        "warnings": package_fields.get("warnings") or [],
    }


def enable_mint_review(*, project_id: str, order_id: str = "") -> dict[str, Any]:
    db = _db()
    readiness = run_readiness_check(project_id=project_id, order_id=order_id)
    if readiness.get("mint_already_completed"):
        return {
            "project_id": _normalize(project_id),
            "mint_review_ready": True,
            "auto_mint_allowed": False,
            "auto_mint_executed": False,
            "skipped_reason": "canonical_mint_already_minted",
            "canonical_mint": readiness.get("canonical_mint"),
        }
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
    package_fields = _package_fields_from_context(project, order, entitlement)
    readiness = run_readiness_check(project_id=project_id_str)

    related_orders = []
    db = _db()
    if project_id_str:
        cursor = db["orders"].find(
            {"project_id": {"$in": _project_id_candidates(project_id_str)}}
        ).sort("created_at", -1).limit(10)
        related_orders = [_serialize_order(item) for item in cursor if _serialize_order(item)]

    return {
        "project": _serialize_project(project),
        "order": _serialize_order(order),
        "package": package_fields,
        "warnings": package_fields.get("warnings") or [],
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


def _find_matching_approved_project_for_order(order: dict[str, Any]) -> dict[str, Any] | None:
    db = _db()
    email = _normalize_email(order.get("email"))
    user_id = _normalize(order.get("user_id"))
    user_oid = _to_object_id(user_id)
    order_package = normalize_package_code(
        _normalize(order.get("package_code") or order.get("package_slug") or order.get("package_type"))
    )

    filters: list[dict[str, Any]] = []
    if email:
        filters.append({"owner_email": email})
    if user_id:
        filters.append({"owner_user_id": user_id})
    if user_oid is not None:
        filters.append({"owner_user_id": str(user_oid)})

    if not filters:
        return None

    ranked: list[tuple[int, datetime, dict[str, Any]]] = []
    for project in db["projects"].find({"$or": filters}).sort("updated_at", -1).limit(100):
        if _project_is_approved(project):
            project_package = normalize_package_code(
                _normalize(project.get("package_code") or project.get("package_slug") or project.get("package_type"))
            )
            score = 10
            if order_package and project_package == order_package:
                score += 20
            if _normalize(project.get("owner_email")).lower() == email:
                score += 5
            updated_at = _coerce_datetime(project.get("updated_at")) or datetime.min.replace(tzinfo=UTC)
            ranked.append((score, updated_at, project))

    if not ranked:
        return None
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return ranked[0][2]


def _order_has_project_link(order: dict[str, Any]) -> bool:
    project_ref = _normalize(order.get("project_id"))
    return bool(_to_object_id(project_ref))


def _link_order_to_project_document(order: dict[str, Any], project: dict[str, Any]) -> bool:
    db = _db()
    project_id_str = _normalize(project.get("_id") or project.get("id"))
    project_oid = _to_object_id(project_id_str)
    if project_oid is None:
        return False

    db["orders"].update_one(
        {"_id": order["_id"]},
        {"$set": {"project_id": project_oid}},
    )
    return True


def link_unlinked_paid_orders(*, limit: int = 500) -> dict[str, Any]:
    db = _db()
    scanned = 0
    linked = 0
    skipped = 0
    failures = 0
    linked_order_ids: list[str] = []

    cursor = db["orders"].find({"status": {"$in": list(PAID_ORDER_STATUSES)}}).sort("created_at", -1).limit(max(1, min(limit, MAX_BULK_ACTION_LIMIT)))
    for order in cursor:
        if not _is_paid_package_order(order):
            skipped += 1
            continue
        scanned += 1
        if _order_has_project_link(order):
            skipped += 1
            continue

        project = _find_matching_approved_project_for_order(order)
        if project is None:
            skipped += 1
            continue

        if _link_order_to_project_document(order, project):
            linked += 1
            linked_order_ids.append(_normalize(order.get("_id")))
        else:
            failures += 1

    return {
        "action": "link_unlinked_paid_orders",
        "scanned": scanned,
        "linked": linked,
        "skipped": skipped,
        "failed": failures,
        "order_ids": linked_order_ids[:50],
    }


def assign_missing_lanes(*, limit: int = 500) -> dict[str, Any]:
    db = _db()
    scanned = 0
    assigned = 0
    skipped = 0
    failures = 0
    project_ids: list[str] = []

    cursor = (
        db["projects"]
        .find(_approved_project_query())
        .sort("updated_at", -1)
        .limit(max(1, min(limit, MAX_BULK_ACTION_LIMIT)))
    )
    for project in cursor:
        scanned += 1
        if not _project_is_approved(project):
            skipped += 1
            continue

        lane = _normalize(project.get("project_lane")).lower()
        if lane in ALLOWED_LANES:
            skipped += 1
            continue

        project_id = _normalize(project.get("_id"))
        try:
            assign_lane(project_id=project_id)
            assigned += 1
            project_ids.append(project_id)
        except Exception:
            failures += 1

    return {
        "action": "assign_missing_lanes",
        "scanned": scanned,
        "assigned": assigned,
        "skipped": skipped,
        "failed": failures,
        "project_ids": project_ids[:50],
    }


def repair_missing_entitlements(*, limit: int = 500) -> dict[str, Any]:
    db = _db()
    scanned = 0
    repaired = 0
    skipped = 0
    failures = 0
    project_ids: list[str] = []

    cursor = (
        db["projects"]
        .find(_approved_project_query())
        .sort("updated_at", -1)
        .limit(max(1, min(limit, MAX_BULK_ACTION_LIMIT)))
    )
    for project in cursor:
        scanned += 1
        if not _project_is_approved(project):
            skipped += 1
            continue

        project_id = _normalize(project.get("_id"))
        if get_project_entitlement(project_id) is not None:
            skipped += 1
            continue

        order = _latest_linked_order(project_id) or _latest_user_order_for_project(project)
        if order is None or not _is_paid_package_order(order):
            skipped += 1
            continue

        if not _order_has_project_link(order):
            _link_order_to_project_document(order, project)

        try:
            generate_entitlement(
                project_id=project_id,
                order_id=_normalize(order.get("_id")),
                force=False,
            )
            repaired += 1
            project_ids.append(project_id)
        except Exception:
            failures += 1

    return {
        "action": "repair_missing_entitlements",
        "scanned": scanned,
        "repaired": repaired,
        "skipped": skipped,
        "failed": failures,
        "project_ids": project_ids[:50],
    }


def _serialize_datetime(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _search_regex(search: str) -> dict[str, Any] | None:
    normalized = _normalize(search)
    if not normalized:
        return None
    return {"$regex": re.escape(normalized), "$options": "i"}


def _flexible_name_regex(search: str) -> dict[str, Any] | None:
    parts = [part for part in re.split(r"\s+", _normalize(search)) if part]
    if not parts:
        return None
    return {"$regex": r"\s+".join(re.escape(part) for part in parts), "$options": "i"}


def _search_seed_sets(search: str) -> tuple[set[str], set[str], set[str], set[str]]:
    db = _db()
    regex = _search_regex(search)
    if regex is None:
        return set(), set(), set(), set()
    flexible_name_regex = _flexible_name_regex(search) or regex
    name_parts = [part for part in re.split(r"\s+", _normalize(search)) if part]
    first_last_filter: dict[str, Any] | None = None
    if len(name_parts) >= 2:
        first_last_filter = {
            "$and": [
                {"first_name": {"$regex": re.escape(name_parts[0]), "$options": "i"}},
                {"last_name": {"$regex": re.escape(name_parts[-1]), "$options": "i"}},
            ]
        }

    user_emails: set[str] = set()
    user_ids: set[str] = set()
    family_ids: set[str] = set()
    project_ids_from_mint: set[str] = set()

    user_search_filters: list[dict[str, Any]] = [
        {"email": regex},
        {"first_name": regex},
        {"last_name": regex},
        {"full_name": flexible_name_regex},
        {"birthday": regex},
        {"birth_date": regex},
        {"date_of_birth": regex},
        {"dob": regex},
        {"id_last4": regex},
        {"government_id_last4": regex},
    ]
    if first_last_filter:
        user_search_filters.append(first_last_filter)

    for user in db["users"].find(
        {"$or": user_search_filters},
        {"_id": 1, "email": 1},
    ).limit(300):
        user_email = _normalize_email(user.get("email"))
        user_id = _normalize(user.get("_id"))
        if user_email:
            user_emails.add(user_email)
        if user_id:
            user_ids.add(user_id)

    for family in db["families"].find(
        {"$or": [{"family_name": regex}, {"name": regex}]},
        {"_id": 1},
    ).limit(200):
        family_id = _normalize(family.get("_id"))
        if family_id:
            family_ids.add(family_id)

    for mint_record in db["mint_records"].find(
        {
            "$or": [
                {"project_id": regex},
                {"token_id": regex},
                {"public_token_id": regex},
                {"wallet_address": regex},
                {"certificate_id": regex},
            ]
        },
        {"project_id": 1},
    ).limit(300):
        project_id = _normalize(mint_record.get("project_id"))
        if project_id:
            project_ids_from_mint.add(project_id)

    return user_emails, user_ids, family_ids, project_ids_from_mint


def _order_supports_search(order: dict[str, Any], search: str, user_emails: set[str]) -> bool:
    normalized_search = _normalize(search).lower()
    if not normalized_search:
        return True

    haystack = " ".join(
        [
            _normalize(order.get("_id")),
            _normalize(order.get("email")),
            _normalize(order.get("package_name")),
            _normalize(order.get("package_code")),
            _normalize(order.get("package_slug")),
            _normalize(order.get("project_id")),
            _normalize(order.get("stripe_session_id")),
            _normalize(order.get("stripe_payment_link_id")),
            _normalize(order.get("session_id")),
            _normalize(order.get("order_id")),
            _normalize(order.get("wallet_address")),
            _normalize(order.get("token_id")),
            _normalize(order.get("certificate_id")),
            _normalize(order.get("id_last4")),
            _normalize(order.get("government_id_last4")),
        ]
    ).lower()
    if normalized_search in haystack:
        return True
    return _normalize_email(order.get("email")) in user_emails


def _project_supports_search(
    project: dict[str, Any],
    *,
    search: str,
    user_emails: set[str],
    user_ids: set[str],
    family_ids: set[str],
    mint_project_ids: set[str],
) -> bool:
    normalized_search = _normalize(search).lower()
    if not normalized_search:
        return True

    project_id = _normalize(project.get("_id") or project.get("id"))
    haystack = " ".join(
        [
            project_id,
            _normalize(project.get("name")),
            _normalize(project.get("project_name")),
            _normalize(project.get("owner_email")),
            _normalize(project.get("owner_user_id")),
            _normalize(project.get("family_id")),
            _normalize(project.get("household_id")),
            _normalize(project.get("package_name")),
            _normalize(project.get("package_code")),
            _normalize(project.get("package_slug")),
            _normalize(project.get("project_lane")),
            _normalize(project.get("status")),
            _normalize(project.get("phase")),
            _normalize(project.get("wallet_address")),
            _normalize(project.get("token_id")),
            _normalize(project.get("certificate_id")),
            _normalize(project.get("id_last4")),
            _normalize(project.get("government_id_last4")),
        ]
    ).lower()
    if normalized_search in haystack:
        return True
    owner_email = _normalize_email(project.get("owner_email"))
    owner_user_id = _normalize(project.get("owner_user_id"))
    family_id = _normalize(project.get("family_id"))
    return bool(
        project_id in mint_project_ids
        or owner_email in user_emails
        or owner_user_id in user_ids
        or family_id in family_ids
    )


def _case_alerts(
    *,
    project: dict[str, Any] | None,
    order: dict[str, Any] | None,
    entitlement: dict[str, Any] | None,
    readiness: dict[str, Any] | None,
    upload_count: int,
    duplicate_identity: bool,
) -> list[str]:
    alerts: list[str] = []
    mint_already_completed = bool((readiness or {}).get("mint_already_completed"))
    if not entitlement:
        alerts.append("missing_entitlement")

    lane = _normalize((project or {}).get("project_lane")).lower()
    if project is not None and lane not in ALLOWED_LANES:
        alerts.append("lane_unknown")

    if order and _is_paid_package_order(order) and not _normalize(order.get("project_id")):
        alerts.append("paid_order_not_linked")

    if readiness and readiness.get("mint_review_ready") and not readiness.get("mint_eligible"):
        alerts.append("mint_blocked")

    maintenance_status = _normalize((entitlement or {}).get("maintenance_status")).lower()
    if entitlement and maintenance_status in {"", "not_started"}:
        alerts.append("maintenance_not_started")

    if duplicate_identity:
        alerts.append("duplicate_admin_user_identity")

    if upload_count <= 0 and not mint_already_completed:
        alerts.append("upload_review_pending")

    return alerts


def _humanize_code(value: Any) -> str:
    words = re.sub(r"[_\-]+", " ", _normalize(value)).strip()
    return words.title() if words else "Operational guidance"


def _operator_guidance_item(code: str) -> dict[str, Any]:
    normalized_code = GUIDANCE_RULE_ALIASES.get(_normalize(code).lower(), _normalize(code).lower())
    rule = OPERATOR_GUIDANCE_RULES.get(normalized_code)
    if not rule:
        rule = {
            "title": _humanize_code(normalized_code),
            "rule": "The case has a state that should be reviewed before the next operation.",
            "next_action": "Run Readiness Check",
            "recommended_action": "run_readiness_check",
            "severity": "info",
        }
    return {
        "code": normalized_code,
        "title": rule["title"],
        "rule": rule["rule"],
        "next_action": rule["next_action"],
        "recommended_action": rule["recommended_action"],
        "severity": rule["severity"],
    }


def _operator_guidance_items(
    *,
    alerts: list[str] | None = None,
    readiness: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    include_mint_runtime: bool = False,
) -> list[dict[str, Any]]:
    codes: list[str] = []
    if readiness:
        codes.extend([_normalize(value) for value in readiness.get("blocking_reasons") or []])
        if readiness.get("mint_review_ready") and not readiness.get("mint_eligible"):
            codes.append("mint_blocked")
        if include_mint_runtime and not settings.nft_auto_mint_on_review_enabled and not readiness.get("mint_already_completed"):
            codes.append("mint_runtime_disabled")

    codes.extend([_normalize(value) for value in alerts or []])
    codes.extend([_normalize(value) for value in warnings or []])

    unique_codes: list[str] = []
    for code in codes:
        normalized_code = GUIDANCE_RULE_ALIASES.get(_normalize(code).lower(), _normalize(code).lower())
        if normalized_code and normalized_code not in unique_codes:
            unique_codes.append(normalized_code)

    severity_order = {"critical": 0, "warning": 1, "info": 2}
    items = [_operator_guidance_item(code) for code in unique_codes]
    items.sort(key=lambda item: severity_order.get(_normalize(item.get("severity")).lower(), 3))
    return items[:8]


def _case_queue_match(queue: str, alerts: list[str]) -> bool:
    normalized = _normalize(queue).lower()
    if normalized in {"", "all", "overview", "customer_cases", "projects", "system_health"}:
        return True
    if normalized == "orders":
        return "paid_order_not_linked" in alerts
    if normalized == "entitlements":
        return "missing_entitlement" in alerts
    if normalized == "mint_queue":
        return "mint_blocked" in alerts
    if normalized == "upload_review":
        return "upload_review_pending" in alerts
    if normalized == "billing_maintenance":
        return "maintenance_not_started" in alerts
    if normalized == "users":
        return "duplicate_admin_user_identity" in alerts
    if normalized == "audit":
        return True
    return True


def _find_duplicate_identity(email: str) -> bool:
    db = _db()
    normalized = _normalize_email(email)
    if not normalized:
        return False
    users = list(
        db["users"].find(
            {"email": normalized},
            {"role": 1, "access_tier": 1, "department_role": 1},
        ).limit(10)
    )
    if len(users) < 2:
        return False
    internal = 0
    external = 0
    for user in users:
        values = {
            _normalize(user.get("role")).lower(),
            _normalize(user.get("access_tier")).lower(),
            _normalize(user.get("department_role")).lower(),
        }
        if any(value in INTERNAL_ROLE_KEYS for value in values if value):
            internal += 1
        else:
            external += 1
    return internal > 0 and external > 0


def _workspace_audit_timeline(*, project_id: str, order_id: str = "", owner_email: str = "") -> list[dict[str, Any]]:
    del owner_email
    db = _db()
    conditions: list[dict[str, Any]] = []
    if project_id:
        project_id_values = _document_id_candidates(project_id)
        conditions.extend(
            [
                {"target_id": {"$in": project_id_values}},
                {"context.project_id": {"$in": project_id_values}},
                {"details.project_id": {"$in": project_id_values}},
            ]
        )
    if order_id:
        order_id_values = _document_id_candidates(order_id)
        conditions.extend(
            [
                {"target_id": {"$in": order_id_values}},
                {"context.order_id": {"$in": order_id_values}},
                {"details.order_id": {"$in": order_id_values}},
            ]
        )
    if not conditions:
        return []

    timeline: list[dict[str, Any]] = []
    for item in db["audit_logs"].find({"$or": conditions}).sort("timestamp", -1).limit(40):
        timeline.append(
            {
                "id": _normalize(item.get("_id")),
                "action": _normalize(item.get("action") or item.get("event")) or "event",
                "target_type": _normalize(item.get("target_type") or item.get("entity_type")) or "system",
                "target_id": _normalize(item.get("target_id") or item.get("entity_id")) or None,
                "actor_email": _normalize_email(item.get("actor_email")) or None,
                "actor_name": _normalize(item.get("actor_name")) or None,
                "result": _normalize(item.get("result")) or "success",
                "timestamp": _serialize_datetime(item.get("timestamp") or item.get("created_at")),
                "details": item.get("details") or {},
            }
        )
    return timeline


def _workspace_uploads_snapshot(project_id: str, owner_email: str) -> dict[str, Any]:
    del owner_email
    db = _db()
    if not project_id:
        return {"count": 0, "items": []}

    items: list[dict[str, Any]] = []
    cursor = db["uploaded_files"].find(
        {"project_id": {"$in": _project_id_candidates(project_id)}}
    ).sort("created_at", -1).limit(12)
    for item in cursor:
        items.append(
            {
                "id": _normalize(item.get("_id")),
                "project_id": _normalize_object_id(item.get("project_id")) or None,
                "filename": _normalize(item.get("original_filename") or item.get("filename")) or None,
                "category": _normalize(item.get("category")) or None,
                "uploaded_by": _normalize(item.get("uploaded_by")) or None,
                "status": _normalize(item.get("status")) or None,
                "created_at": _serialize_datetime(item.get("created_at")),
            }
        )
    return {"count": len(items), "items": items}


def _is_internal_user_document(user: dict[str, Any] | None) -> bool:
    if not user:
        return False
    values = {
        _normalize(user.get("role")).lower(),
        _normalize(user.get("access_tier")).lower(),
        _normalize(user.get("department_role")).lower(),
    }
    return any(value in INTERNAL_ROLE_KEYS for value in values if value)


def _user_display_name(user: dict[str, Any]) -> str:
    full_name = _normalize(user.get("full_name") or user.get("name"))
    if full_name:
        return full_name
    first_name = _normalize(user.get("first_name"))
    last_name = _normalize(user.get("last_name"))
    joined = " ".join([first_name, last_name]).strip()
    if joined:
        return joined
    email = _normalize_email(user.get("email"))
    return email.split("@")[0].replace(".", " ").replace("_", " ").title() if email else "Unknown User"


def _user_role_value(user: dict[str, Any]) -> str:
    return (
        _normalize(user.get("role"))
        or _normalize(user.get("access_tier"))
        or _normalize(user.get("department_role"))
        or "user"
    )


def _user_supports_search(user: dict[str, Any], search: str) -> bool:
    normalized_search = _normalize(search).lower()
    if not normalized_search:
        return True
    haystack = " ".join(
        [
            _normalize(user.get("_id")),
            _normalize(user.get("email")),
            _normalize(user.get("full_name")),
            _normalize(user.get("first_name")),
            _normalize(user.get("last_name")),
            _normalize(user.get("role")),
            _normalize(user.get("access_tier")),
            _normalize(user.get("department_role")),
            _normalize(user.get("status")),
            _normalize(user.get("birthday")),
            _normalize(user.get("birth_date")),
            _normalize(user.get("date_of_birth")),
            _normalize(user.get("dob")),
        ]
    ).lower()
    return normalized_search in haystack


def _serialize_user_case(user: dict[str, Any]) -> dict[str, Any]:
    user_id = _normalize_object_id(user.get("_id")) or _normalize(user.get("id"))
    if not user_id:
        return {}
    role = _user_role_value(user)
    is_internal = _is_internal_user_document(user)
    status_value = _normalize(user.get("status")) or "active"
    alerts: list[str] = []
    if status_value not in {"active", "enabled", ""}:
        alerts.append("user_inactive")
    if is_internal:
        alerts.append("internal_admin_identity")

    return {
        "case_id": f"user:{user_id}",
        "project_id": None,
        "order_id": None,
        "name": _user_display_name(user),
        "email": _normalize_email(user.get("email")) or None,
        "role": role,
        "project": "User account",
        "package": "Account",
        "package_name": "Account",
        "package_slug": "account",
        "package_code": "account",
        "package_normalization_status": "not_applicable",
        "lane": "admin" if is_internal else "customer",
        "project_lane": "admin" if is_internal else "customer",
        "lane_source": "user_role",
        "warnings": [],
        "status": status_value,
        "alerts": alerts,
        "operator_guidance": _operator_guidance_items(alerts=alerts),
        "quick_actions": ["refresh_case_data"],
        "mint_blocking_reasons": [],
        "updated_at": _serialize_datetime(user.get("updated_at") or user.get("last_login_at") or user.get("created_at")),
    }


def _list_user_account_cases(
    *,
    db: Any,
    search: str,
    safe_limit: int,
) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    cursor = db["users"].find({}).sort("updated_at", -1).limit(max(300, safe_limit * 10))
    for user in cursor:
        if not _user_supports_search(user, search):
            continue
        serialized = _serialize_user_case(user)
        if serialized:
            cases.append(serialized)
        if len(cases) >= safe_limit:
            break
    return cases


def _user_id_candidates(user: dict[str, Any]) -> list[Any]:
    user_id = _normalize_object_id(user.get("_id")) or _normalize(user.get("id"))
    candidates: list[Any] = []
    if user_id:
        candidates.append(user_id)
    oid = _to_object_id(user_id)
    if oid is not None:
        candidates.append(oid)
    return candidates


def _related_projects_for_user(user: dict[str, Any]) -> list[dict[str, Any]]:
    db = _db()
    filters: list[dict[str, Any]] = []
    user_id_values = _user_id_candidates(user)
    email = _normalize_email(user.get("email"))
    if user_id_values:
        filters.append({"owner_user_id": {"$in": user_id_values}})
    if email:
        filters.append({"owner_email": email})
    if not filters:
        return []
    cursor = db["projects"].find({"$or": filters}).sort("updated_at", -1).limit(20)
    return [_serialize_project(project) for project in cursor]


def _related_orders_for_user(user: dict[str, Any]) -> list[dict[str, Any]]:
    db = _db()
    filters: list[dict[str, Any]] = []
    user_id_values = _user_id_candidates(user)
    email = _normalize_email(user.get("email"))
    if user_id_values:
        filters.append({"user_id": {"$in": user_id_values}})
    if email:
        filters.append({"email": email})
    if not filters:
        return []
    cursor = db["orders"].find({"$or": filters}).sort("created_at", -1).limit(20)
    return [item for item in (_serialize_order(order) for order in cursor) if item]


def _serialize_entitlement_item(entitlement: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _normalize_object_id(entitlement.get("_id")) or None,
        "project_id": _normalize_object_id(entitlement.get("project_id")) or None,
        "user_id": _normalize_object_id(entitlement.get("user_id")) or None,
        "package_code": _normalize(entitlement.get("package_code")) or None,
        "package_name": _normalize(entitlement.get("package_name")) or None,
        "package_lane": _normalize(entitlement.get("package_lane")) or None,
        "maintenance_plan": _normalize(entitlement.get("maintenance_plan")) or None,
        "maintenance_status": _normalize(entitlement.get("maintenance_status")) or None,
        "status": _normalize(entitlement.get("status")) or None,
        "resolved_entitlements": entitlement.get("resolved_entitlements") or {},
        "created_at": _serialize_datetime(entitlement.get("created_at")),
        "updated_at": _serialize_datetime(entitlement.get("updated_at")),
    }


def _related_entitlements_for_user(
    user: dict[str, Any],
    project_ids: list[str],
) -> list[dict[str, Any]]:
    db = _db()
    filters: list[dict[str, Any]] = []
    user_id_values = _user_id_candidates(user)
    if user_id_values:
        filters.append({"user_id": {"$in": user_id_values}})

    project_id_values: list[Any] = []
    for project_id in project_ids:
        normalized_project_id = _normalize_object_id(project_id)
        if normalized_project_id:
            project_id_values.append(normalized_project_id)
        oid = _to_object_id(normalized_project_id)
        if oid is not None:
            project_id_values.append(oid)
    if project_id_values:
        filters.append({"project_id": {"$in": project_id_values}})
    if not filters:
        return []
    cursor = db["project_entitlements"].find({"$or": filters}).sort("updated_at", -1).limit(20)
    return [_serialize_entitlement_item(entitlement) for entitlement in cursor]


def _user_uploads_snapshot(user: dict[str, Any], project_ids: list[str]) -> dict[str, Any]:
    db = _db()
    filters: list[dict[str, Any]] = []
    email = _normalize_email(user.get("email"))
    if email:
        filters.append({"uploaded_by": email})
    project_id_values = [_normalize_object_id(project_id) for project_id in project_ids if _normalize_object_id(project_id)]
    if project_id_values:
        filters.append({"project_id": {"$in": project_id_values}})
    if not filters:
        return {"count": 0, "items": []}

    items: list[dict[str, Any]] = []
    for item in db["uploaded_files"].find({"$or": filters}).sort("created_at", -1).limit(20):
        items.append(
            {
                "id": _normalize_object_id(item.get("_id")) or None,
                "project_id": _normalize_object_id(item.get("project_id")) or None,
                "family_id": _normalize_object_id(item.get("family_id")) or None,
                "member_id": _normalize_object_id(item.get("member_id")) or None,
                "filename": _normalize(item.get("original_filename") or item.get("filename")) or None,
                "category": _normalize(item.get("category")) or None,
                "uploaded_by": _normalize(item.get("uploaded_by")) or None,
                "status": _normalize(item.get("status")) or None,
                "created_at": _serialize_datetime(item.get("created_at")),
            }
        )
    return {"count": len(items), "items": items}


def _user_audit_timeline(user: dict[str, Any]) -> list[dict[str, Any]]:
    db = _db()
    user_id = _normalize_object_id(user.get("_id")) or _normalize(user.get("id"))
    email = _normalize_email(user.get("email"))
    conditions: list[dict[str, Any]] = []
    if user_id:
        conditions.extend(
            [
                {"actor_user_id": user_id},
                {"target_id": user_id},
                {"context.user_id": user_id},
                {"details.user_id": user_id},
            ]
        )
    if email:
        conditions.append({"actor_email": email})
    if not conditions:
        return []

    timeline: list[dict[str, Any]] = []
    for item in db["audit_logs"].find({"$or": conditions}).sort("timestamp", -1).limit(40):
        timeline.append(
            {
                "id": _normalize_object_id(item.get("_id")) or None,
                "action": _normalize(item.get("action") or item.get("event")) or "event",
                "target_type": _normalize(item.get("target_type") or item.get("entity_type")) or "user",
                "target_id": _normalize_object_id(item.get("target_id") or item.get("entity_id")) or None,
                "actor_email": _normalize_email(item.get("actor_email")) or None,
                "actor_name": _normalize(item.get("actor_name")) or None,
                "result": _normalize(item.get("result")) or "success",
                "timestamp": _serialize_datetime(item.get("timestamp") or item.get("created_at")),
                "details": item.get("details") or {},
            }
        )
    return timeline


def _find_case_user(*, email: str = "", user_id: str = "") -> dict[str, Any] | None:
    db = _db()
    normalized_user_id = _normalize(user_id)
    user_oid = _to_object_id(normalized_user_id)
    projection = {
        "_id": 1,
        "email": 1,
        "full_name": 1,
        "first_name": 1,
        "last_name": 1,
        "birthday": 1,
        "birth_date": 1,
        "date_of_birth": 1,
        "dob": 1,
        "role": 1,
        "access_tier": 1,
        "department_role": 1,
        "status": 1,
        "created_at": 1,
        "updated_at": 1,
        "last_login_at": 1,
    }

    if user_oid is not None:
        user = db["users"].find_one({"_id": user_oid}, projection)
        if user:
            return user
    if normalized_user_id:
        user = db["users"].find_one({"_id": normalized_user_id}, projection)
        if user:
            return user

    normalized_email = _normalize_email(email)
    if not normalized_email:
        return None

    users = list(db["users"].find({"email": normalized_email}, projection).limit(20))
    customer_users = [user for user in users if not _is_internal_user_document(user)]
    return (customer_users or users or [None])[0]


def _user_identity_snapshot(*, email: str = "", user_id: str = "") -> dict[str, Any]:
    normalized_email = _normalize_email(email)
    normalized_user_id = _normalize(user_id)
    user = _find_case_user(email=normalized_email, user_id=normalized_user_id)
    if not user:
        return {
            "user_id": normalized_user_id or None,
            "full_name": None,
            "email": normalized_email or None,
            "birthday": None,
            "role": "customer",
            "admin_user_relationship": "customer_record",
        }

    full_name = _normalize(user.get("full_name")) or " ".join(
        [_normalize(user.get("first_name")), _normalize(user.get("last_name"))]
    ).strip()
    role = _normalize(user.get("role") or user.get("access_tier") or user.get("department_role")) or "customer"
    return {
        "user_id": _normalize_object_id(user.get("_id")) or normalized_user_id or None,
        "full_name": full_name or None,
        "first_name": _normalize(user.get("first_name")) or None,
        "last_name": _normalize(user.get("last_name")) or None,
        "email": _normalize_email(user.get("email")) or normalized_email or None,
        "birthday": _serialize_datetime(
            user.get("birthday") or user.get("birth_date") or user.get("date_of_birth") or user.get("dob")
        ),
        "role": role,
        "admin_user_relationship": "internal_admin_identity"
        if role.lower() in INTERNAL_ROLE_KEYS
        else "customer_record",
    }


def _linked_family_snapshot(project: dict[str, Any] | None) -> dict[str, Any]:
    if not project:
        return {"family_id": None, "household_id": None, "family_name": None, "household_name": None}

    db = _db()
    family_id = _normalize((project or {}).get("family_id"))
    household_id = _normalize((project or {}).get("household_id"))
    family: dict[str, Any] | None = None
    household: dict[str, Any] | None = None

    if family_id:
        family_oid = _to_object_id(family_id)
        family = db["families"].find_one({"_id": family_oid}) if family_oid else None
        family = family or db["families"].find_one({"_id": family_id})
        family = family or db["families"].find_one({"id": family_id})
    if household_id:
        household_oid = _to_object_id(household_id)
        household = db["households"].find_one({"_id": household_oid}) if household_oid else None
        household = household or db["households"].find_one({"_id": household_id})
        household = household or db["households"].find_one({"id": household_id})

    return {
        "family_id": family_id or None,
        "household_id": household_id or None,
        "family_name": _normalize((family or {}).get("family_name") or (family or {}).get("name")) or None,
        "household_name": _normalize((household or {}).get("household_name") or (household or {}).get("name")) or None,
    }


def _mint_record_snapshot(project_id: str) -> dict[str, Any]:
    if not project_id:
        return {}

    canonical = resolve_canonical_mint_status(project_id, include_history=True)
    current = canonical.get("current_record") or {}
    if not current:
        return {
            "mint_record_id": None,
            "mint_status": "none",
            "current_status": "none",
            "token_id": None,
            "tx_hash": None,
            "wallet_address": None,
            "chain": settings.nft_chain,
            "version_number": None,
            "error_state": None,
            "mint_queue_status": "not_queued",
            "historical_attempt_count": 0,
        }

    return {
        "mint_record_id": current.get("id"),
        "mint_status": canonical.get("current_status"),
        "current_status": canonical.get("current_status"),
        "token_id": canonical.get("token_id") or current.get("public_token_id"),
        "tx_hash": canonical.get("tx_hash"),
        "wallet_address": canonical.get("wallet") or current.get("wallet_address"),
        "chain": canonical.get("chain") or settings.nft_chain,
        "contract_address": canonical.get("contract_address") or settings.nft_contract_address,
        "version_number": canonical.get("version_number"),
        "error_state": canonical.get("error_message") if canonical.get("is_current_failed") else None,
        "error_code": canonical.get("error_code") if canonical.get("is_current_failed") else None,
        "mint_queue_status": canonical.get("current_status") or "not_queued",
        "historical_attempt_count": canonical.get("historical_attempt_count", 0),
        "historical_attempts": [
            {
                "mint_record_id": record.get("id"),
                "status": record.get("canonical_mint_status") or record.get("mint_status"),
                "version_number": record.get("version_number"),
                "token_id": record.get("token_id"),
                "tx_hash": record.get("tx_hash"),
                "error_code": record.get("error_code"),
                "error_message": record.get("error_message") if record.get("canonical_mint_status") == "failed" else None,
                "updated_at": _serialize_datetime(record.get("updated_at")),
            }
            for record in canonical.get("history", [])
            if record.get("is_historical")
        ],
        "created_at": _serialize_datetime(current.get("created_at")),
        "updated_at": _serialize_datetime(current.get("updated_at")),
    }


def _workspace_related_orders(
    *,
    project_id: str,
    primary_order: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    db = _db()
    seen: set[str] = set()
    related_orders: list[dict[str, Any]] = []

    def append_order(order: dict[str, Any] | None) -> None:
        serialized = _serialize_order(order)
        order_id = _normalize((serialized or {}).get("id"))
        if not serialized or not order_id or order_id in seen:
            return
        seen.add(order_id)
        related_orders.append(serialized)

    if project_id:
        cursor = db["orders"].find(
            {"project_id": {"$in": _project_id_candidates(project_id)}}
        ).sort("created_at", -1).limit(10)
        for order in cursor:
            append_order(order)
        if _order_project_id_matches(primary_order, project_id):
            append_order(primary_order)
        return related_orders[:10]

    append_order(primary_order)
    return related_orders


def _build_user_workspace_payload(user: dict[str, Any]) -> dict[str, Any]:
    user_id = _normalize_object_id(user.get("_id")) or _normalize(user.get("id"))
    if not user_id:
        raise ValueError("User account not found.")

    role = _user_role_value(user)
    is_internal = _is_internal_user_document(user)
    related_projects = _related_projects_for_user(user)
    related_orders = _related_orders_for_user(user)
    project_ids = [
        _normalize_object_id(project.get("id"))
        for project in related_projects
        if _normalize_object_id(project.get("id"))
    ]
    related_entitlements = _related_entitlements_for_user(user, project_ids)
    uploads = _user_uploads_snapshot(user, project_ids)
    audit = _user_audit_timeline(user)
    primary_project = related_projects[0] if related_projects else {}
    primary_order = related_orders[0] if related_orders else {}
    primary_entitlement = related_entitlements[0] if related_entitlements else {}

    package_code = (
        _normalize(primary_entitlement.get("package_code"))
        or _normalize(primary_order.get("package_code"))
        or _normalize(primary_project.get("package_code"))
        or "account"
    )
    package_name = (
        _normalize(primary_entitlement.get("package_name"))
        or _normalize(primary_order.get("package_name"))
        or _normalize(primary_project.get("package_name"))
        or "Account"
    )
    package_lane = (
        _normalize(primary_entitlement.get("package_lane"))
        or _normalize(primary_project.get("project_lane"))
        or _normalize(primary_project.get("lane"))
        or ("admin" if is_internal else "customer")
    )
    upload_categories = sorted(
        {
            _normalize(item.get("category"))
            for item in uploads.get("items", [])
            if _normalize(item.get("category"))
        }
    )
    alerts: list[str] = []
    if is_internal:
        alerts.append("internal_admin_identity")
    if not related_projects and not is_internal:
        alerts.append("customer_without_project")
    operator_guidance = _operator_guidance_items(alerts=alerts)
    display_name = _user_display_name(user)
    status_value = _normalize(user.get("status")) or "active"

    return {
        "case_id": f"user:{user_id}",
        "project": primary_project or None,
        "order": primary_order or None,
        "package": {
            "package_code": package_code,
            "package_slug": package_code,
            "package_name": package_name,
            "lane": package_lane,
            "project_lane": package_lane,
            "source": "user_account",
            "normalization_status": "not_applicable",
            "warnings": [],
        },
        "entitlement": primary_entitlement or None,
        "readiness": {
            "mint_review_ready": False,
            "mint_eligible": False,
            "mint_already_completed": False,
            "blocking_reasons": ["user_account_case"],
        },
        "uploads": uploads,
        "audit_timeline": audit,
        "alerts": alerts,
        "operator_guidance": operator_guidance,
        "warnings": [],
        "tabs": {
            "identity": {
                "user_id": user_id,
                "full_name": display_name,
                "first_name": _normalize(user.get("first_name")) or None,
                "last_name": _normalize(user.get("last_name")) or None,
                "email": _normalize_email(user.get("email")) or None,
                "birthday": _serialize_datetime(
                    user.get("birthday") or user.get("birth_date") or user.get("date_of_birth") or user.get("dob")
                ),
                "role": role,
                "status": status_value,
                "admin_user_relationship": "internal_admin_identity" if is_internal else "customer_record",
                "created_at": _serialize_datetime(user.get("created_at")),
                "updated_at": _serialize_datetime(user.get("updated_at")),
                "last_login_at": _serialize_datetime(user.get("last_login_at")),
            },
            "package_lane": {
                "package_slug": package_code,
                "package_name": package_name,
                "package_code": package_code,
                "lane": package_lane,
                "project_lane": package_lane,
                "source": "user_account",
                "related_project_count": len(related_projects),
                "related_order_count": len(related_orders),
                "entitlement_count": len(related_entitlements),
                "warnings": [],
                "package_normalization_status": "not_applicable",
                "package_normalized": True,
            },
            "orders_billing": {
                "package_slug": package_code,
                "package_name": package_name,
                "package_code": package_code,
                "lane": package_lane,
                "order_status": primary_order.get("status"),
                "paid": bool(primary_order and primary_order.get("status") in PAID_ORDER_STATUSES),
                "project_link_status": "linked" if primary_order.get("project_id") else "not_linked",
                "maintenance_state": primary_entitlement.get("maintenance_status"),
                "primary_order": primary_order,
                "related_orders": related_orders,
            },
            "project": {
                "project_name": primary_project.get("name"),
                "project_id": primary_project.get("id"),
                "package_slug": package_code,
                "package_name": package_name,
                "package_code": package_code,
                "lane": package_lane,
                "project_lane": package_lane,
                "build_status": primary_project.get("status"),
                "phase": primary_project.get("phase"),
                "source": primary_project.get("source"),
                "related_projects": related_projects,
                "uploads_summary": {
                    "count": uploads.get("count", 0),
                    "categories": upload_categories,
                },
            },
            "entitlements": {
                "entitlement_status": "exists" if related_entitlements else "missing",
                "package_code": primary_entitlement.get("package_code") or package_code,
                "package_lane": primary_entitlement.get("package_lane") or package_lane,
                "maintenance_plan": primary_entitlement.get("maintenance_plan"),
                "maintenance_status": primary_entitlement.get("maintenance_status"),
                "resolved_entitlements": primary_entitlement.get("resolved_entitlements") or {},
                "items": related_entitlements,
            },
            "uploads_verification": {
                "uploaded_files": uploads.get("count", 0),
                "file_categories": upload_categories,
                "review_status": "pending" if uploads.get("count", 0) <= 0 else "files_present",
                "verification_readiness": "ready" if uploads.get("count", 0) > 0 else "waiting_for_uploads",
                "items": uploads.get("items", []),
            },
            "mint_readiness": {
                "eligibility": "not_applicable",
                "runtime": "not_applicable",
                "current_state": "user_account_case",
                "decision": "User account cases do not mint directly.",
                "next_admin_action": "Review linked projects or orders",
                "blocking_reasons": ["user_account_case"],
                "guidance": operator_guidance,
                "historical_attempts": [],
                "historical_attempt_count": 0,
                "mint_readiness_computed": True,
            },
            "audit_timeline": audit,
        },
    }


def list_customer_cases(*, search: str = "", limit: int = 50, queue: str = "customer_cases") -> dict[str, Any]:
    db = _db()
    safe_limit = max(1, min(limit, 200))
    normalized_queue = _normalize(queue).lower()
    if normalized_queue == "users":
        return {
            "items": _list_user_account_cases(
                db=db,
                search=search,
                safe_limit=safe_limit,
            )
        }

    user_emails, user_ids, family_ids, mint_project_ids = _search_seed_sets(search)

    cases: list[dict[str, Any]] = []
    for project in db["projects"].find({}).sort("updated_at", -1).limit(max(400, safe_limit * 10)):
        if not _project_supports_search(
            project,
            search=search,
            user_emails=user_emails,
            user_ids=user_ids,
            family_ids=family_ids,
            mint_project_ids=mint_project_ids,
        ):
            continue

        project_id = _normalize(project.get("_id") or project.get("id"))
        order = _latest_linked_order(project_id) or _latest_user_order_for_project(project)
        entitlement = get_project_entitlement(project_id)
        package_fields = _package_fields_from_context(project, order, entitlement)
        readiness_order_id = (
            _normalize((order or {}).get("_id"))
            if _order_project_id_matches(order, project_id)
            else ""
        )
        readiness = run_readiness_check(project_id=project_id, order_id=readiness_order_id)
        upload_count = count_workspace_uploads(project_id=project_id)
        duplicate_identity = _find_duplicate_identity(_normalize_email(project.get("owner_email")))
        alerts = _case_alerts(
            project=project,
            order=order,
            entitlement=entitlement,
            readiness=readiness,
            upload_count=upload_count,
            duplicate_identity=duplicate_identity,
        )
        package_status = _normalize(package_fields.get("normalization_status"))
        if package_status == "unknown":
            alerts.append("package_unknown")
        elif package_status in {"alias_mapped", "recovered_from_order", "recovered_from_entitlement"}:
            alerts.append("package_normalization_needed")
        alerts.extend(package_fields.get("warnings") or [])
        alerts = list(dict.fromkeys(alerts))
        operator_guidance = _operator_guidance_items(
            alerts=alerts,
            readiness=readiness,
            warnings=package_fields.get("warnings") or [],
        )
        if not _case_queue_match(queue, alerts):
            continue

        owner_email = _normalize_email(project.get("owner_email"))
        user = _find_case_user(email=owner_email, user_id=_normalize(project.get("owner_user_id")))
        user_name = _normalize((user or {}).get("full_name")) or " ".join(
            [
                _normalize((user or {}).get("first_name")),
                _normalize((user or {}).get("last_name")),
            ]
        ).strip() or _normalize(project.get("name")) or "Unknown Customer"

        cases.append(
            {
                "case_id": project_id,
                "project_id": project_id,
                "order_id": readiness_order_id or None,
                "name": user_name,
                "email": owner_email or None,
                "role": _normalize((user or {}).get("role")) or "customer",
                "project": _normalize(project.get("name") or project.get("project_name")) or "Project",
                "package": _normalize(package_fields.get("package_name")) or "Unknown Package",
                "package_name": _normalize(package_fields.get("package_name")) or "Unknown Package",
                "package_slug": _normalize(package_fields.get("package_slug")) or "unknown",
                "package_code": _normalize(package_fields.get("package_code")) or "unknown",
                "package_normalization_status": package_status or "unknown",
                "lane": _normalize(package_fields.get("lane")) or "unknown",
                "project_lane": _normalize(package_fields.get("project_lane")) or "unknown",
                "lane_source": "project"
                if _project_lane_value(project)
                else _normalize(package_fields.get("source")) or "package_policy",
                "warnings": package_fields.get("warnings") or [],
                "status": _normalize(project.get("status")) or "unknown",
                "alerts": alerts,
                "operator_guidance": operator_guidance,
                "quick_actions": [
                    "sync_package",
                    "normalize_package",
                    "assign_lane",
                    "link_order_to_project",
                    "generate_entitlement",
                    "refresh_entitlement",
                    "run_readiness_check",
                    "queue_for_mint_review",
                    "repair_record",
                    "refresh_case_data",
                ],
                "mint_blocking_reasons": list((readiness or {}).get("blocking_reasons") or []),
                "updated_at": _serialize_datetime(project.get("updated_at") or project.get("created_at")),
            }
        )
        if len(cases) >= safe_limit:
            break

    if len(cases) < safe_limit:
        for order in db["orders"].find({"status": {"$in": list(PAID_ORDER_STATUSES)}}).sort("created_at", -1).limit(max(300, safe_limit * 8)):
            if _normalize(order.get("project_id")):
                continue
            if not _order_supports_search(order, search, user_emails):
                continue

            order_id = _normalize(order.get("_id"))
            project = _find_matching_approved_project_for_order(order)
            package_fields = _package_fields_from_context(project or {}, order)
            alerts = ["paid_order_not_linked"]
            package_status = _normalize(package_fields.get("normalization_status"))
            if package_status == "unknown":
                alerts.append("package_unknown")
            elif package_status in {"alias_mapped", "recovered_from_order", "recovered_from_entitlement"}:
                alerts.append("package_normalization_needed")
            alerts.extend(package_fields.get("warnings") or [])
            alerts = list(dict.fromkeys(alerts))
            operator_guidance = _operator_guidance_items(
                alerts=alerts,
                warnings=package_fields.get("warnings") or [],
            )
            if not _case_queue_match(queue, alerts):
                continue

            cases.append(
                {
                    "case_id": f"order:{order_id}",
                    "project_id": _normalize((project or {}).get("_id")) or None,
                    "order_id": order_id,
                    "name": _normalize(order.get("full_name") or order.get("customer_name")) or "Order Case",
                    "email": _normalize_email(order.get("email")) or None,
                    "role": "customer",
                    "project": _normalize((project or {}).get("name") or (project or {}).get("project_name")) or "No linked project",
                    "package": _normalize(package_fields.get("package_name")) or "Unknown Package",
                    "package_name": _normalize(package_fields.get("package_name")) or "Unknown Package",
                    "package_slug": _normalize(package_fields.get("package_slug")) or "unknown",
                    "package_code": _normalize(package_fields.get("package_code")) or "unknown",
                    "package_normalization_status": package_status or "unknown",
                    "lane": _normalize(package_fields.get("lane")) or "unknown",
                    "project_lane": _normalize(package_fields.get("project_lane")) or "unknown",
                    "lane_source": "matched_project"
                    if _project_lane_value(project or {})
                    else _normalize(package_fields.get("source")) or "package_policy",
                    "warnings": package_fields.get("warnings") or [],
                    "status": _normalize(order.get("status")) or "unknown",
                    "alerts": alerts,
                    "operator_guidance": operator_guidance,
                    "quick_actions": [
                        "link_order_to_project",
                        "normalize_package",
                        "refresh_case_data",
                    ],
                    "mint_blocking_reasons": [],
                    "updated_at": _serialize_datetime(order.get("created_at")),
                }
            )
            if len(cases) >= safe_limit:
                break

    return {"items": cases[:safe_limit]}


def _build_case_workspace_payload(
    *,
    case_id: str,
    project: dict[str, Any] | None,
    order: dict[str, Any] | None,
) -> dict[str, Any]:
    project_id = _normalize((project or {}).get("_id") or (project or {}).get("id"))
    if project_id and order is not None and not _order_project_id_matches(order, project_id):
        order = None
    order_id = _normalize((order or {}).get("_id"))
    owner_email = _normalize_email((project or {}).get("owner_email") or (order or {}).get("email"))
    owner_user_id = _normalize((project or {}).get("owner_user_id") or (order or {}).get("user_id"))

    readiness = run_readiness_check(project_id=project_id, order_id=order_id) if project_id else {}
    entitlement = get_project_entitlement(project_id) if project_id else None
    package_fields = _package_fields_from_context(project or {}, order, entitlement)
    control_profile = get_package_control_profile(package_fields["package_code"]) or {}
    uploads = _workspace_uploads_snapshot(project_id, owner_email)
    audit = _workspace_audit_timeline(
        project_id=project_id,
        order_id=order_id,
        owner_email=owner_email,
    )
    identity = _user_identity_snapshot(email=owner_email, user_id=owner_user_id)
    family = _linked_family_snapshot(project)
    mint_record = _mint_record_snapshot(project_id)

    related_orders = _workspace_related_orders(
        project_id=project_id,
        primary_order=order,
    )

    project_snapshot = _serialize_project(project) if project else None
    order_snapshot = _serialize_order(order)
    entitlement_exists = entitlement is not None
    upload_categories = sorted(
        {
            _normalize(item.get("category"))
            for item in uploads.get("items", [])
            if _normalize(item.get("category"))
        }
    )
    workspace_alerts = _case_alerts(
        project=project,
        order=order,
        entitlement=entitlement,
        readiness=readiness,
        upload_count=int(uploads.get("count", 0) or 0),
        duplicate_identity=_find_duplicate_identity(owner_email),
    )
    package_status = _normalize(package_fields.get("normalization_status"))
    if package_status == "unknown":
        workspace_alerts.append("package_unknown")
    elif package_status in {"alias_mapped", "recovered_from_order", "recovered_from_entitlement"}:
        workspace_alerts.append("package_normalization_needed")
    workspace_alerts.extend(package_fields.get("warnings") or [])
    workspace_alerts = list(dict.fromkeys(workspace_alerts))
    operator_guidance = _operator_guidance_items(
        alerts=workspace_alerts,
        readiness=readiness,
        warnings=package_fields.get("warnings") or [],
        include_mint_runtime=True,
    )
    mint_guidance = _operator_guidance_items(
        alerts=["mint_blocked"] if readiness.get("mint_review_ready") and not readiness.get("mint_eligible") else [],
        readiness=readiness,
        warnings=package_fields.get("warnings") or [],
        include_mint_runtime=True,
    )
    next_mint_action = (
        "No mint action required"
        if readiness.get("mint_already_completed")
        else (
        "Queue for Mint Review"
        if readiness.get("mint_review_ready")
        else ((mint_guidance[0] or {}).get("next_action") if mint_guidance else "Run Readiness Check")
        )
    )

    display_name = (
        identity.get("full_name")
        or _normalize((order or {}).get("full_name") or (order or {}).get("customer_name"))
        or _normalize((project or {}).get("name") or (project or {}).get("project_name"))
        or "Customer Case"
    )

    return {
        "case_id": case_id,
        "project": project_snapshot,
        "order": order_snapshot,
        "package": package_fields,
        "entitlement": entitlement,
        "readiness": readiness,
        "uploads": uploads,
        "audit_timeline": audit,
        "alerts": workspace_alerts,
        "operator_guidance": operator_guidance,
        "warnings": package_fields.get("warnings") or [],
        "tabs": {
            "identity": {
                "full_name": display_name,
                "email": identity.get("email") or owner_email or None,
                "birthday": identity.get("birthday"),
                "role": identity.get("role") or "customer",
                "admin_user_relationship": identity.get("admin_user_relationship") or "customer_record",
                "household_name": family.get("household_name"),
                "family_name": family.get("family_name"),
                "user_id": identity.get("user_id") or owner_user_id or None,
            },
            "package_lane": {
                "package_slug": package_fields.get("package_slug"),
                "package_name": package_fields.get("package_name"),
                "package_code": package_fields.get("package_code"),
                "lane": package_fields.get("project_lane"),
                "project_lane": package_fields.get("project_lane"),
                "warnings": package_fields.get("warnings") or [],
                "package_policy_summary": {
                    "anchor_type": control_profile.get("anchor_type"),
                    "allows_automatic_anchor": (control_profile.get("launch_policy") or {}).get("allows_automatic_anchor"),
                    "auto_mint_enabled": (control_profile.get("mint_policy") or {}).get("auto_mint_enabled"),
                },
                "maintenance_defaults": control_profile.get("maintenance_default"),
                "package_normalization_status": package_fields.get("normalization_status"),
                "package_normalized": package_fields.get("normalization_status") != "unknown",
                "source": package_fields.get("source"),
                "raw_value": package_fields.get("raw_value"),
                "sources": package_fields.get("sources") or {},
            },
            "orders_billing": {
                "package_slug": package_fields.get("package_slug"),
                "package_name": package_fields.get("package_name"),
                "package_code": package_fields.get("package_code"),
                "lane": package_fields.get("lane"),
                "warnings": package_fields.get("warnings") or [],
                "order_status": (order_snapshot or {}).get("status"),
                "paid": bool(order and _is_paid_package_order(order)),
                "stripe_session_id": (order_snapshot or {}).get("stripe_session_id"),
                "payment_link_id": (order_snapshot or {}).get("payment_link_id"),
                "project_link_status": "linked" if (order_snapshot or {}).get("project_id") else "not_linked",
                "subscription": (order_snapshot or {}).get("subscription_id"),
                "maintenance_state": (entitlement or {}).get("maintenance_status"),
                "next_charge_date": (order_snapshot or {}).get("next_charge_date")
                or _serialize_datetime((entitlement or {}).get("maintenance_renews_at")),
                "primary_order": order_snapshot,
                "related_orders": related_orders,
            },
            "project": {
                "project_name": (project_snapshot or {}).get("name"),
                "project_id": project_id or None,
                "package_slug": package_fields.get("package_slug"),
                "package_name": package_fields.get("package_name"),
                "package_code": package_fields.get("package_code"),
                "lane": package_fields.get("lane"),
                "project_lane": package_fields.get("project_lane"),
                "warnings": package_fields.get("warnings") or [],
                "build_status": (project_snapshot or {}).get("status"),
                "phase": (project_snapshot or {}).get("phase"),
                "source": (project_snapshot or {}).get("source"),
                "intake_readiness": (project_snapshot or {}).get("intake_status")
                or ("ready" if readiness.get("intake_approved") else "not_ready"),
                "linked_family": family,
                "uploads_summary": {
                    "count": uploads.get("count", 0),
                    "categories": upload_categories,
                },
            },
            "entitlements": {
                "entitlement_status": "exists" if entitlement_exists else "missing",
                "package_code": (entitlement or {}).get("package_code") or package_fields.get("package_code"),
                "package_lane": (entitlement or {}).get("package_lane") or package_fields.get("project_lane"),
                "maintenance_plan": (entitlement or {}).get("maintenance_plan"),
                "maintenance_status": (entitlement or {}).get("maintenance_status"),
                "resolved_entitlements": (entitlement or {}).get("resolved_entitlements") or {},
            },
            "uploads_verification": {
                "uploaded_files": uploads.get("count", 0),
                "file_categories": upload_categories,
                "review_status": "pending" if uploads.get("count", 0) <= 0 else "files_present",
                "verification_readiness": "ready" if uploads.get("count", 0) > 0 else "waiting_for_uploads",
                "items": uploads.get("items", []),
            },
            "mint_readiness": {
                "package_mint_policy": readiness.get("mint_policy") or (control_profile.get("mint_policy") or {}),
                "eligibility": "minted" if readiness.get("mint_already_completed") else "eligible" if readiness.get("mint_eligible") else "blocked",
                "runtime": "enabled" if settings.nft_auto_mint_on_review_enabled else "disabled",
                "current_state": mint_record.get("current_status") or ("mint_ready" if readiness.get("mint_eligible") else "blocked"),
                "decision": "Minted successfully" if readiness.get("mint_already_completed") else "Ready for mint review" if readiness.get("mint_review_ready") else "Readiness gates are still blocking mint review",
                "next_admin_action": next_mint_action,
                "approvals": {
                    "customer_public_safe_approval_required": (
                        (control_profile.get("mint_policy") or {}).get("requires_customer_public_safe_approval")
                    ),
                    "mint_review_ready": readiness.get("mint_review_ready"),
                },
                "token_id": mint_record.get("token_id"),
                "tx_hash": mint_record.get("tx_hash"),
                "chain": mint_record.get("chain"),
                "version_number": mint_record.get("version_number"),
                "wallet": mint_record.get("wallet_address"),
                "error_state": mint_record.get("error_state"),
                "mint_queue_status": mint_record.get("mint_queue_status"),
                "historical_attempt_count": mint_record.get("historical_attempt_count", 0),
                "historical_attempts": mint_record.get("historical_attempts") or [],
                "blocking_reasons": readiness.get("blocking_reasons") or [],
                "guidance": mint_guidance,
                "mint_readiness_computed": True,
            },
            "audit_timeline": audit,
        },
    }


def customer_case_workspace(case_id: str) -> dict[str, Any]:
    normalized_case_id = _normalize(case_id)
    if not normalized_case_id:
        raise ValueError("Case id is required.")

    if normalized_case_id.startswith("user:"):
        user_id = normalized_case_id.split(":", 1)[1]
        user = _find_case_user(user_id=user_id)
        if user is None:
            raise ValueError("User account case not found.")
        return _build_user_workspace_payload(user)

    if normalized_case_id.startswith("order:"):
        order_id = normalized_case_id.split(":", 1)[1]
        order = _order_by_id(order_id)
        if order is None:
            raise ValueError("Order case not found.")
        project = _project_by_id(_normalize(order.get("project_id")))
        return _build_case_workspace_payload(
            case_id=normalized_case_id,
            project=project,
            order=order,
        )

    project, order = _resolve_project_order_context(normalized_case_id)
    return _build_case_workspace_payload(
        case_id=normalized_case_id,
        project=project,
        order=order,
    )


def normalize_broken_package_records(*, limit: int = 500) -> dict[str, Any]:
    db = _db()
    scanned = 0
    normalized_count = 0
    failures = 0
    project_ids: list[str] = []

    cursor = db["projects"].find(_approved_project_query()).sort("updated_at", -1).limit(max(1, min(limit, MAX_BULK_ACTION_LIMIT)))
    for project in cursor:
        scanned += 1
        project_id = _normalize(project.get("_id"))
        try:
            sync_package(project_id=project_id)
            normalized_count += 1
            project_ids.append(project_id)
        except Exception:
            failures += 1

    return {
        "action": "normalize_broken_package_records",
        "scanned": scanned,
        "normalized": normalized_count,
        "failed": failures,
        "project_ids": project_ids[:50],
    }


def refresh_mint_readiness(*, limit: int = 500) -> dict[str, Any]:
    db = _db()
    scanned = 0
    ready = 0
    blocked = 0
    failures = 0
    items: list[dict[str, Any]] = []

    cursor = db["projects"].find(_approved_project_query()).sort("updated_at", -1).limit(max(1, min(limit, MAX_BULK_ACTION_LIMIT)))
    for project in cursor:
        scanned += 1
        project_id = _normalize(project.get("_id"))
        try:
            mint_repair = repair_project_mint_status(project_id=project_id)
            readiness = run_readiness_check(project_id=project_id)
            if readiness.get("mint_review_ready"):
                ready += 1
            else:
                blocked += 1
            items.append(
                {
                    "project_id": project_id,
                    "mint_review_ready": bool(readiness.get("mint_review_ready")),
                    "mint_eligible": bool(readiness.get("mint_eligible")),
                    "canonical_mint_status": (readiness.get("canonical_mint") or {}).get("current_status"),
                    "mint_repair": mint_repair.get("job_cleanup"),
                    "blocking_reasons": list(readiness.get("blocking_reasons") or []),
                }
            )
        except Exception:
            failures += 1

    return {
        "action": "refresh_mint_readiness",
        "scanned": scanned,
        "ready": ready,
        "blocked": blocked,
        "failed": failures,
        "items": items[:50],
    }


def repair_selected_records(*, project_ids: list[str], order_ids: list[str]) -> dict[str, Any]:
    repaired: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    generic_failure_message = "repair_failed"

    for project_id in [pid for pid in project_ids if _normalize(pid)]:
        try:
            repaired.append(repair_record(project_id=_normalize(project_id)))
        except Exception:
            failures.append({"project_id": _normalize(project_id), "error": generic_failure_message})

    for order_id in [oid for oid in order_ids if _normalize(oid)]:
        try:
            order = _order_by_id(_normalize(order_id))
            if order is None:
                failures.append({"order_id": _normalize(order_id), "error": "Order not found."})
                continue
            project = _project_by_id(_normalize(order.get("project_id")))
            if project is None:
                failures.append({"order_id": _normalize(order_id), "error": "Linked project not found."})
                continue
            repaired.append(repair_record(project_id=_normalize(project.get("_id")), order_id=_normalize(order_id)))
        except Exception:
            failures.append({"order_id": _normalize(order_id), "error": generic_failure_message})

    return {
        "action": "repair_selected_records",
        "repaired_count": len(repaired),
        "failed_count": len(failures),
        "failed": failures[:50],
    }


def repair_all_safe_records(*, limit: int = 500) -> dict[str, Any]:
    db = _db()
    scanned = 0
    repaired = 0
    failed = 0
    project_ids: list[str] = []

    cursor = db["projects"].find(_approved_project_query()).sort("updated_at", -1).limit(max(1, min(limit, MAX_BULK_ACTION_LIMIT)))
    for project in cursor:
        scanned += 1
        project_id = _normalize(project.get("_id"))
        try:
            repair_record(project_id=project_id)
            repaired += 1
            project_ids.append(project_id)
        except Exception:
            failed += 1

    return {
        "action": "repair_all_safe_records",
        "scanned": scanned,
        "repaired": repaired,
        "failed": failed,
        "project_ids": project_ids[:50],
    }


def execute_case_action(
    *,
    case_id: str,
    action: str,
    actor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_case_id = _normalize(case_id)
    normalized_action = _normalize(action).lower()
    if not normalized_case_id:
        raise ValueError("Case id is required.")

    order_id = ""
    project_id = normalized_case_id
    if normalized_case_id.startswith("order:"):
        order_id = normalized_case_id.split(":", 1)[1]
        order = _order_by_id(order_id)
        if order is None:
            raise ValueError("Order not found.")
        project_id = ""
        project = _project_by_id(_normalize(order.get("project_id")))
        if project is not None:
            project_id = _normalize(project.get("_id"))
    elif normalized_case_id.startswith("user:"):
        project_id = ""

    if normalized_action in {"refresh_case_data"}:
        payload = customer_case_workspace(normalized_case_id)
        _write_admin_action_audit(
            actor=actor,
            action=normalized_action,
            target_type="customer_case",
            target_id=normalized_case_id,
            context={"case_id": normalized_case_id, "project_id": project_id, "order_id": order_id},
            details={"refreshed": True},
        )
        return payload

    if normalized_case_id.startswith("user:"):
        raise ValueError("User account cases only support refresh_case_data.")

    if not project_id:
        raise ValueError("Action requires a linked project.")

    if not order_id:
        linked = _latest_linked_order(project_id)
        order_id = _normalize((linked or {}).get("_id"))

    action_handlers: dict[str, Callable[[], dict[str, Any]]] = {
        "sync_package": lambda: sync_package(project_id=project_id, order_id=order_id),
        "normalize_package": lambda: sync_package(project_id=project_id, order_id=order_id),
        "assign_lane": lambda: assign_lane(project_id=project_id),
        "link_order_to_project": lambda: link_order_to_project(order_id=order_id, project_id=project_id),
        "generate_entitlement": lambda: generate_entitlement(project_id=project_id, order_id=order_id, force=False),
        "refresh_entitlement": lambda: generate_entitlement(project_id=project_id, order_id=order_id, force=True),
        "run_readiness_check": lambda: run_readiness_check(project_id=project_id, order_id=order_id),
        "queue_for_mint_review": lambda: enable_mint_review(project_id=project_id, order_id=order_id),
        "repair_record": lambda: repair_record(project_id=project_id, order_id=order_id),
        "repair_mint_status": lambda: repair_project_mint_status(project_id=project_id),
        "rebuild_mint_summary": lambda: repair_project_mint_status(project_id=project_id),
        "resync_mint_receipt": lambda: resync_current_mint_receipt(project_id=project_id),
    }

    handler = action_handlers.get(normalized_action)
    if handler is None:
        raise ValueError("Unsupported case action.")
    if normalized_action == "link_order_to_project" and not order_id:
        raise ValueError("No order is available to link for this case.")
    try:
        result = handler()
        _write_admin_action_audit(
            actor=actor,
            action=normalized_action,
            target_type="project",
            target_id=project_id,
            after=result,
            context={"case_id": normalized_case_id, "project_id": project_id, "order_id": order_id},
        )
        return result
    except Exception as exc:
        _write_admin_action_audit(
            actor=actor,
            action=normalized_action,
            target_type="project",
            target_id=project_id,
            result="failed",
            context={"case_id": normalized_case_id, "project_id": project_id, "order_id": order_id},
            details={"error": str(exc)},
        )
        raise
