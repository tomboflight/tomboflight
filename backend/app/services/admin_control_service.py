from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Callable

from bson import ObjectId

from app.config import settings
from app.core.package_catalog import (
    canonicalize_package_identifier,
    get_package,
    get_package_control_profile,
    normalize_package_code,
)
from app.core.role_catalog import (
    INTERNAL_ADMIN_ROLE_CODES,
    SUPER_ADMIN_ROLE_CODES,
    normalize_role_code,
    resolve_primary_role_code,
)
from app.core.relationship_catalog import normalize_relationship_type
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
from app.services.email_service import send_household_invite_email

ALLOWED_LANES = {"portrait", "household", "network", "organization"}
BUILD_READY_STATUSES = {"build_ready", "in_production", "qa_review", "client_review", "delivered", "archived"}
INTAKE_APPROVED_PHASES = {"intake_approved", "build_started", "quality_review", "client_review", "delivery_complete", "delivered", "archived"}
PAID_ORDER_STATUSES = {"paid", "succeeded", "complete", "completed"}
OBJECT_ID_WRAPPER_PATTERN = re.compile(r"""^ObjectId\((["']?)([0-9a-fA-F]{24})\1\)$""")
MAX_BULK_ACTION_LIMIT = 5000
INTERNAL_ROLE_KEYS = set(INTERNAL_ADMIN_ROLE_CODES) | {"admin"}

ADMIN_CONTROL_QUEUES = [
    "overview",
    "intake_onboarding",
    "verification_upload_review",
    "workspace_access_invites",
    "build_fulfillment",
    "exceptions_escalations",
    "ops_reports",
    "traffic_awareness",
    "funnel_conversion",
    "package_demand",
    "campaign_performance",
    "content_performance",
    "marketing_reports",
    "money_now",
    "subscriptions_maintenance",
    "package_revenue",
    "finance_integrity",
    "payroll",
    "reports_exports",
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
    "marketing_dashboard",
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
    "queue_for_mint_review": {"admin.control.mint.readiness"},
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
    "intake_onboarding": {"admin.intake.review", "admin.control.view"},
    "verification_upload_review": {"uploads.admin.review", "verification.review"},
    "workspace_access_invites": {"admin.control.view"},
    "build_fulfillment": {"admin.control.view"},
    "exceptions_escalations": {"admin.control.view"},
    "ops_reports": {"admin.control.view"},
    "traffic_awareness": {"admin.analytics.read"},
    "funnel_conversion": {"admin.analytics.read"},
    "package_demand": {"admin.analytics.read"},
    "campaign_performance": {"admin.analytics.read"},
    "content_performance": {"admin.analytics.read"},
    "marketing_reports": {"admin.analytics.read"},
    "money_now": {"admin.control.billing", "admin.orders.read"},
    "subscriptions_maintenance": {"admin.control.billing", "admin.entitlements.read"},
    "package_revenue": {"admin.control.billing", "admin.orders.read"},
    "finance_integrity": {"admin.control.billing", "admin.audit.read"},
    "payroll": {"admin.control.billing"},
    "reports_exports": {"admin.control.billing"},
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
    "marketing_dashboard": {"admin.analytics.read"},
    "identity": {"admin.control.view"},
    "package_lane": {"admin.control.view"},
    "project": {"admin.control.view"},
    "orders_billing": {"admin.control.billing", "admin.orders.read"},
    "entitlements": {"admin.control.billing", "admin.entitlements.read"},
    "uploads_verification": {"uploads.admin.review", "verification.review"},
    "mint_readiness": {"admin.control.mint.readiness"},
    "audit_timeline": {"admin.audit.read"},
}

FINANCE_QUEUE_ALLOWLIST = [
    "money_now",
    "subscriptions_maintenance",
    "package_revenue",
    "finance_integrity",
    "payroll",
    "reports_exports",
]
FINANCE_TAB_ALLOWLIST = [
    "identity",
    "package_lane",
    "orders_billing",
    "project",
    "entitlements",
    "audit_timeline",
]
FINANCE_ACTION_ALLOWLIST = [
    "link_order_to_project",
    "generate_entitlement",
    "refresh_entitlement",
    "run_readiness_check",
    "refresh_case_data",
]
FINANCE_BULK_ACTION_ALLOWLIST = [
    "repair-missing-entitlements",
    "link-unlinked-paid-orders",
    "repair-selected-records",
]
FINANCE_WORKSPACE_ALERT_EXCLUDE = {
    "upload_review_pending",
    "mint_blocked",
    "mint_runtime_disabled",
    "project_not_build_ready",
    "project_not_intake_approved",
}
FINANCE_EVENT_TYPES = {
    "payment_captured",
    "refund_recorded",
    "credit_recorded",
    "billing_adjustment",
    "package_upgrade",
    "package_downgrade",
    "package_change",
}
MARKETING_QUEUE_ALLOWLIST = [
    "traffic_awareness",
    "funnel_conversion",
    "package_demand",
    "campaign_performance",
    "content_performance",
    "marketing_reports",
]
MARKETING_TAB_ALLOWLIST = [
    "marketing_dashboard",
]
OPERATIONS_QUEUE_ALLOWLIST = [
    "intake_onboarding",
    "verification_upload_review",
    "workspace_access_invites",
    "build_fulfillment",
    "exceptions_escalations",
    "ops_reports",
]
OPERATIONS_TAB_ALLOWLIST = [
    "identity",
    "package_lane",
    "project",
    "uploads_verification",
    "mint_readiness",
    "audit_timeline",
]
OPERATIONS_ACTION_ALLOWLIST = [
    "sync_package",
    "normalize_package",
    "assign_lane",
    "repair_record",
    "run_readiness_check",
    "queue_for_mint_review",
    "refresh_case_data",
]
OPERATIONS_BULK_ACTION_ALLOWLIST = [
    "assign-missing-lanes",
    "normalize-broken-package-records",
    "repair-selected-records",
    "repair-all-safe-records",
]

SUPER_ADMIN_USER_STATUS_VALUES = {
    "active",
    "enabled",
    "disabled",
    "suspended",
    "pending_activation",
    "archived",
}
SUPER_ADMIN_USER_STATE_ACTIONS = {
    "activate": "active",
    "restore": "active",
    "suspend": "suspended",
    "disable": "disabled",
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
    capabilities = {
        _normalize(capability).lower()
        for capability in (access_context.get("capabilities") or [])
        if _normalize(capability)
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

    primary_role = resolve_primary_role_code(role_codes, default="user")

    if primary_role == "operations_admin":
        allowed_queues = [
            queue
            for queue in OPERATIONS_QUEUE_ALLOWLIST
            if _has_any_permission(permissions, QUEUE_PERMISSIONS.get(queue, {"admin.control.view"}))
        ]
        allowed_tabs = [
            tab
            for tab in OPERATIONS_TAB_ALLOWLIST
            if _has_any_permission(permissions, TAB_PERMISSIONS.get(tab, {"admin.control.view"}))
        ]
        allowed_actions = [
            action
            for action in OPERATIONS_ACTION_ALLOWLIST
            if _has_any_permission(permissions, CASE_ACTION_PERMISSIONS.get(action, {"admin.control.view"}))
        ]
        allowed_bulk_actions = [
            action
            for action in OPERATIONS_BULK_ACTION_ALLOWLIST
            if _has_any_permission(permissions, BULK_ACTION_PERMISSIONS.get(action, {"admin.control.view"}))
        ]
    elif primary_role == "finance_admin":
        allowed_queues = [
            queue
            for queue in FINANCE_QUEUE_ALLOWLIST
            if _has_any_permission(permissions, QUEUE_PERMISSIONS.get(queue, {"admin.control.billing"}))
        ]
        allowed_tabs = [
            tab
            for tab in FINANCE_TAB_ALLOWLIST
            if _has_any_permission(permissions, TAB_PERMISSIONS.get(tab, {"admin.control.billing"}))
        ]
        allowed_actions = [
            action
            for action in FINANCE_ACTION_ALLOWLIST
            if _has_any_permission(permissions, CASE_ACTION_PERMISSIONS.get(action, {"admin.control.billing"}))
        ]
        allowed_bulk_actions = [
            action
            for action in FINANCE_BULK_ACTION_ALLOWLIST
            if _has_any_permission(permissions, BULK_ACTION_PERMISSIONS.get(action, {"admin.control.billing"}))
        ]
    elif primary_role == "marketing_admin":
        allowed_queues = [
            queue
            for queue in MARKETING_QUEUE_ALLOWLIST
            if _has_any_permission(permissions, QUEUE_PERMISSIONS.get(queue, {"admin.analytics.read"}))
        ]
        allowed_tabs = [
            tab
            for tab in MARKETING_TAB_ALLOWLIST
            if _has_any_permission(permissions, TAB_PERMISSIONS.get(tab, {"admin.analytics.read"}))
        ]
        allowed_actions = []
        allowed_bulk_actions = []

    return {
        "role_key": primary_role,
        "role_codes": role_codes,
        "capabilities": sorted(capabilities),
        "permissions": sorted(permissions),
        "allowed_queues": allowed_queues,
        "allowed_tabs": allowed_tabs,
        "allowed_actions": allowed_actions,
        "allowed_bulk_actions": allowed_bulk_actions,
        "is_wildcard": "*" in permissions,
        "is_super_admin": primary_role in SUPER_ADMIN_ROLE_CODES,
    }


def admin_control_queue_allowed(
    current_user: dict[str, Any],
    queue: str,
) -> bool:
    normalized_queue = _normalize(queue).lower()
    if not normalized_queue:
        return False
    profile = admin_control_access_profile(current_user)
    return normalized_queue in set(profile.get("allowed_queues") or [])


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


def ensure_finance_event_indexes() -> None:
    db = _db()
    collection = db["finance_events"]
    if not hasattr(collection, "create_index"):
        return
    try:
        collection.create_index([("event_key", 1)], name="event_key_1", unique=True, sparse=True)
    except Exception:
        pass
    try:
        collection.create_index([("occurred_at", -1)], name="occurred_at_-1")
    except Exception:
        pass
    try:
        collection.create_index([("event_type", 1)], name="event_type_1")
    except Exception:
        pass
    try:
        collection.create_index([("order_id", 1)], name="order_id_1")
    except Exception:
        pass
    try:
        collection.create_index([("project_id", 1)], name="project_id_1")
    except Exception:
        pass
    try:
        collection.create_index([("customer_email", 1)], name="customer_email_1")
    except Exception:
        pass


def _coerce_amount(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    normalized = _normalize(value).replace(",", "")
    if not normalized:
        return 0.0
    try:
        return float(normalized)
    except ValueError:
        return 0.0


def _order_amount_value(order: dict[str, Any]) -> float:
    for key in ("amount", "amount_total", "total_amount", "subtotal", "price"):
        amount = _coerce_amount(order.get(key))
        if amount:
            return amount
    return 0.0


def _package_lane_for_code(package_code: str) -> str:
    package = get_package(normalize_package_code(package_code) or "")
    lane = _normalize((package or {}).get("package_lane")).lower()
    return lane if lane in ALLOWED_LANES else "unknown"


def _finance_event_key_part(value: Any) -> str:
    return _normalize(value).replace("|", "¦")


def _build_finance_event_key(*, order_id: str, event_type: str, amount: float, occurred_at: datetime | None) -> str:
    occurred_text = occurred_at.isoformat() if occurred_at else "none"
    return "|".join(
        [
            _finance_event_key_part(order_id),
            _finance_event_key_part(event_type),
            _finance_event_key_part(round(float(amount), 2)),
            _finance_event_key_part(occurred_text),
        ]
    )


def _write_finance_event(
    *,
    event_type: str,
    order_id: str = "",
    project_id: str = "",
    customer_email: str = "",
    customer_user_id: str = "",
    amount: float = 0.0,
    currency: str = "usd",
    occurred_at: datetime | None = None,
    source: str = "system",
    details: dict[str, Any] | None = None,
) -> None:
    normalized_type = _normalize(event_type).lower()
    if normalized_type not in FINANCE_EVENT_TYPES:
        return
    normalized_order_id = _normalize(order_id)
    normalized_project_id = _normalize(project_id)
    normalized_customer_email = _normalize_email(customer_email)
    if not (normalized_order_id or normalized_project_id or normalized_customer_email):
        return
    ensure_finance_event_indexes()
    db = _db()
    collection = db["finance_events"]
    event_amount = round(float(amount or 0.0), 2)
    occurred = occurred_at or _now()
    event_key = _build_finance_event_key(
        order_id=normalized_order_id or normalized_project_id or normalized_customer_email,
        event_type=normalized_type,
        amount=event_amount,
        occurred_at=occurred,
    )
    if collection.find_one({"event_key": event_key}):
        return
    collection.insert_one(
        {
            "event_key": event_key,
            "event_type": normalized_type,
            "order_id": normalized_order_id or None,
            "project_id": normalized_project_id or None,
            "customer_email": normalized_customer_email or None,
            "customer_user_id": _normalize_object_id(customer_user_id) or None,
            "amount": event_amount,
            "currency": _normalize(currency).lower() or "usd",
            "occurred_at": occurred,
            "source": _normalize(source) or "system",
            "details": details or {},
            "created_at": _now(),
        }
    )


def _record_order_finance_events(order: dict[str, Any], *, source: str) -> None:
    if not isinstance(order, dict):
        return
    order_id = _normalize(order.get("_id"))
    if not order_id:
        return
    order_status = _normalize(order.get("status")).lower()
    order_amount = _order_amount_value(order)
    order_dt = _coerce_datetime(order.get("updated_at") or order.get("created_at"))
    order_package = normalize_package_code(_normalize(order.get("package_code") or order.get("package_slug")))
    order_lane = _normalize(order.get("lane") or order.get("package_lane")).lower() or _package_lane_for_code(order_package)

    if _is_paid_package_order(order):
        _write_finance_event(
            event_type="payment_captured",
            order_id=order_id,
            project_id=_normalize_object_id(order.get("project_id")),
            customer_email=_normalize_email(order.get("email")),
            customer_user_id=_normalize_object_id(order.get("user_id")),
            amount=order_amount,
            occurred_at=order_dt,
            source=source,
            details={
                "status": order_status,
                "package_code": order_package,
                "package_lane": order_lane,
            },
        )

    refund_amount = _coerce_amount(order.get("refund_amount") or order.get("refunded_amount"))
    if refund_amount > 0 or order_status in {"refunded", "refund"}:
        _write_finance_event(
            event_type="refund_recorded",
            order_id=order_id,
            project_id=_normalize_object_id(order.get("project_id")),
            customer_email=_normalize_email(order.get("email")),
            customer_user_id=_normalize_object_id(order.get("user_id")),
            amount=refund_amount if refund_amount > 0 else order_amount,
            occurred_at=_coerce_datetime(order.get("refunded_at") or order.get("updated_at") or order.get("created_at")),
            source=source,
            details={"status": order_status, "package_code": order_package},
        )

    credit_amount = _coerce_amount(
        order.get("credit_amount")
        or order.get("credited_amount")
        or order.get("customer_credit_amount")
        or order.get("credit_usd")
    )
    if credit_amount > 0:
        _write_finance_event(
            event_type="credit_recorded",
            order_id=order_id,
            project_id=_normalize_object_id(order.get("project_id")),
            customer_email=_normalize_email(order.get("email")),
            customer_user_id=_normalize_object_id(order.get("user_id")),
            amount=credit_amount,
            occurred_at=_coerce_datetime(order.get("credited_at") or order.get("updated_at") or order.get("created_at")),
            source=source,
            details={"status": order_status, "package_code": order_package},
        )

    adjustment_amount = _coerce_amount(
        order.get("adjustment_amount")
        or order.get("billing_adjustment_amount")
        or order.get("manual_adjustment_amount")
    )
    if adjustment_amount != 0:
        _write_finance_event(
            event_type="billing_adjustment",
            order_id=order_id,
            project_id=_normalize_object_id(order.get("project_id")),
            customer_email=_normalize_email(order.get("email")),
            customer_user_id=_normalize_object_id(order.get("user_id")),
            amount=adjustment_amount,
            occurred_at=_coerce_datetime(order.get("adjusted_at") or order.get("updated_at") or order.get("created_at")),
            source=source,
            details={"status": order_status, "package_code": order_package},
        )


def _record_package_transition_event(
    *,
    order_id: str = "",
    project_id: str = "",
    customer_email: str = "",
    customer_user_id: str = "",
    before_package_code: str,
    after_package_code: str,
    source: str,
) -> None:
    before_code = normalize_package_code(before_package_code)
    after_code = normalize_package_code(after_package_code)
    if not before_code or not after_code or before_code == after_code:
        return
    before_package = get_package(before_code) or {}
    before_price = _coerce_amount(before_package.get("base_price_usd"))
    after_price = _coerce_amount((get_package(after_code) or {}).get("base_price_usd"))
    event_type = "package_change"
    if after_price > before_price:
        event_type = "package_upgrade"
    elif after_price < before_price:
        event_type = "package_downgrade"
    _write_finance_event(
        event_type=event_type,
        order_id=order_id,
        project_id=project_id,
        customer_email=customer_email,
        customer_user_id=customer_user_id,
        amount=after_price - before_price,
        occurred_at=_now(),
        source=source,
        details={
            "before_package_code": before_code,
            "after_package_code": after_code,
            "before_package_lane": _package_lane_for_code(before_code),
            "after_package_lane": _package_lane_for_code(after_code),
            "before_base_price_usd": before_price,
            "after_base_price_usd": after_price,
        },
    )


def _serialize_finance_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _normalize_object_id(event.get("_id")) or None,
        "event_type": _normalize(event.get("event_type")) or "unknown",
        "order_id": _normalize_object_id(event.get("order_id")) or None,
        "project_id": _normalize_object_id(event.get("project_id")) or None,
        "customer_email": _normalize_email(event.get("customer_email")) or None,
        "customer_user_id": _normalize_object_id(event.get("customer_user_id")) or None,
        "amount": round(_coerce_amount(event.get("amount")), 2),
        "currency": _normalize(event.get("currency")) or "usd",
        "occurred_at": _serialize_datetime(event.get("occurred_at") or event.get("created_at")),
        "source": _normalize(event.get("source")) or "system",
        "details": event.get("details") or {},
    }


def _finance_event_query(
    *,
    project_id: str = "",
    order_id: str = "",
    owner_email: str = "",
) -> dict[str, Any]:
    filters: list[dict[str, Any]] = []
    normalized_project_id = _normalize(project_id)
    normalized_order_id = _normalize(order_id)
    normalized_owner_email = _normalize_email(owner_email)
    if normalized_project_id:
        filters.append({"project_id": {"$in": _document_id_candidates(normalized_project_id)}})
    if normalized_order_id:
        filters.append({"order_id": {"$in": _document_id_candidates(normalized_order_id)}})
    if normalized_owner_email:
        filters.append({"customer_email": normalized_owner_email})
    return {"$or": filters} if filters else {}


def _collect_finance_events(
    *,
    project_id: str = "",
    order_id: str = "",
    owner_email: str = "",
    limit: int = 40,
) -> list[dict[str, Any]]:
    db = _db()
    query = _finance_event_query(project_id=project_id, order_id=order_id, owner_email=owner_email)
    if not query:
        return []
    items: list[dict[str, Any]] = []
    for item in db["finance_events"].find(query).sort("occurred_at", -1).limit(max(1, min(limit, 200))):
        items.append(_serialize_finance_event(item))
    return items


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
    order_ref = order or {}
    previous_order_package = _normalize(order_ref.get("package_code") or order_ref.get("package_slug"))
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
                    "lane": package_fields["project_lane"],
                    "package_lane": package_fields["project_lane"],
                }
            },
        )

    refreshed_project, refreshed_order = _resolve_project_order_context(
        _normalize(project.get("_id")),
        preferred_order_id=_normalize((order or {}).get("_id")),
    )
    refreshed_order_id = _normalize((refreshed_order or {}).get("_id"))
    _record_package_transition_event(
        order_id=refreshed_order_id,
        project_id=_normalize(project.get("_id")),
        customer_email=_normalize_email(project.get("owner_email")),
        customer_user_id=_normalize(project.get("owner_user_id")),
        before_package_code=previous_order_package or _normalize(project.get("package_code")),
        after_package_code=package_fields["package_code"],
        source="admin_control.sync_package",
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


def _build_package_change_summary(*, before: dict[str, Any], proposed: dict[str, Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for section in ("project", "order", "entitlement"):
        before_section = dict(before.get(section) or {})
        after_section = dict(proposed.get(section) or {})
        all_keys = sorted(set(before_section.keys()) | set(after_section.keys()))
        for key in all_keys:
            if before_section.get(key) == after_section.get(key):
                continue
            changes.append(
                {
                    "scope": section,
                    "field": key,
                    "before": before_section.get(key),
                    "after": after_section.get(key),
                }
            )
    return changes


def super_admin_preview_package_change(
    *,
    project_id: str,
    package_code: str,
    project_lane: str = "",
    order_status: str = "",
) -> dict[str, Any]:
    normalized_project_id = _normalize(project_id)
    if not normalized_project_id:
        raise ValueError("Project id is required.")
    normalized_package = normalize_package_code(_normalize(package_code))
    package_profile = get_package(normalized_package)
    if not package_profile:
        raise ValueError("Unknown package code.")

    project, order = _resolve_project_order_context(
        normalized_project_id,
        allow_owner_order_fallback=True,
    )
    entitlement = get_project_entitlement(_normalize(project.get("_id")))
    before_package_fields = _package_fields_from_context(project, order, entitlement)

    target_lane = _normalize(project_lane).lower() or _normalize(package_profile.get("package_lane")).lower() or _normalize(project.get("project_lane")).lower()
    if target_lane not in ALLOWED_LANES:
        raise ValueError("Invalid project lane.")
    requested_order_status = _normalize(order_status).lower() or _normalize((order or {}).get("status")).lower() or "paid"

    project_after = {
        "package_code": normalized_package,
        "package_slug": normalized_package,
        "package_name": _normalize(package_profile.get("display_name")) or normalized_package,
        "project_lane": target_lane,
    }
    order_after = {
        "package_code": normalized_package,
        "package_slug": normalized_package,
        "package_name": _normalize(package_profile.get("display_name")) or normalized_package,
        "lane": target_lane if order else None,
        "package_lane": target_lane if order else None,
        "status": requested_order_status if order else None,
    }
    entitlement_after = {
        "package_code": normalized_package,
        "package_lane": target_lane,
    }
    before = {
        "project": {
            "package_code": before_package_fields.get("package_code"),
            "package_slug": before_package_fields.get("package_slug"),
            "package_name": before_package_fields.get("package_name"),
            "project_lane": _normalize(project.get("project_lane")) or before_package_fields.get("project_lane"),
        },
        "order": {
            "package_code": _normalize((order or {}).get("package_code")),
            "package_slug": _normalize((order or {}).get("package_slug")),
            "package_name": _normalize((order or {}).get("package_name")),
            "lane": _normalize((order or {}).get("lane")),
            "package_lane": _normalize((order or {}).get("package_lane")),
            "status": _normalize((order or {}).get("status")) if order else None,
        },
        "entitlement": {
            "package_code": _normalize((entitlement or {}).get("package_code")) if entitlement else None,
            "package_lane": _normalize((entitlement or {}).get("package_lane")) if entitlement else None,
        },
    }
    proposed = {
        "project": project_after,
        "order": order_after,
        "entitlement": entitlement_after,
    }
    return {
        "project_id": _normalize(project.get("_id")),
        "order_id": _normalize((order or {}).get("_id")) or None,
        "before": before,
        "proposed_after": proposed,
        "changes": _build_package_change_summary(before=before, proposed=proposed),
        "validation": {
            "project_exists": True,
            "known_package": True,
            "order_linked": bool(order),
            "target_lane": target_lane,
            "target_order_status": requested_order_status,
        },
    }


def super_admin_apply_package_change(
    *,
    project_id: str,
    package_code: str,
    project_lane: str = "",
    order_status: str = "",
    actor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    preview = super_admin_preview_package_change(
        project_id=project_id,
        package_code=package_code,
        project_lane=project_lane,
        order_status=order_status,
    )
    db = _db()
    resolved_project_id = _normalize(preview.get("project_id"))
    if not resolved_project_id:
        raise ValueError("Project id is invalid.")
    project_oid = _to_object_id(resolved_project_id)
    if project_oid is None:
        raise ValueError("Project id is invalid.")

    project_after = dict((preview.get("proposed_after") or {}).get("project") or {})
    project_after["updated_at"] = _now()
    db["projects"].update_one({"_id": project_oid}, {"$set": project_after})

    order_id = _normalize(preview.get("order_id"))
    before_order_package = _normalize(((preview.get("before") or {}).get("order") or {}).get("package_code"))
    before_project_package = _normalize(((preview.get("before") or {}).get("project") or {}).get("package_code"))
    if order_id:
        order_doc = _order_by_id(order_id)
        if order_doc is not None:
            order_updates = dict((preview.get("proposed_after") or {}).get("order") or {})
            order_updates = {key: value for key, value in order_updates.items() if value is not None}
            db["orders"].update_one({"_id": order_doc.get("_id")}, {"$set": order_updates})

    repaired = repair_record(project_id=resolved_project_id, order_id=order_id)
    after_snapshot = {
        "project": (repaired.get("project") or {}),
        "order": (repaired.get("order") or {}),
        "entitlement": {
            "package_code": _normalize(((repaired.get("entitlement") or {}).get("package_code"))),
            "package_lane": _normalize(((repaired.get("entitlement") or {}).get("package_lane"))),
        },
    }
    _write_admin_action_audit(
        actor=actor,
        action="super_admin.package_change",
        target_type="project",
        target_id=resolved_project_id,
        before=preview.get("before") or {},
        after=after_snapshot,
        context={"surface": "admin_control_center.super_admin", "order_id": order_id or None},
        details={"changes": preview.get("changes") or []},
    )
    _record_package_transition_event(
        order_id=order_id,
        project_id=resolved_project_id,
        customer_email=_normalize((after_snapshot.get("project") or {}).get("owner_email")),
        customer_user_id=_normalize((after_snapshot.get("project") or {}).get("owner_user_id")),
        before_package_code=before_order_package or before_project_package,
        after_package_code=_normalize((after_snapshot.get("project") or {}).get("package_code")),
        source="admin_control.super_admin_package_change",
    )
    return {
        "project_id": resolved_project_id,
        "order_id": order_id or None,
        "before": preview.get("before") or {},
        "after": after_snapshot,
        "changes": preview.get("changes") or [],
        "repair_result": repaired,
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
    order_ref = order or {}
    order_package_code = normalize_package_code(_normalize(order_ref.get("package_code") or order_ref.get("package_slug")))
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


def project_workspace_snapshot(
    project_id: str,
    *,
    current_user: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
        for item in cursor:
            _record_order_finance_events(item, source="project_workspace_snapshot")
            serialized = _serialize_order(item)
            if serialized:
                related_orders.append(serialized)

    finance_events = _collect_finance_events(
        project_id=project_id_str,
        order_id=_normalize((order or {}).get("_id")),
        owner_email=_normalize_email(project.get("owner_email")),
    )

    payload = {
        "project": _serialize_project(project),
        "order": _serialize_order(order),
        "package": package_fields,
        "warnings": package_fields.get("warnings") or [],
        "entitlement": entitlement,
        "readiness": readiness,
        "related_orders": related_orders,
        "finance_history": finance_events,
    }
    finance_profile = _finance_admin_profile(current_user)
    if finance_profile is None:
        return payload
    filtered_readiness = payload.get("readiness") or {}
    payload["readiness"] = {
        "package_synced": bool(filtered_readiness.get("package_synced")),
        "lane_assigned": bool(filtered_readiness.get("lane_assigned")),
        "order_linked": bool(filtered_readiness.get("order_linked")),
        "entitlement_exists": bool(filtered_readiness.get("entitlement_exists")),
        "summary": _normalize(filtered_readiness.get("summary")) or "Finance scope snapshot",
    }
    return payload


def _marketing_metric(value: Any, *, live: bool, status_note: str | None = None) -> dict[str, Any]:
    return {
        "value": value if live else None,
        "live": bool(live),
        "status": "live" if live else "unavailable",
        "status_note": status_note if not live else None,
    }


def _collection_exists(db: Any, name: str) -> bool:
    if hasattr(db, "list_collection_names"):
        try:
            return name in set(db.list_collection_names())
        except Exception:
            return False
    return True


def _analytics_event_stream(db: Any) -> tuple[list[dict[str, Any]], bool]:
    if not _collection_exists(db, "analytics_events"):
        return [], False
    events = list(db["analytics_events"].find({}).sort("created_at", -1).limit(5000))
    return events, True


def _marketing_sections_payload(
    *,
    db: Any,
    paid_orders_count: int,
    lane_sales: dict[str, int],
    upgrades_count: int,
) -> dict[str, Any]:
    analytics_events, analytics_live = _analytics_event_stream(db)

    visitors = 0
    sessions = 0
    cta_clicks = 0
    signup_starts = 0
    signup_completions = 0
    intake_starts = 0
    intake_completions = 0
    checkout_starts = 0
    event_purchases = 0
    landing_page_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    campaign_visit_counts: dict[str, int] = {}
    campaign_signup_counts: dict[str, int] = {}
    campaign_purchase_event_counts: dict[str, int] = {}
    homepage_views = 0
    hero_cta_clicks = 0
    pricing_engagement = 0
    testimonial_engagement = 0
    dropoff_counts: dict[str, int] = {}

    source_buckets = {"organic": 0, "direct": 0, "referral": 0, "paid": 0}
    has_source_breakdown = False

    for event in analytics_events:
        event_type = _normalize(event.get("event_type") or event.get("action")).lower()
        page_path = _normalize(event.get("page_path") or event.get("path")).lower()
        source = _normalize(event.get("source") or event.get("utm_source") or event.get("traffic_source")).lower()
        campaign = _normalize(event.get("campaign") or event.get("utm_campaign")).lower()
        cta_location = _normalize(event.get("cta_location") or event.get("cta_slot")).lower()
        section = _normalize(event.get("section") or event.get("module")).lower()
        dropoff_stage = _normalize(event.get("dropoff_stage") or event.get("funnel_stage")).lower()
        event_id = _normalize(event.get("event_id") or event.get("_id"))

        if event_type in {"page_view", "landing_page_view"}:
            if page_path:
                landing_page_counts[page_path] = landing_page_counts.get(page_path, 0) + 1
            if page_path in {"", "/", "/index", "/index.html", "/home", "/homepage"}:
                homepage_views += 1

        if event_type in {"visitor", "visitor_seen", "visit", "page_view"}:
            visitors += 1
        if event_type in {"session_start", "session"}:
            sessions += 1
        if event_type in {"cta_click", "hero_cta_click"}:
            cta_clicks += 1
            if cta_location in {"hero", "home_hero"}:
                hero_cta_clicks += 1
        if event_type in {"signup_start", "sign_up_start"}:
            signup_starts += 1
        if event_type in {"signup_complete", "sign_up_complete", "signup_completed"}:
            signup_completions += 1
        if event_type in {"intake_start"}:
            intake_starts += 1
        if event_type in {"intake_complete", "intake_completed"}:
            intake_completions += 1
        if event_type in {"checkout_start"}:
            checkout_starts += 1
        if event_type in {"purchase_complete", "purchase_completed"}:
            event_purchases += 1
            if campaign:
                campaign_purchase_event_counts[campaign] = campaign_purchase_event_counts.get(campaign, 0) + 1

        if event_type in {"section_view", "pricing_view"} and section in {"pricing", "packages", "package_pricing"}:
            pricing_engagement += 1
        if event_type in {"section_view", "testimonial_view", "testimonial_click"} and section in {"testimonials", "testimonial"}:
            testimonial_engagement += 1

        if event_type in {"page_dropoff", "dropoff", "funnel_dropoff"}:
            key = dropoff_stage or page_path or "unknown"
            dropoff_counts[key] = dropoff_counts.get(key, 0) + 1

        if source:
            source_counts[source] = source_counts.get(source, 0) + 1
            if source in source_buckets:
                source_buckets[source] += 1
                has_source_breakdown = True
            elif source in {"google", "bing", "search"}:
                source_buckets["organic"] += 1
                has_source_breakdown = True
            elif source in {"facebook_ads", "google_ads", "paid_social", "paid_search", "ads"}:
                source_buckets["paid"] += 1
                has_source_breakdown = True
            elif source in {"referral", "partner", "affiliate"}:
                source_buckets["referral"] += 1
                has_source_breakdown = True
            elif source in {"direct"}:
                source_buckets["direct"] += 1
                has_source_breakdown = True

        if campaign and event_type in {"visit", "page_view", "landing_page_view", "campaign_visit"}:
            campaign_visit_counts[campaign] = campaign_visit_counts.get(campaign, 0) + 1
        if campaign and event_type in {"signup_complete", "sign_up_complete", "signup_completed"}:
            campaign_signup_counts[campaign] = campaign_signup_counts.get(campaign, 0) + 1

        if not campaign and event_type in {"campaign_visit", "campaign_click"}:
            synthetic_campaign = f"campaign:{event_id or 'unknown'}"
            campaign_visit_counts[synthetic_campaign] = campaign_visit_counts.get(synthetic_campaign, 0) + 1

    lane_interest = {"portrait": 0, "household": 0, "network": 0, "organization": 0}
    for project in db["projects"].find({}, {"project_lane": 1, "lane": 1, "package_code": 1, "package_slug": 1}).limit(5000):
        lane_value = _normalize(project.get("project_lane") or project.get("lane")).lower()
        if lane_value not in lane_interest:
            lane_value = _package_lane_for_code(
                _normalize(project.get("package_code") or project.get("package_slug"))
            )
        if lane_value in lane_interest:
            lane_interest[lane_value] += 1

    total_lane_interest = sum(lane_interest.values())
    total_lane_conversions = int(sum(lane_sales.values()))
    package_conversion_rate = (
        round((float(total_lane_conversions) / float(total_lane_interest)) * 100.0, 2)
        if total_lane_interest > 0
        else 0.0
    )

    campaign_order_purchases: dict[str, int] = {}
    campaign_source_purchases: dict[str, int] = {}
    promo_referral_use = 0
    for order in db["orders"].find({}).sort("created_at", -1).limit(5000):
        if not _is_paid_package_order(order):
            continue
        campaign_value = _normalize(
            order.get("campaign") or order.get("utm_campaign") or order.get("campaign_code")
        ).lower()
        source_value = _normalize(
            order.get("source") or order.get("utm_source") or order.get("traffic_source")
        ).lower()
        promo_code = _normalize(order.get("promo_code") or order.get("promotion_code"))
        referral_code = _normalize(order.get("referral_code"))
        if campaign_value:
            campaign_order_purchases[campaign_value] = campaign_order_purchases.get(campaign_value, 0) + 1
        if campaign_value or source_value:
            key = f"{campaign_value or 'unknown_campaign'}::{source_value or 'unknown_source'}"
            campaign_source_purchases[key] = campaign_source_purchases.get(key, 0) + 1
        if promo_code or referral_code:
            promo_referral_use += 1

    campaign_keys = sorted(
        set(campaign_visit_counts.keys())
        | set(campaign_signup_counts.keys())
        | set(campaign_purchase_event_counts.keys())
        | set(campaign_order_purchases.keys())
    )
    campaign_conversion_rows: list[dict[str, Any]] = []
    for key in campaign_keys:
        visits = int(campaign_visit_counts.get(key, 0))
        signups = int(campaign_signup_counts.get(key, 0))
        purchases = int(campaign_order_purchases.get(key, 0) or campaign_purchase_event_counts.get(key, 0))
        campaign_conversion_rows.append(
            {
                "campaign": key,
                "visits": visits,
                "signups": signups,
                "purchases": purchases,
                "conversion_rate": round((float(purchases) / float(visits)) * 100.0, 2) if visits > 0 else 0.0,
            }
        )

    campaign_source_rows: list[dict[str, Any]] = []
    for key, purchases in sorted(campaign_source_purchases.items()):
        campaign, source = key.split("::", 1)
        campaign_source_rows.append({"campaign": campaign, "source": source, "purchases": purchases})

    top_landing_pages = [
        {"page": page, "visits": count}
        for page, count in sorted(landing_page_counts.items(), key=lambda item: item[1], reverse=True)[:10]
    ]
    top_sources = [
        {"source": source, "visits": count}
        for source, count in sorted(source_counts.items(), key=lambda item: item[1], reverse=True)[:10]
    ]
    top_campaign_traffic = [
        {"campaign": campaign, "visits": count}
        for campaign, count in sorted(campaign_visit_counts.items(), key=lambda item: item[1], reverse=True)[:10]
    ]
    dropoff_points = [
        {"point": point, "count": count}
        for point, count in sorted(dropoff_counts.items(), key=lambda item: item[1], reverse=True)[:10]
    ]

    reports = {
        "funnel_export": {
            "available": True,
            "status": "live",
            "status_note": None,
        },
        "campaign_export": {
            "available": bool(campaign_conversion_rows),
            "status": "live" if campaign_conversion_rows else "unavailable",
            "status_note": None if campaign_conversion_rows else "Campaign-tagged events are not yet captured in live analytics.",
        },
        "source_attribution_export": {
            "available": bool(top_sources),
            "status": "live" if top_sources else "unavailable",
            "status_note": None if top_sources else "Source attribution fields are not yet present in live analytics events.",
        },
        "page_performance_export": {
            "available": bool(top_landing_pages),
            "status": "live" if top_landing_pages else "unavailable",
            "status_note": None if top_landing_pages else "Page performance events are not yet captured in a live analytics stream.",
        },
        "package_interest_export": {
            "available": True,
            "status": "live",
            "status_note": None,
        },
    }

    return {
        "traffic_awareness": {
            "visitors": _marketing_metric(visitors, live=analytics_live, status_note="Visitor tracking is not yet live."),
            "sessions": _marketing_metric(sessions, live=analytics_live, status_note="Session tracking is not yet live."),
            "top_landing_pages": _marketing_metric(
                top_landing_pages,
                live=analytics_live,
                status_note="Landing-page telemetry is not yet live.",
            ),
            "traffic_sources": _marketing_metric(
                top_sources,
                live=analytics_live,
                status_note="Traffic-source attribution is not yet live.",
            ),
            "campaign_traffic": _marketing_metric(
                top_campaign_traffic,
                live=analytics_live,
                status_note="Campaign traffic telemetry is not yet live.",
            ),
            "channel_breakdown": _marketing_metric(
                source_buckets,
                live=analytics_live and has_source_breakdown,
                status_note="Organic/direct/referral/paid channel breakdown is not yet live.",
            ),
        },
        "funnel_conversion": {
            "cta_clicks": _marketing_metric(cta_clicks, live=analytics_live, status_note="CTA click telemetry is not yet live."),
            "signup_starts": _marketing_metric(
                signup_starts,
                live=analytics_live,
                status_note="Signup start telemetry is not yet live.",
            ),
            "signup_completions": _marketing_metric(
                signup_completions,
                live=analytics_live,
                status_note="Signup completion telemetry is not yet live.",
            ),
            "intake_starts": _marketing_metric(
                intake_starts,
                live=analytics_live,
                status_note="Intake start telemetry is not yet live.",
            ),
            "intake_completions": _marketing_metric(
                intake_completions,
                live=analytics_live,
                status_note="Intake completion telemetry is not yet live.",
            ),
            "checkout_starts": _marketing_metric(
                checkout_starts,
                live=analytics_live,
                status_note="Checkout start telemetry is not yet live.",
            ),
            "purchases_completed": _marketing_metric(
                paid_orders_count,
                live=True,
            ),
            "upgrade_conversions": _marketing_metric(
                upgrades_count,
                live=True,
            ),
        },
        "package_demand": {
            "portrait_lane_interest_conversion": _marketing_metric(
                {"interest": lane_interest["portrait"], "conversions": lane_sales["portrait"]},
                live=True,
            ),
            "household_lane_interest_conversion": _marketing_metric(
                {"interest": lane_interest["household"], "conversions": lane_sales["household"]},
                live=True,
            ),
            "network_lane_interest_conversion": _marketing_metric(
                {"interest": lane_interest["network"], "conversions": lane_sales["network"]},
                live=True,
            ),
            "organization_lane_interest_conversion": _marketing_metric(
                {"interest": lane_interest["organization"], "conversions": lane_sales["organization"]},
                live=True,
            ),
            "package_page_views": _marketing_metric(
                int(sum(count for page, count in landing_page_counts.items() if "package" in page)),
                live=analytics_live,
                status_note="Package page-view telemetry is not yet live.",
            ),
            "package_conversion_rate": _marketing_metric(
                package_conversion_rate,
                live=True,
            ),
        },
        "campaign_performance": {
            "campaign_visits": _marketing_metric(
                int(sum(campaign_visit_counts.values())),
                live=analytics_live,
                status_note="Campaign visit telemetry is not yet live.",
            ),
            "campaign_signups": _marketing_metric(
                int(sum(campaign_signup_counts.values())),
                live=analytics_live,
                status_note="Campaign signup telemetry is not yet live.",
            ),
            "campaign_purchases": _marketing_metric(
                int(sum(campaign_order_purchases.values())),
                live=bool(campaign_order_purchases),
                status_note="Campaign purchase attribution is not yet live in paid-order records.",
            ),
            "conversion_by_campaign_source": _marketing_metric(
                campaign_conversion_rows or campaign_source_rows,
                live=bool(campaign_conversion_rows or campaign_source_rows),
                status_note="Campaign/source conversion attribution is not yet live.",
            ),
            "promo_referral_use": _marketing_metric(
                promo_referral_use,
                live=True,
            ),
        },
        "content_performance": {
            "homepage_performance": _marketing_metric(
                {"views": homepage_views},
                live=analytics_live,
                status_note="Homepage performance telemetry is not yet live.",
            ),
            "hero_cta_performance": _marketing_metric(
                {"cta_clicks": hero_cta_clicks},
                live=analytics_live,
                status_note="Hero CTA telemetry is not yet live.",
            ),
            "pricing_package_engagement": _marketing_metric(
                pricing_engagement,
                live=analytics_live,
                status_note="Pricing/package section engagement telemetry is not yet live.",
            ),
            "testimonial_engagement": _marketing_metric(
                testimonial_engagement,
                live=analytics_live,
                status_note="Testimonial engagement telemetry is not yet live.",
            ),
            "page_dropoff_points": _marketing_metric(
                dropoff_points,
                live=analytics_live and bool(dropoff_points),
                status_note="Page dropoff telemetry is not yet live.",
            ),
        },
        "marketing_reports": reports,
    }


def admin_console_overview(*, limit: int = 20) -> dict[str, Any]:
    db = _db()
    users_total = int(db["users"].count_documents({}))
    active_projects = int(db["projects"].count_documents({"status": {"$ne": "archived"}}))
    paid_orders = int(db["orders"].count_documents({"status": {"$in": list(PAID_ORDER_STATUSES)}}))
    now = _now()
    month_start = datetime(now.year, now.month, 1, tzinfo=UTC)

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

    gross_revenue = 0.0
    successful_payments = 0
    failed_payments = 0
    unpaid_balances = 0
    collected_today = 0.0
    collected_month = 0.0
    refunds_this_month = 0.0
    unlinked_payments = 0
    lane_sales = {"portrait": 0, "household": 0, "network": 0, "organization": 0}
    seven_days_ago = now - timedelta(days=7)
    three_days_ago = now - timedelta(days=3)
    fourteen_days_ago = now - timedelta(days=14)

    new_projects_accounts = 0
    intake_started = 0
    intake_completed = 0
    incomplete_intake = 0
    stuck_intake = 0
    missing_consent_or_steps = 0

    uploads_awaiting_review = 0
    verification_pending = 0
    rejected_or_incomplete_uploads = 0
    missing_records = 0
    aging_verification_queue = 0

    pending_invites = 0
    expired_invites = 0
    failed_invite_deliveries = 0
    access_mismatches = 0
    member_role_access_issues = 0

    build_stage_in_progress = 0
    certificate_readiness = 0
    blocked_projects = 0
    waiting_on_customer = 0
    ready_for_next_step = 0

    stuck_linkage = 0
    stuck_entitlements = 0
    unresolved_admin_cases = 0
    manual_review_queue = 0
    executive_escalations = 0

    finance_statuses = set(PAID_ORDER_STATUSES) | {
        "failed",
        "payment_failed",
        "declined",
        "pending",
        "open",
        "unpaid",
        "past_due",
        "incomplete",
        "refunded",
        "refund",
    }
    for order in db["orders"].find({"status": {"$in": list(finance_statuses)}}).sort("created_at", -1).limit(5000):
        status_value = _normalize(order.get("status")).lower()
        amount = _order_amount_value(order)
        order_dt = _coerce_datetime(order.get("created_at") or order.get("updated_at"))
        _record_order_finance_events(order, source="admin_console_overview")

        if _is_paid_package_order(order):
            successful_payments += 1
            gross_revenue += amount
            if order_dt and order_dt.date() == now.date():
                collected_today += amount
            if order_dt and order_dt >= month_start:
                collected_month += amount
            if not _normalize(order.get("project_id")):
                unlinked_payments += 1

            lane_value = _normalize(order.get("lane") or order.get("package_lane")).lower()
            if lane_value not in lane_sales:
                lane_value = _normalize(
                    canonicalize_package_identifier(
                        order.get("package_code") or order.get("package_slug")
                    ).get("package_lane")
                ).lower()
            if lane_value in lane_sales:
                lane_sales[lane_value] += 1
        elif status_value in {"failed", "payment_failed", "declined"}:
            failed_payments += 1
        elif status_value in {"pending", "open", "unpaid", "past_due", "incomplete"}:
            unpaid_balances += 1

        refund_value = _coerce_amount(order.get("refund_amount") or order.get("refunded_amount"))
        if refund_value > 0 and order_dt and order_dt >= month_start:
            refunds_this_month += refund_value
        elif status_value in {"refunded", "refund"} and order_dt and order_dt >= month_start:
            refunds_this_month += amount

    for project in db["projects"].find({}).sort("updated_at", -1).limit(500):
        project_id = _normalize(project.get("_id"))
        readiness = run_readiness_check(project_id=project_id)
        created_at = _coerce_datetime(project.get("created_at"))
        updated_at = _coerce_datetime(project.get("updated_at"))
        phase_value = _normalize(project.get("phase")).lower()
        intake_status = _normalize(project.get("intake_status")).lower()
        build_status = _normalize(project.get("status")).lower()
        upload_count = int(db["uploaded_files"].count_documents({"project_id": project_id}))
        if created_at and created_at >= seven_days_ago:
            new_projects_accounts += 1
        if phase_value.startswith("intake") or intake_status in {"started", "in_progress", "pending"}:
            intake_started += 1
        if readiness.get("intake_approved") or phase_value in INTAKE_APPROVED_PHASES:
            intake_completed += 1
        if phase_value.startswith("intake") and not readiness.get("intake_approved"):
            incomplete_intake += 1
            if updated_at and updated_at < three_days_ago:
                stuck_intake += 1
        if intake_status in {"missing_consent", "missing_steps", "blocked"}:
            missing_consent_or_steps += 1
        if upload_count <= 0 and not readiness.get("mint_already_completed"):
            missing_records += 1
            waiting_on_customer += 1
        if build_status in {"build_started", "in_production", "qa_review", "quality_review", "client_review"}:
            build_stage_in_progress += 1
        if readiness.get("mint_review_ready"):
            certificate_readiness += 1
            ready_for_next_step += 1
        if readiness.get("blocking_reasons"):
            blocked_projects += 1
            manual_review_queue += 1
            if updated_at and updated_at < fourteen_days_ago:
                executive_escalations += 1
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
            stuck_entitlements += 1
        if not readiness.get("lane_assigned"):
            priority_repairs["package_without_lane"].append(project_id)
        if readiness.get("mint_review_ready") and not readiness.get("mint_eligible"):
            priority_repairs["mint_eligible_blocked"].append(project_id)

    for order in db["orders"].find({"status": {"$in": list(PAID_ORDER_STATUSES)}}).sort("created_at", -1).limit(500):
        if _normalize(order.get("project_id")):
            continue
        stuck_linkage += 1
        priority_repairs["paid_order_without_project_link"].append(
            {
                "order_id": _normalize(order.get("_id")),
                "email": _normalize_email(order.get("email")) or None,
                "package_name": _normalize(order.get("package_name")) or None,
            }
        )

    uploads_awaiting_review = int(
        db["uploaded_files"].count_documents(
            {"status": {"$in": ["pending", "awaiting_review", "uploaded", "received"]}}
        )
    )
    rejected_or_incomplete_uploads = int(
        db["uploaded_files"].count_documents(
            {"status": {"$in": ["rejected", "incomplete", "needs_resubmission"]}}
        )
    )
    verification_pending = int(
        db["verification_records"].count_documents(
            {"status": {"$in": ["pending", "awaiting_review", "in_review"]}}
        )
    )
    for record in db["verification_records"].find(
        {"status": {"$in": ["pending", "awaiting_review", "in_review"]}}
    ).limit(5000):
        created_at = _coerce_datetime(record.get("created_at") or record.get("updated_at"))
        if created_at and created_at < three_days_ago:
            aging_verification_queue += 1

    for invite in db["household_invites"].find({}).limit(5000):
        status_value = _normalize(invite.get("status")).lower()
        if status_value == "pending":
            pending_invites += 1
        if status_value == "expired":
            expired_invites += 1
        if _normalize(invite.get("email_delivery_status")).lower() == "failed":
            failed_invite_deliveries += 1

    for member in db["project_members"].find({}).limit(5000):
        link_status = _normalize(member.get("link_status") or member.get("status")).lower()
        member_role = _normalize(member.get("member_role")).lower()
        if link_status and link_status not in {"active", "accepted"}:
            access_mismatches += 1
        if not member_role or member_role in {"unknown", "invalid"}:
            member_role_access_issues += 1

    unresolved_admin_cases = len(mismatches)
    new_accounts = int(db["users"].count_documents({"created_at": {"$gte": seven_days_ago}}))
    new_projects_accounts += new_accounts

    postmark_token_configured = bool(_normalize(settings.postmark_server_token))
    postmark_from_address_configured = bool(_normalize_email(settings.postmark_from_email))
    manual_override_log = int(
        db["audit_logs"].count_documents({"action": {"$regex": "manual|override", "$options": "i"}})
    )
    payroll_runs = list(
        db["payroll_runs"]
        .find({"period_end": {"$exists": True, "$ne": None}})
        .sort("period_end", -1)
        .limit(12)
    )
    payroll_current = payroll_runs[0] if payroll_runs else {}
    processed_payroll_history = len(
        [run for run in payroll_runs if _normalize(run.get("status")).lower() in {"processed", "completed"}]
    )
    pending_payroll_review = len(
        [run for run in payroll_runs if _normalize(run.get("status")).lower() in {"pending", "review"}]
    )
    finance_events = db["finance_events"]
    upgrades_count = int(finance_events.count_documents({"event_type": "package_upgrade"}))
    downgrades_count = int(finance_events.count_documents({"event_type": "package_downgrade"}))
    refund_event_count = int(finance_events.count_documents({"event_type": "refund_recorded"}))
    credit_event_count = int(finance_events.count_documents({"event_type": "credit_recorded"}))
    adjustment_event_count = int(finance_events.count_documents({"event_type": "billing_adjustment"}))
    recent_finance_events = [
        _serialize_finance_event(item)
        for item in finance_events.find({}).sort("occurred_at", -1).limit(20)
    ]
    net_revenue = gross_revenue - refunds_this_month

    marketing_sections = _marketing_sections_payload(
        db=db,
        paid_orders_count=paid_orders,
        lane_sales=lane_sales,
        upgrades_count=upgrades_count,
    )

    return {
        "summary": {
            "total_users": users_total,
            "total_active_projects": active_projects,
            "paid_orders": paid_orders,
            "missing_entitlements": len(missing_entitlements),
            "mint_ready_projects": mint_ready_count,
            "projects_with_data_mismatch": len(mismatches),
            "gross_revenue": round(gross_revenue, 2),
            "net_revenue": round(net_revenue, 2),
            "successful_payments": successful_payments,
            "failed_payments": failed_payments,
            "unpaid_balances": unpaid_balances,
            "collected_today": round(collected_today, 2),
            "collected_month": round(collected_month, 2),
            "refunds_this_month": round(refunds_this_month, 2),
            "unlinked_payments": unlinked_payments,
            "manual_override_log": manual_override_log,
        },
        "finance_sections": {
            "money_now": {
                "gross_revenue": round(gross_revenue, 2),
                "net_revenue": round(net_revenue, 2),
                "collected_today": round(collected_today, 2),
                "collected_month": round(collected_month, 2),
                "refunds_this_month": round(refunds_this_month, 2),
                "failed_payments": failed_payments,
                "unpaid_balances": unpaid_balances,
            },
            "subscriptions_maintenance": {
                "active_maintenance_plans": int(db["project_entitlements"].count_documents({"maintenance_status": {"$in": ["active", "started"]}})),
                "renewals_due": int(db["project_entitlements"].count_documents({"maintenance_status": {"$in": ["due", "renewal_due"]}})),
                "past_due_subscriptions": int(db["project_entitlements"].count_documents({"maintenance_status": {"$in": ["past_due", "overdue"]}})),
                "churned_subscriptions": int(db["project_entitlements"].count_documents({"maintenance_status": {"$in": ["canceled", "cancelled", "churned"]}})),
                "recovered_failed_subscriptions": int(db["audit_logs"].count_documents({"action": {"$regex": "subscription.*recover|recover.*subscription", "$options": "i"}})),
            },
            "package_revenue": {
                "portrait_lane_sales": lane_sales["portrait"],
                "household_lane_sales": lane_sales["household"],
                "network_lane_sales": lane_sales["network"],
                "organization_lane_sales": lane_sales["organization"],
                "upgrades": upgrades_count,
                "downgrades": downgrades_count,
            },
            "finance_integrity": {
                "unlinked_payments": unlinked_payments,
                "order_project_mismatch": len(priority_repairs["paid_order_without_project_link"]),
                "entitlement_mismatch": len(priority_repairs["project_without_entitlement"]),
                "refunded_but_still_active_access": int(
                    db["project_entitlements"].count_documents(
                        {"status": {"$in": ["active", "enabled"]}, "maintenance_status": {"$in": ["refunded", "canceled", "cancelled"]}}
                    )
                ),
                "duplicate_risk_records": int(db["users"].count_documents({"status": {"$in": ["duplicate", "conflict", "pending_merge"]}})),
                "manual_override_log": manual_override_log,
                "refund_event_count": refund_event_count,
                "credit_event_count": credit_event_count,
                "adjustment_event_count": adjustment_event_count,
            },
            "payroll": {
                "next_payroll_due": _serialize_datetime(payroll_current.get("next_due_at")),
                "payroll_total_this_period": round(_coerce_amount(payroll_current.get("total_amount")), 2),
                "processed_payroll_history": processed_payroll_history,
                "pending_payroll_review": pending_payroll_review,
                "snapshot_mode": "read_only",
                "write_pipeline_live": False,
                "workflow_actions_enabled": False,
                "status_note": "Payroll is currently a read-only snapshot; write workflows are not yet live.",
            },
            "reports_exports": {
                "export_generation_live": False,
                "status_note": "Finance export generation is not yet live.",
                "available_exports": [],
                "unavailable_exports": [
                    "monthly_finance_export",
                    "tax_export",
                    "refund_report",
                    "subscription_report",
                    "payroll_report",
                    "package_performance_report",
                ],
            },
            "finance_history": {
                "refund_records": refund_event_count,
                "credit_records": credit_event_count,
                "billing_adjustments": adjustment_event_count,
                "recent_events": recent_finance_events,
            },
        },
        "marketing_sections": marketing_sections,
        "operations_sections": {
            "intake_onboarding": {
                "new_projects_accounts": {"value": new_projects_accounts, "live": True, "status": "live"},
                "intake_started": {"value": intake_started, "live": True, "status": "live"},
                "intake_completed": {"value": intake_completed, "live": True, "status": "live"},
                "incomplete_intake": {"value": incomplete_intake, "live": True, "status": "live"},
                "stuck_intake": {"value": stuck_intake, "live": True, "status": "live"},
                "missing_consent_or_steps": {"value": missing_consent_or_steps, "live": True, "status": "live"},
            },
            "verification_upload_review": {
                "uploads_awaiting_review": {"value": uploads_awaiting_review, "live": True, "status": "live"},
                "verification_pending": {"value": verification_pending, "live": True, "status": "live"},
                "rejected_or_incomplete_uploads": {"value": rejected_or_incomplete_uploads, "live": True, "status": "live"},
                "missing_records": {"value": missing_records, "live": True, "status": "live"},
                "aging_verification_queue": {"value": aging_verification_queue, "live": True, "status": "live"},
            },
            "workspace_access_invites": {
                "pending_invites": {"value": pending_invites, "live": True, "status": "live"},
                "expired_invites": {"value": expired_invites, "live": True, "status": "live"},
                "failed_invite_deliveries": {"value": failed_invite_deliveries, "live": True, "status": "live"},
                "access_mismatches": {"value": access_mismatches, "live": True, "status": "live"},
                "member_role_access_issues": {"value": member_role_access_issues, "live": True, "status": "live"},
            },
            "build_fulfillment": {
                "project_readiness": {"value": {"ready_for_next_step": ready_for_next_step, "blocked": blocked_projects}, "live": True, "status": "live"},
                "lineage_family_build_stage": {"value": build_stage_in_progress, "live": True, "status": "live"},
                "certificate_readiness": {"value": certificate_readiness, "live": True, "status": "live"},
                "blocked_projects": {"value": blocked_projects, "live": True, "status": "live"},
                "waiting_on_customer": {"value": waiting_on_customer, "live": True, "status": "live"},
                "ready_for_next_step": {"value": ready_for_next_step, "live": True, "status": "live"},
            },
            "exceptions_escalations": {
                "stuck_linkage": {"value": stuck_linkage, "live": True, "status": "live"},
                "stuck_entitlements_impacting_ops": {"value": stuck_entitlements, "live": True, "status": "live"},
                "unresolved_admin_cases": {"value": unresolved_admin_cases, "live": True, "status": "live"},
                "manual_review_queue": {"value": manual_review_queue, "live": True, "status": "live"},
                "projects_needing_executive_escalation": {"value": executive_escalations, "live": True, "status": "live"},
            },
            "ops_reports": {
                "queue_totals": {"value": intake_started + verification_pending + pending_invites + build_stage_in_progress + manual_review_queue, "live": True, "status": "live"},
                "aging_by_queue": {"value": {"intake": stuck_intake, "verification": aging_verification_queue, "escalation": executive_escalations}, "live": True, "status": "live"},
                "completion_throughput": {"value": {"intake_completed": intake_completed, "ready_for_next_step": ready_for_next_step}, "live": True, "status": "live"},
                "sla_turnaround_indicators": {"value": None, "live": False, "status": "unavailable", "status_note": "SLA turnaround metrics are not yet live."},
                "export_ops_report": {"value": "available", "live": True, "status": "live"},
            },
        },
        "priority_repairs": {
            "paid_order_without_project_link": priority_repairs["paid_order_without_project_link"][:limit],
            "project_without_entitlement": priority_repairs["project_without_entitlement"][:limit],
            "package_without_lane": priority_repairs["package_without_lane"][:limit],
            "mint_eligible_blocked": priority_repairs["mint_eligible_blocked"][:limit],
        },
        "mismatches": mismatches[:limit],
        "system_health": {
            "postmark": {
                "token_configured": postmark_token_configured,
                "from_address_configured": postmark_from_address_configured,
            }
        },
    }


def export_operations_report() -> dict[str, Any]:
    payload = admin_console_overview(limit=200)
    return {
        "generated_at": _serialize_datetime(_now()),
        "report_type": "operations_control_center",
        "format": "json",
        "sections": payload.get("operations_sections") or {},
        "status": "live",
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

    project_package = _normalize(project.get("package_code") or project.get("package_slug"))
    order_package = _normalize(order.get("package_code") or order.get("package_slug"))
    package_code = normalize_package_code(project_package or order_package)
    package_name = _normalize(project.get("package_name") or order.get("package_name"))
    lane = _project_lane_value(project) or _package_lane_for_code(package_code)
    db["orders"].update_one(
        {"_id": order["_id"]},
        {
            "$set": {
                "project_id": project_oid,
                "package_code": package_code or _normalize(order.get("package_code")),
                "package_slug": package_code or _normalize(order.get("package_slug")),
                "package_name": package_name or _normalize(order.get("package_name")),
                "lane": lane,
                "package_lane": lane,
            }
        },
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


def _case_queue_match(
    queue: str,
    alerts: list[str],
    *,
    project: dict[str, Any] | None = None,
    readiness: dict[str, Any] | None = None,
) -> bool:
    normalized = _normalize(queue).lower()
    if normalized in {"", "all", "overview", "customer_cases", "projects", "system_health"}:
        return True
    if normalized == "intake_onboarding":
        phase = _normalize((project or {}).get("phase")).lower()
        status_value = _normalize((project or {}).get("status")).lower()
        if phase.startswith("intake"):
            return True
        return status_value in {"new", "pending", "intake_started", "intake_in_progress"} or "upload_review_pending" in alerts
    if normalized == "verification_upload_review":
        return "upload_review_pending" in alerts or bool(readiness and not readiness.get("mint_already_completed"))
    if normalized == "workspace_access_invites":
        return any(
            alert in {"duplicate_admin_user_identity", "paid_order_not_linked"}
            for alert in alerts
        )
    if normalized == "build_fulfillment":
        return bool(project)
    if normalized == "exceptions_escalations":
        return any(
            alert
            in {
                "missing_entitlement",
                "lane_unknown",
                "paid_order_not_linked",
                "mint_blocked",
                "duplicate_admin_user_identity",
            }
            for alert in alerts
        )
    if normalized == "ops_reports":
        return False
    if normalized == "money_now":
        return True
    if normalized == "subscriptions_maintenance":
        return "maintenance_not_started" in alerts
    if normalized == "package_revenue":
        return True
    if normalized == "finance_integrity":
        return any(
            alert in {
                "paid_order_not_linked",
                "missing_entitlement",
                "package_mismatch_order",
                "package_mismatch_entitlement",
                "lane_mismatch_entitlement",
                "duplicate_admin_user_identity",
            }
            for alert in alerts
        )
    if normalized == "payroll":
        return False
    if normalized == "reports_exports":
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
        normalize_role_code(_normalize(user.get("role"))).lower(),
        normalize_role_code(_normalize(user.get("access_tier"))).lower(),
        normalize_role_code(_normalize(user.get("department_role"))).lower(),
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
    return resolve_primary_role_code(
        (
            _normalize(user.get("role")),
            _normalize(user.get("access_tier")),
            _normalize(user.get("department_role")),
        ),
        default="user",
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


def _finance_admin_profile(current_user: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(current_user, dict):
        return None
    profile = admin_control_access_profile(current_user)
    if _normalize(profile.get("role_key")).lower() != "finance_admin":
        return None
    return profile


def _filter_guidance_for_finance(guidance_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    allowed_actions = set(FINANCE_ACTION_ALLOWLIST)
    filtered: list[dict[str, Any]] = []
    for item in guidance_items:
        recommended = _normalize(item.get("recommended_action")).lower()
        code = _normalize(item.get("code")).lower()
        if recommended and recommended not in allowed_actions:
            continue
        if code in FINANCE_WORKSPACE_ALERT_EXCLUDE:
            continue
        filtered.append(item)
    return filtered


def _filter_case_item_for_access(item: dict[str, Any], current_user: dict[str, Any] | None) -> dict[str, Any]:
    finance_profile = _finance_admin_profile(current_user)
    if finance_profile is None:
        return item
    allowed_actions = set(finance_profile.get("allowed_actions") or [])
    alerts = [alert for alert in (item.get("alerts") or []) if _normalize(alert).lower() not in FINANCE_WORKSPACE_ALERT_EXCLUDE]
    guidance = _filter_guidance_for_finance(item.get("operator_guidance") or [])
    item["alerts"] = alerts
    item["operator_guidance"] = guidance
    item["quick_actions"] = [action for action in (item.get("quick_actions") or []) if _normalize(action).lower() in allowed_actions]
    item["mint_blocking_reasons"] = []
    return item


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


def _user_by_id(user_id: str) -> dict[str, Any] | None:
    normalized_user_id = _normalize(user_id)
    if not normalized_user_id:
        return None
    db = _db()
    user_oid = _to_object_id(normalized_user_id)
    if user_oid is not None:
        user = db["users"].find_one({"_id": user_oid})
        if user is not None:
            return user
    return db["users"].find_one(
        {
            "$or": [
                {"_id": normalized_user_id},
                {"id": normalized_user_id},
                {"user_id": normalized_user_id},
            ]
        }
    )


def _safe_user_search_haystack(user: dict[str, Any]) -> str:
    return " ".join(
        [
            _normalize(user.get("_id")),
            _normalize(user.get("id")),
            _normalize(user.get("user_id")),
            _normalize(user.get("email")),
            _normalize(user.get("full_name")),
            _normalize(user.get("first_name")),
            _normalize(user.get("last_name")),
            _normalize(user.get("role")),
            _normalize(user.get("access_tier")),
            _normalize(user.get("department_role")),
            _normalize(user.get("status")),
            _normalize(user.get("phone_number") or user.get("phone")),
            _normalize(user.get("birthday") or user.get("birth_date") or user.get("date_of_birth") or user.get("dob")),
            _normalize(user.get("mailing_address") or user.get("address")),
        ]
    ).lower()


def _serialize_super_admin_user_summary(user: dict[str, Any]) -> dict[str, Any]:
    related_projects = _related_projects_for_user(user)
    related_orders = _related_orders_for_user(user)
    project_ids = [
        _normalize_object_id(project.get("id"))
        for project in related_projects
        if _normalize_object_id(project.get("id"))
    ]
    related_entitlements = _related_entitlements_for_user(user, project_ids)
    family_ids = sorted(
        {
            _normalize(project.get("family_id"))
            for project in related_projects
            if _normalize(project.get("family_id"))
        }
    )
    package_values = sorted(
        {
            _normalize(entitlement.get("package_code"))
            for entitlement in related_entitlements
            if _normalize(entitlement.get("package_code"))
        }
        | {
            _normalize(order.get("package_code"))
            for order in related_orders
            if _normalize(order.get("package_code"))
        }
        | {
            _normalize(project.get("package_code"))
            for project in related_projects
            if _normalize(project.get("package_code"))
        }
    )
    return {
        "user_id": _normalize_object_id(user.get("_id")) or _normalize(user.get("id")) or _normalize(user.get("user_id")),
        "email": _normalize_email(user.get("email")) or None,
        "full_name": _user_display_name(user),
        "role": _user_role_value(user),
        "status": _normalize(user.get("status")) or "active",
        "phone_number": _normalize(user.get("phone_number") or user.get("phone")) or None,
        "birthday": _serialize_datetime(
            user.get("birthday") or user.get("birth_date") or user.get("date_of_birth") or user.get("dob")
        ),
        "mailing_address": _normalize(user.get("mailing_address") or user.get("address")) or None,
        "project_count": len(related_projects),
        "order_count": len(related_orders),
        "entitlement_count": len(related_entitlements),
        "family_ids": family_ids,
        "packages": package_values,
        "is_internal_admin": _is_internal_user_document(user),
        "last_login_at": _serialize_datetime(user.get("last_login_at")),
        "updated_at": _serialize_datetime(user.get("updated_at") or user.get("created_at")),
    }


def super_admin_list_users(*, search: str = "", limit: int = 100) -> dict[str, Any]:
    db = _db()
    safe_limit = max(1, min(limit, 500))
    normalized_search = _normalize(search).lower()
    items: list[dict[str, Any]] = []
    for user in db["users"].find({}).sort("updated_at", -1).limit(max(500, safe_limit * 8)):
        summary = _serialize_super_admin_user_summary(user)
        if not summary.get("user_id"):
            continue
        if normalized_search:
            related_terms = " ".join(
                [
                    " ".join(summary.get("packages") or []),
                    " ".join(summary.get("family_ids") or []),
                ]
            ).lower()
            if normalized_search not in (_safe_user_search_haystack(user) + " " + related_terms):
                continue
        items.append(summary)
        if len(items) >= safe_limit:
            break
    return {"items": items, "total": len(items)}


def _validate_super_admin_email(email: str, *, user_id: str) -> str:
    normalized = _normalize_email(email)
    if not normalized or "@" not in normalized:
        raise ValueError("A valid email address is required.")
    db = _db()
    existing = db["users"].find_one({"email": normalized})
    existing_id = _normalize_object_id((existing or {}).get("_id"))
    if existing is not None and existing_id and existing_id != _normalize_object_id(user_id):
        raise ValueError("Email address is already in use by another account.")
    return normalized


def _validated_role_value(role_value: str) -> str:
    normalized_role = normalize_role_code(role_value)
    if not normalized_role:
        raise ValueError("Role is required.")
    return normalized_role


def super_admin_update_user(
    *,
    user_id: str,
    payload: dict[str, Any],
    actor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    user = _user_by_id(user_id)
    if user is None:
        raise ValueError("User not found.")
    db = _db()
    current_user_id = _normalize_object_id(user.get("_id")) or _normalize(user_id)
    updates: dict[str, Any] = {"updated_at": _now()}

    if "email" in payload:
        updates["email"] = _validate_super_admin_email(_normalize(payload.get("email")), user_id=current_user_id)
    if "full_name" in payload:
        full_name = _normalize(payload.get("full_name"))
        if not full_name:
            raise ValueError("full_name is required.")
        updates["full_name"] = full_name
    if "phone_number" in payload:
        updates["phone_number"] = _normalize(payload.get("phone_number")) or None
    if "birthday" in payload:
        updates["birthday"] = _normalize(payload.get("birthday")) or None
    if "mailing_address" in payload:
        updates["mailing_address"] = _normalize(payload.get("mailing_address")) or None
    if "status" in payload:
        status_value = _normalize(payload.get("status")).lower()
        if status_value not in SUPER_ADMIN_USER_STATUS_VALUES:
            raise ValueError("Invalid account status.")
        updates["status"] = status_value
    if "role" in payload:
        updates["role"] = _validated_role_value(_normalize(payload.get("role")))
    if "access_tier" in payload:
        updates["access_tier"] = normalize_role_code(_normalize(payload.get("access_tier"))) or None
    if "department_role" in payload:
        updates["department_role"] = normalize_role_code(_normalize(payload.get("department_role"))) or None

    if len(updates) == 1:
        raise ValueError("No valid updates were provided.")

    before = {
        "email": _normalize_email(user.get("email")),
        "full_name": _user_display_name(user),
        "phone_number": _normalize(user.get("phone_number") or user.get("phone")) or None,
        "birthday": _serialize_datetime(
            user.get("birthday") or user.get("birth_date") or user.get("date_of_birth") or user.get("dob")
        ),
        "mailing_address": _normalize(user.get("mailing_address") or user.get("address")) or None,
        "status": _normalize(user.get("status")) or "active",
        "role": _user_role_value(user),
        "access_tier": _normalize(user.get("access_tier")) or None,
        "department_role": _normalize(user.get("department_role")) or None,
    }

    user_oid = _to_object_id(current_user_id)
    if user_oid is not None:
        db["users"].update_one({"_id": user_oid}, {"$set": updates})
    else:
        db["users"].update_one({"_id": current_user_id}, {"$set": updates})
    refreshed = _user_by_id(current_user_id) or {}
    after = {
        "email": _normalize_email(refreshed.get("email")),
        "full_name": _user_display_name(refreshed),
        "phone_number": _normalize(refreshed.get("phone_number") or refreshed.get("phone")) or None,
        "birthday": _serialize_datetime(
            refreshed.get("birthday") or refreshed.get("birth_date") or refreshed.get("date_of_birth") or refreshed.get("dob")
        ),
        "mailing_address": _normalize(refreshed.get("mailing_address") or refreshed.get("address")) or None,
        "status": _normalize(refreshed.get("status")) or "active",
        "role": _user_role_value(refreshed),
        "access_tier": _normalize(refreshed.get("access_tier")) or None,
        "department_role": _normalize(refreshed.get("department_role")) or None,
    }
    _write_admin_action_audit(
        actor=actor,
        action="super_admin.user_update",
        target_type="user",
        target_id=current_user_id,
        before=before,
        after=after,
        context={"surface": "admin_control_center.super_admin"},
    )
    return {"user_id": current_user_id, "before": before, "after": after}


def super_admin_apply_user_state_action(
    *,
    user_id: str,
    action: str,
    actor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_action = _normalize(action).lower()
    mapped_status = SUPER_ADMIN_USER_STATE_ACTIONS.get(normalized_action)
    if not mapped_status:
        raise ValueError("Unsupported user state action.")
    return super_admin_update_user(
        user_id=user_id,
        payload={"status": mapped_status},
        actor=actor,
    )


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
        "phone_number": 1,
        "phone": 1,
        "mailing_address": 1,
        "address": 1,
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
        "phone_number": _normalize(user.get("phone_number") or user.get("phone")) or None,
        "mailing_address": _normalize(user.get("mailing_address") or user.get("address")) or None,
        "birthday": _serialize_datetime(
            user.get("birthday") or user.get("birth_date") or user.get("date_of_birth") or user.get("dob")
        ),
        "role": role,
        "status": _normalize(user.get("status")) or "active",
        "access_tier": _normalize(user.get("access_tier")) or None,
        "department_role": _normalize(user.get("department_role")) or None,
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
                "phone_number": _normalize(user.get("phone_number") or user.get("phone")) or None,
                "mailing_address": _normalize(user.get("mailing_address") or user.get("address")) or None,
                "birthday": _serialize_datetime(
                    user.get("birthday") or user.get("birth_date") or user.get("date_of_birth") or user.get("dob")
                ),
                "role": role,
                "status": status_value,
                "access_tier": _normalize(user.get("access_tier")) or None,
                "department_role": _normalize(user.get("department_role")) or None,
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


def list_customer_cases(
    *,
    search: str = "",
    limit: int = 50,
    queue: str = "customer_cases",
    current_user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    db = _db()
    safe_limit = max(1, min(limit, 200))
    normalized_queue = _normalize(queue).lower()
    if normalized_queue == "users":
        items = _list_user_account_cases(
            db=db,
            search=search,
            safe_limit=safe_limit,
        )
        return {"items": [_filter_case_item_for_access(item, current_user) for item in items]}

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
        if not _case_queue_match(queue, alerts, project=project, readiness=readiness):
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
            _filter_case_item_for_access(
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
                },
                current_user,
            )
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
                _filter_case_item_for_access(
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
                },
                current_user,
            )
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
    for related_order in related_orders:
        order_doc = _order_by_id(_normalize(related_order.get("id")))
        if order_doc:
            _record_order_finance_events(order_doc, source="customer_case_workspace")
    finance_events = _collect_finance_events(
        project_id=project_id,
        order_id=order_id,
        owner_email=owner_email,
        limit=40,
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
                "phone_number": identity.get("phone_number") or None,
                "mailing_address": identity.get("mailing_address") or None,
                "birthday": identity.get("birthday"),
                "role": identity.get("role") or "customer",
                "status": identity.get("status") or "active",
                "access_tier": identity.get("access_tier") or None,
                "department_role": identity.get("department_role") or None,
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
                "finance_history": finance_events,
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


def _filter_workspace_for_access(workspace: dict[str, Any], current_user: dict[str, Any] | None) -> dict[str, Any]:
    finance_profile = _finance_admin_profile(current_user)
    if finance_profile is None:
        return workspace

    filtered = dict(workspace)
    tabs = dict(filtered.get("tabs") or {})
    allowed_tabs = set(FINANCE_TAB_ALLOWLIST)
    filtered["tabs"] = {tab: value for tab, value in tabs.items() if tab in allowed_tabs}
    filtered.pop("uploads", None)
    filtered_alerts = [
        alert
        for alert in (filtered.get("alerts") or [])
        if _normalize(alert).lower() not in FINANCE_WORKSPACE_ALERT_EXCLUDE
    ]
    filtered["alerts"] = filtered_alerts
    filtered["operator_guidance"] = _filter_guidance_for_finance(filtered.get("operator_guidance") or [])
    readiness = dict(filtered.get("readiness") or {})
    filtered["readiness"] = {
        "package_synced": bool(readiness.get("package_synced")),
        "lane_assigned": bool(readiness.get("lane_assigned")),
        "order_linked": bool(readiness.get("order_linked")),
        "entitlement_exists": bool(readiness.get("entitlement_exists")),
        "summary": _normalize(readiness.get("summary")) or "Finance scope snapshot",
    }

    project_tab = dict((filtered.get("tabs") or {}).get("project") or {})
    project_tab.pop("uploads_summary", None)
    if "project" in filtered["tabs"]:
        filtered["tabs"]["project"] = project_tab

    orders_tab = dict((filtered.get("tabs") or {}).get("orders_billing") or {})
    events = orders_tab.get("finance_history")
    if not isinstance(events, list):
        events = []
    orders_tab["finance_history"] = [event for event in events if _normalize(event.get("event_type")) in FINANCE_EVENT_TYPES]
    filtered["tabs"]["orders_billing"] = orders_tab
    return filtered


def customer_case_workspace(
    case_id: str,
    *,
    current_user: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_case_id = _normalize(case_id)
    if not normalized_case_id:
        raise ValueError("Case id is required.")

    workspace_payload: dict[str, Any]
    if normalized_case_id.startswith("user:"):
        user_id = normalized_case_id.split(":", 1)[1]
        user = _find_case_user(user_id=user_id)
        if user is None:
            raise ValueError("User account case not found.")
        workspace_payload = _filter_workspace_for_access(_build_user_workspace_payload(user), current_user)
    elif normalized_case_id.startswith("order:"):
        order_id = normalized_case_id.split(":", 1)[1]
        order = _order_by_id(order_id)
        if order is None:
            raise ValueError("Order case not found.")
        project = _project_by_id(_normalize(order.get("project_id")))
        workspace_payload = _filter_workspace_for_access(_build_case_workspace_payload(
            case_id=normalized_case_id,
            project=project,
            order=order,
        ), current_user)
    else:
        project, order = _resolve_project_order_context(normalized_case_id)
        workspace_payload = _filter_workspace_for_access(_build_case_workspace_payload(
            case_id=normalized_case_id,
            project=project,
            order=order,
        ), current_user)
    _write_admin_action_audit(
        actor=current_user,
        action="operations.sensitive_record_access",
        target_type="customer_case",
        target_id=normalized_case_id,
        context={"surface": "admin_control_center.workspace"},
        details={
            "viewed_tabs": sorted((workspace_payload.get("tabs") or {}).keys()),
            "alerts": list(workspace_payload.get("alerts") or []),
        },
    )
    return workspace_payload


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
        payload = customer_case_workspace(normalized_case_id, current_user=actor)
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


def _super_admin_actor_snapshot(actor: dict[str, Any] | None) -> dict[str, Any]:
    actor = actor or {}
    role_codes = actor.get("role_codes") or []
    normalized_codes = [normalize_role_code(code) for code in role_codes if normalize_role_code(code)]
    fallback_role = normalize_role_code(actor.get("role") or actor.get("access_tier") or actor.get("department_role"))
    primary_role = resolve_primary_role_code(normalized_codes) or fallback_role or "super_admin"
    return {
        "actor_user_id": _normalize(actor.get("_id") or actor.get("id") or actor.get("user_id")) or None,
        "actor_email": _normalize_email(actor.get("email")) or None,
        "actor_name": _normalize(actor.get("full_name") or actor.get("name")) or None,
        "actor_role": primary_role,
    }


def _resolve_case_project_order(case_id: str) -> tuple[str, str]:
    normalized_case_id = _normalize(case_id)
    project_id = normalized_case_id
    order_id = ""
    if normalized_case_id.startswith("order:"):
        order_id = normalized_case_id.split(":", 1)[1]
        order = _order_by_id(order_id)
        if order is None:
            raise ValueError("Order case not found.")
        project_id = _normalize(order.get("project_id"))
    elif normalized_case_id.startswith("user:"):
        user = _find_case_user(user_id=normalized_case_id.split(":", 1)[1])
        if user is None:
            raise ValueError("User case not found.")
        related_projects = _related_projects_for_user(user)
        project_id = _normalize((related_projects[0] or {}).get("_id")) if related_projects else ""
    if project_id and _project_by_id(project_id) is None:
        project_id = ""
    if not order_id and project_id:
        linked_order = _latest_linked_order(project_id)
        order_id = _normalize((linked_order or {}).get("_id"))
    return project_id, order_id


def _admin_repair_confirmed(payload: dict[str, Any]) -> bool:
    return bool(payload.get("confirm_destructive") or payload.get("confirm") or payload.get("confirmed"))


def _super_admin_update_relationship(*, payload: dict[str, Any], project_id: str) -> dict[str, Any]:
    db = _db()
    relationship_id = _normalize(payload.get("relationship_id"))
    if not relationship_id:
        raise ValueError("relationship_id is required.")
    relationship_oid = _to_object_id(relationship_id)
    relationship = db["relationships"].find_one({"_id": relationship_oid}) if relationship_oid else None
    if relationship is None:
        raise ValueError("Relationship record was not found.")
    before = {
        "source_member_id": _normalize(relationship.get("source_member_id")),
        "target_member_id": _normalize(relationship.get("target_member_id")),
        "relationship_type": normalize_relationship_type(relationship.get("relationship_type")),
        "notes": _normalize(relationship.get("notes")),
    }
    updates: dict[str, Any] = {}
    if _normalize(payload.get("source_member_id")):
        updates["source_member_id"] = _normalize(payload.get("source_member_id"))
    if _normalize(payload.get("target_member_id")):
        updates["target_member_id"] = _normalize(payload.get("target_member_id"))
    if _normalize(payload.get("relationship_type")):
        updates["relationship_type"] = normalize_relationship_type(payload.get("relationship_type"))
    if "notes" in payload:
        updates["notes"] = _normalize(payload.get("notes"))
    if not updates:
        raise ValueError("No relationship updates were provided.")
    updates["updated_at"] = _now().isoformat()
    db["relationships"].update_one({"_id": relationship_oid}, {"$set": updates})
    after_doc = db["relationships"].find_one({"_id": relationship_oid}) or {}
    after = {
        "source_member_id": _normalize(after_doc.get("source_member_id")),
        "target_member_id": _normalize(after_doc.get("target_member_id")),
        "relationship_type": normalize_relationship_type(after_doc.get("relationship_type")),
        "notes": _normalize(after_doc.get("notes")),
    }
    return {"target_type": "relationship", "target_id": relationship_id, "before": before, "after": after, "project_id": project_id}


def _super_admin_relink_person(*, payload: dict[str, Any], project_id: str) -> dict[str, Any]:
    db = _db()
    member_id = _normalize(payload.get("member_id"))
    if not member_id:
        raise ValueError("member_id is required.")
    member_oid = _to_object_id(member_id)
    member = db["family_members"].find_one({"_id": member_oid}) if member_oid else None
    if member is None:
        raise ValueError("Family member was not found.")
    before = {
        "family_id": _normalize(member.get("family_id")),
        "household_id": _normalize(member.get("household_id")),
        "network_id": _normalize(member.get("network_id")),
    }
    updates: dict[str, Any] = {}
    for key in ("family_id", "household_id", "network_id"):
        value = _normalize(payload.get(key))
        if value:
            updates[key] = value
    if not updates:
        raise ValueError("Provide at least one target linkage field to relink this person.")
    updates["updated_at"] = _now().isoformat()
    db["family_members"].update_one({"_id": member_oid}, {"$set": updates})
    after_doc = db["family_members"].find_one({"_id": member_oid}) or {}
    after = {
        "family_id": _normalize(after_doc.get("family_id")),
        "household_id": _normalize(after_doc.get("household_id")),
        "network_id": _normalize(after_doc.get("network_id")),
    }
    return {"target_type": "family_member", "target_id": member_id, "before": before, "after": after, "project_id": project_id}


def _super_admin_add_missing_parent(*, payload: dict[str, Any], project_id: str) -> dict[str, Any]:
    db = _db()
    child_member_id = _normalize(payload.get("child_member_id") or payload.get("target_member_id"))
    if not child_member_id:
        raise ValueError("child_member_id is required.")
    parent_member_id = _normalize(payload.get("parent_member_id") or payload.get("source_member_id"))
    relationship_type = normalize_relationship_type(payload.get("relationship_type") or "biological_parent")
    child_oid = _to_object_id(child_member_id)
    child = db["family_members"].find_one({"_id": child_oid}) if child_oid else None
    if child is None:
        raise ValueError("Child member was not found.")
    created_parent = False
    if not parent_member_id:
        parent_document = {
            "family_id": _normalize(payload.get("family_id")) or _normalize(child.get("family_id")),
            "first_name": _normalize(payload.get("parent_first_name")) or "Unknown",
            "last_name": _normalize(payload.get("parent_last_name")) or "Parent",
            "generation": int(child.get("generation") or 1) - 1,
            "birth_year": payload.get("parent_birth_year"),
            "bio": _normalize(payload.get("notes")) or "Added by super admin repair workflow.",
            "created_at": _now().isoformat(),
            "updated_at": _now().isoformat(),
            "created_by": "super_admin_repair",
        }
        inserted = db["family_members"].insert_one(parent_document)
        parent_member_id = _normalize(inserted.inserted_id)
        created_parent = True
    existing = db["relationships"].find_one(
        {
            "source_member_id": parent_member_id,
            "target_member_id": child_member_id,
            "relationship_type": relationship_type,
        }
    )
    if existing:
        relationship_id = _normalize(existing.get("_id"))
    else:
        rel_document = {
            "family_id": _normalize(payload.get("family_id")) or _normalize(child.get("family_id")),
            "source_member_id": parent_member_id,
            "target_member_id": child_member_id,
            "relationship_type": relationship_type,
            "notes": _normalize(payload.get("notes")) or "Added by super admin repair workflow.",
            "created_at": _now().isoformat(),
            "updated_at": _now().isoformat(),
            "created_by": "super_admin_repair",
        }
        inserted_rel = db["relationships"].insert_one(rel_document)
        relationship_id = _normalize(inserted_rel.inserted_id)
    return {
        "target_type": "family_link",
        "target_id": relationship_id,
        "before": {"relationship_present": bool(existing), "created_parent": False},
        "after": {
            "relationship_present": True,
            "created_parent": created_parent,
            "parent_member_id": parent_member_id,
            "child_member_id": child_member_id,
            "relationship_type": relationship_type,
        },
        "project_id": project_id,
    }


def _super_admin_correct_child_or_spouse(*, payload: dict[str, Any], project_id: str, default_type: str) -> dict[str, Any]:
    db = _db()
    source_member_id = _normalize(payload.get("source_member_id"))
    target_member_id = _normalize(payload.get("target_member_id"))
    if not source_member_id or not target_member_id:
        raise ValueError("source_member_id and target_member_id are required.")
    relationship_type = normalize_relationship_type(payload.get("relationship_type") or default_type)
    existing = db["relationships"].find_one(
        {
            "source_member_id": source_member_id,
            "target_member_id": target_member_id,
            "relationship_type": relationship_type,
        }
    )
    if existing is None and relationship_type in {"spouse", "former_spouse", "household_member"}:
        existing = db["relationships"].find_one(
            {
                "source_member_id": target_member_id,
                "target_member_id": source_member_id,
                "relationship_type": relationship_type,
            }
        )
    before = {"relationship_present": bool(existing)}
    if existing:
        rel_id = _normalize(existing.get("_id"))
        db["relationships"].update_one(
            {"_id": existing.get("_id")},
            {"$set": {"notes": _normalize(payload.get("notes")) or _normalize(existing.get("notes")), "updated_at": _now().isoformat()}},
        )
    else:
        rel_document = {
            "family_id": _normalize(payload.get("family_id")),
            "source_member_id": source_member_id,
            "target_member_id": target_member_id,
            "relationship_type": relationship_type,
            "notes": _normalize(payload.get("notes")) or "Added by super admin repair workflow.",
            "created_at": _now().isoformat(),
            "updated_at": _now().isoformat(),
            "created_by": "super_admin_repair",
        }
        inserted = db["relationships"].insert_one(rel_document)
        rel_id = _normalize(inserted.inserted_id)
    return {
        "target_type": "relationship",
        "target_id": rel_id,
        "before": before,
        "after": {
            "relationship_present": True,
            "source_member_id": source_member_id,
            "target_member_id": target_member_id,
            "relationship_type": relationship_type,
        },
        "project_id": project_id,
    }


def _super_admin_fix_household_member_access(*, payload: dict[str, Any], project_id: str) -> dict[str, Any]:
    db = _db()
    membership_id = _normalize(payload.get("membership_id"))
    if not membership_id:
        raise ValueError("membership_id is required.")
    membership_oid = _to_object_id(membership_id)
    membership = db["project_members"].find_one({"_id": membership_oid}) if membership_oid else None
    if membership is None:
        raise ValueError("Project membership was not found.")
    before = {
        "member_role": _normalize(membership.get("member_role")),
        "relationship_scope": _normalize(membership.get("relationship_scope")),
        "privacy_scope": _normalize(membership.get("privacy_scope")),
        "status": _normalize(membership.get("status")),
        "project_id": _normalize(membership.get("project_id")),
    }
    updates: dict[str, Any] = {}
    for key in ("member_role", "relationship_scope", "privacy_scope", "status"):
        if key in payload and _normalize(payload.get(key)):
            updates[key] = _normalize(payload.get(key))
    if not updates:
        raise ValueError("No membership updates were provided.")
    updates["updated_at"] = _now().isoformat()
    db["project_members"].update_one({"_id": membership_oid}, {"$set": updates})
    after_doc = db["project_members"].find_one({"_id": membership_oid}) or {}
    after = {
        "member_role": _normalize(after_doc.get("member_role")),
        "relationship_scope": _normalize(after_doc.get("relationship_scope")),
        "privacy_scope": _normalize(after_doc.get("privacy_scope")),
        "status": _normalize(after_doc.get("status")),
        "project_id": _normalize(after_doc.get("project_id")),
    }
    return {"target_type": "project_member", "target_id": membership_id, "before": before, "after": after, "project_id": project_id}


def _super_admin_repair_invite(*, payload: dict[str, Any], project_id: str, action: str) -> dict[str, Any]:
    db = _db()
    invite_id = _normalize(payload.get("invite_id"))
    if not invite_id:
        raise ValueError("invite_id is required.")
    invite_oid = _to_object_id(invite_id)
    invite = db["household_invites"].find_one({"_id": invite_oid}) if invite_oid else None
    if invite is None:
        raise ValueError("Household invite was not found.")
    before = {
        "email": _normalize_email(invite.get("email")),
        "status": _normalize(invite.get("status")),
        "invite_key": _normalize(invite.get("invite_key")),
        "expires_at": invite.get("expires_at"),
    }
    now_iso = _now().isoformat()
    if action == "cancel_invite":
        if not _admin_repair_confirmed(payload):
            raise ValueError("Destructive invite cancellation requires confirm_destructive=true.")
        updates = {"status": "revoked", "revoked_at": now_iso, "updated_at": now_iso}
    elif action == "resend_invite":
        new_key = f"hhinv_{secrets.token_urlsafe(24)}"
        updates = {
            "status": "pending",
            "invite_key": new_key,
            "use_count": 0,
            "accepted_at": None,
            "revoked_at": None,
            "expired_at": None,
            "updated_at": now_iso,
            "expires_at": (_now() + timedelta(days=7)).isoformat(),
        }
    elif action == "update_invite_email":
        new_email = _normalize_email(payload.get("invite_email"))
        if not new_email:
            raise ValueError("invite_email is required.")
        updates = {"email": new_email, "target_email": new_email, "updated_at": now_iso}
    else:
        raise ValueError("Unsupported invite repair action.")
    db["household_invites"].update_one({"_id": invite_oid}, {"$set": updates})
    after_doc = db["household_invites"].find_one({"_id": invite_oid}) or {}
    after = {
        "email": _normalize_email(after_doc.get("email")),
        "status": _normalize(after_doc.get("status")),
        "invite_key": _normalize(after_doc.get("invite_key")),
        "expires_at": after_doc.get("expires_at"),
    }
    if action == "resend_invite":
        send_household_invite_email(
            to_email=after["email"],
            invite_key=after["invite_key"],
            project_id=_normalize(after_doc.get("project_id")),
            member_role=_normalize(after_doc.get("member_role")) or "viewer",
            inviter_email=_normalize_email((payload.get("actor_email") or "")),
            is_resend=True,
        )
    return {"target_type": "household_invite", "target_id": invite_id, "before": before, "after": after, "project_id": project_id}


def _super_admin_repair_tree_rendering(*, payload: dict[str, Any], project_id: str) -> dict[str, Any]:
    db = _db()
    family_id = _normalize(payload.get("family_id"))
    if not family_id:
        raise ValueError("family_id is required.")

    relationships = list(db["relationships"].find({"family_id": family_id}))
    before = {
        "relationship_count": len(relationships),
        "normalized_relationship_types": 0,
        "deduplicated_relationships": 0,
    }
    if not relationships:
        return {
            "target_type": "family_tree",
            "target_id": family_id,
            "before": before,
            "after": before,
            "project_id": project_id,
        }

    normalized_updates = 0
    dedupe_removed = 0
    seen_keys: dict[tuple[str, str, str], ObjectId] = {}
    for rel in relationships:
        rel_id = rel.get("_id")
        rel_type = normalize_relationship_type(rel.get("relationship_type"))
        source_member_id = _normalize(rel.get("source_member_id"))
        target_member_id = _normalize(rel.get("target_member_id"))
        if not source_member_id or not target_member_id:
            continue
        if rel_type in {"spouse", "former_spouse", "sibling", "household_member"}:
            pair = sorted([source_member_id, target_member_id])
            key = (pair[0], pair[1], rel_type)
        else:
            key = (source_member_id, target_member_id, rel_type)

        if key in seen_keys and rel_id:
            db["relationships"].delete_one({"_id": rel_id})
            dedupe_removed += 1
            continue
        if rel_id:
            seen_keys[key] = rel_id

        updates: dict[str, Any] = {}
        if _normalize(rel.get("relationship_type")) != rel_type:
            updates["relationship_type"] = rel_type
        if updates and rel_id:
            updates["updated_at"] = _now().isoformat()
            db["relationships"].update_one({"_id": rel_id}, {"$set": updates})
            normalized_updates += 1

    after = {
        "relationship_count": int(db["relationships"].count_documents({"family_id": family_id})),
        "normalized_relationship_types": normalized_updates,
        "deduplicated_relationships": dedupe_removed,
    }
    return {
        "target_type": "family_tree",
        "target_id": family_id,
        "before": before,
        "after": after,
        "project_id": project_id,
    }


def super_admin_repair_case_action(
    *,
    case_id: str,
    action: str,
    payload: dict[str, Any] | None = None,
    actor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_case_id = _normalize(case_id)
    normalized_action = _normalize(action).lower()
    if not normalized_case_id:
        raise ValueError("Case id is required.")
    if not normalized_action:
        raise ValueError("Repair action is required.")

    payload = dict(payload or {})
    reason = _normalize(payload.get("reason") or payload.get("note"))
    if not reason:
        raise ValueError("A repair reason is required for audit traceability.")
    project_id, order_id = _resolve_case_project_order(normalized_case_id)
    actor_snapshot = _super_admin_actor_snapshot(actor)
    payload["actor_email"] = actor_snapshot.get("actor_email")

    before_workspace = customer_case_workspace(normalized_case_id)
    action_handlers: dict[str, Callable[[], dict[str, Any]]] = {
        "fix_family_relationship": lambda: _super_admin_update_relationship(payload=payload, project_id=project_id),
        "relink_person": lambda: _super_admin_relink_person(payload=payload, project_id=project_id),
        "add_missing_parent": lambda: _super_admin_add_missing_parent(payload=payload, project_id=project_id),
        "correct_spouse_connection": lambda: _super_admin_correct_child_or_spouse(
            payload=payload, project_id=project_id, default_type="spouse"
        ),
        "correct_child_connection": lambda: _super_admin_correct_child_or_spouse(
            payload=payload, project_id=project_id, default_type="biological_parent"
        ),
        "fix_household_member_access": lambda: _super_admin_fix_household_member_access(
            payload=payload, project_id=project_id
        ),
        "resend_invite": lambda: _super_admin_repair_invite(payload=payload, project_id=project_id, action="resend_invite"),
        "cancel_invite": lambda: _super_admin_repair_invite(payload=payload, project_id=project_id, action="cancel_invite"),
        "update_invite_email": lambda: _super_admin_repair_invite(payload=payload, project_id=project_id, action="update_invite_email"),
        "repair_entitlement": lambda: {
            "target_type": "project",
            "target_id": project_id,
            "before": {"entitlement": get_project_entitlement(project_id) if project_id else None},
            "after": {"entitlement": generate_entitlement(project_id=project_id, order_id=order_id, force=True)},
            "project_id": project_id,
        },
        "repair_package_lane": lambda: {
            "target_type": "project",
            "target_id": project_id,
            "before": {"project": _serialize_project(_project_by_id(project_id) or {}) if project_id else None},
            "after": {
                "sync": sync_package(project_id=project_id, order_id=order_id),
                "lane": assign_lane(project_id=project_id),
            },
            "project_id": project_id,
        },
        "repair_tree_rendering": lambda: _super_admin_repair_tree_rendering(
            payload=payload, project_id=project_id
        ),
    }

    handler = action_handlers.get(normalized_action)
    if handler is None:
        raise ValueError("Unsupported super admin repair action.")
    if normalized_action in {"cancel_invite"} and not _admin_repair_confirmed(payload):
        raise ValueError("Destructive actions require confirm_destructive=true.")

    repair_result = handler()
    after_workspace = customer_case_workspace(normalized_case_id)
    write_audit_log(
        actor_user_id=actor_snapshot.get("actor_user_id"),
        actor_email=actor_snapshot.get("actor_email"),
        actor_name=actor_snapshot.get("actor_name"),
        action=f"super_admin_repair.{normalized_action}",
        target_type=_normalize(repair_result.get("target_type")) or "customer_case",
        target_id=_normalize(repair_result.get("target_id")) or normalized_case_id,
        before=repair_result.get("before") or {},
        after=repair_result.get("after") or {},
        context={
            "case_id": normalized_case_id,
            "project_id": project_id,
            "order_id": order_id,
            "actor_role": actor_snapshot.get("actor_role"),
            "reason": reason,
        },
        details={"requested_payload": payload},
        result="success",
    )
    return {
        "status": "repaired",
        "case_id": normalized_case_id,
        "action": normalized_action,
        "project_id": project_id or None,
        "order_id": order_id or None,
        "repair_result": repair_result,
        "before_workspace_alerts": before_workspace.get("alerts") or [],
        "after_workspace_alerts": after_workspace.get("alerts") or [],
    }
