"""Operational Continuity Kernel orchestration.

This service turns the earlier isolated Continuity Kernel contracts into a
governed runtime around the repair capabilities that already exist in the
Tomb of Light backend.  It does not replace the domain services.  It records
the request, approval, evidence packet, state transitions, execution result,
and immutable event trail before delegating to an allow-listed operation.

No operation runs automatically.  Every write requires an authenticated
admin request, an allowed officer role, a reason, an idempotency key, an
approval, and an explicit execute call.  The solo-founder convenience path
still records the full state machine and requires an acknowledged CEO
override for high-risk same-requester execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib import import_module
import hashlib
import os
from pathlib import Path
import sys
from typing import Any
from uuid import uuid4

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError

from app.core.admin_permission_registry import CEO_MASTER_ADMIN_EMAIL
from app.database import get_database
from app.services import (
    admin_control_service,
    manual_fulfillment_service,
    stripe_admin_operations_service,
)
from app.services.auth_service import admin_issue_password_reset
from app.services.audit_log_service import write_audit_log


RUNTIME_VERSION = "12.0.0"
OPERATIONS_COLLECTION = "continuity_operations"
EVENTS_COLLECTION = "continuity_events"
EXECUTION_KILL_SWITCH = "CONTINUITY_EXECUTION_KILL_SWITCH"
MAX_OPERATION_LIST_LIMIT = 200
STALE_EXECUTION_RETRY_MINUTES = 15


@dataclass(frozen=True)
class ActionSpec:
    repair_category: str
    risk_level: str
    target_type: str
    required_target_fields: tuple[str, ...] = ()
    mutates_business_data: bool = True


CASE_ACTION_SPECS: dict[str, ActionSpec] = {
    "sync_package": ActionSpec("package_lane_normalization", "medium", "customer_case", ("case_id",)),
    "normalize_package": ActionSpec("package_lane_normalization", "medium", "customer_case", ("case_id",)),
    "assign_lane": ActionSpec("package_lane_normalization", "medium", "customer_case", ("case_id",)),
    "link_order_to_project": ActionSpec("billing_order_payment_repair", "high", "customer_case", ("case_id",)),
    "generate_entitlement": ActionSpec("missing_entitlement_repair", "high", "customer_case", ("case_id",)),
    "refresh_entitlement": ActionSpec("missing_entitlement_repair", "high", "customer_case", ("case_id",)),
    "run_readiness_check": ActionSpec(
        "admin_repair_safety", "low", "customer_case", ("case_id",), mutates_business_data=False
    ),
    "queue_for_mint_review": ActionSpec("mint_readiness_repair", "high", "customer_case", ("case_id",)),
    "prepare_legacy_anchor": ActionSpec("mint_readiness_repair", "high", "customer_case", ("case_id",)),
    "approve_legacy_anchor": ActionSpec("mint_readiness_repair", "high", "customer_case", ("case_id",)),
    "queue_approved_legacy_anchor": ActionSpec("mint_readiness_repair", "high", "customer_case", ("case_id",)),
    "repair_record": ActionSpec("admin_repair_safety", "high", "customer_case", ("case_id",)),
    "repair_mint_status": ActionSpec("mint_readiness_repair", "high", "customer_case", ("case_id",)),
    "rebuild_mint_summary": ActionSpec("mint_readiness_repair", "high", "customer_case", ("case_id",)),
    "resync_mint_receipt": ActionSpec("mint_readiness_repair", "medium", "customer_case", ("case_id",)),
    "refresh_case_data": ActionSpec(
        "admin_repair_safety", "low", "customer_case", ("case_id",), mutates_business_data=False
    ),
}


BULK_ACTION_SPECS: dict[str, ActionSpec] = {
    "repair_missing_entitlements": ActionSpec("missing_entitlement_repair", "high", "bulk_repair"),
    "assign_missing_lanes": ActionSpec("package_lane_normalization", "high", "bulk_repair"),
    "link_unlinked_paid_orders": ActionSpec("billing_order_payment_repair", "high", "bulk_repair"),
    "normalize_broken_package_records": ActionSpec("package_lane_normalization", "high", "bulk_repair"),
    "refresh_mint_readiness": ActionSpec("mint_readiness_repair", "high", "bulk_repair"),
    "repair_selected_records": ActionSpec("admin_repair_safety", "high", "bulk_repair"),
    "repair_all_safe_records": ActionSpec("admin_repair_safety", "high", "bulk_repair"),
}


SUPER_ADMIN_ACTION_SPECS: dict[str, ActionSpec] = {
    "package_change": ActionSpec("package_lane_normalization", "high", "project", ("project_id",)),
    "package_revoke": ActionSpec("admin_repair_safety", "high", "project", ("project_id",)),
    "package_restore": ActionSpec("admin_repair_safety", "high", "project", ("project_id",)),
    "service_controls": ActionSpec("admin_repair_safety", "high", "project", ("project_id",)),
    "officer_permissions": ActionSpec("admin_repair_safety", "high", "officer", ("officer_email",)),
    "account_lifecycle": ActionSpec("admin_repair_safety", "high", "user", ("user_id",)),
    "account_permanent_delete": ActionSpec("admin_repair_safety", "high", "user", ("user_id",)),
    "orphan_identity_reconciliation": ActionSpec(
        "admin_repair_safety",
        "high",
        "removed_identity",
        ("identity_email",),
    ),
    "case_repair": ActionSpec("admin_repair_safety", "high", "customer_case", ("case_id",)),
    "customer_package_provision": ActionSpec(
        "missing_entitlement_repair", "high", "user", ("user_id",)
    ),
    "legacy_admin_remediation": ActionSpec(
        "admin_repair_safety", "high", "user", ("user_id",)
    ),
}


CONTROL_SURFACE_ACTION_SPECS: dict[str, ActionSpec] = {
    "manual_fulfillment": ActionSpec(
        "billing_order_payment_repair", "high", "order", ("order_id",)
    ),
    "stripe_operation": ActionSpec(
        "billing_order_payment_repair", "high", "stripe", ("target_id",)
    ),
    "customer_account_create": ActionSpec(
        "admin_repair_safety", "high", "user", ("customer_email",)
    ),
    "user_profile_update": ActionSpec(
        "admin_repair_safety", "high", "user", ("user_id",)
    ),
    "user_password_reset": ActionSpec(
        "admin_repair_safety", "high", "user", ("user_id",)
    ),
    "project_ownership_transfer": ActionSpec(
        "admin_repair_safety", "high", "project", ("project_id",)
    ),
    "impersonation_start": ActionSpec(
        "admin_repair_safety", "medium", "customer_case", ("case_id",)
    ),
    "impersonation_stop": ActionSpec(
        "admin_repair_safety", "medium", "impersonation_session", ("session_id",)
    ),
    "upload_rescan": ActionSpec(
        "admin_repair_safety", "medium", "upload", ("upload_id",)
    ),
    "portrait_review": ActionSpec(
        "admin_repair_safety", "high", "upload", ("upload_id",)
    ),
    "evidence_review": ActionSpec(
        "admin_repair_safety", "high", "upload", ("upload_id",)
    ),
}


ACTION_SPECS: dict[str, ActionSpec] = {
    **CASE_ACTION_SPECS,
    **BULK_ACTION_SPECS,
    **SUPER_ADMIN_ACTION_SPECS,
    **CONTROL_SURFACE_ACTION_SPECS,
}


def _now() -> datetime:
    return datetime.now(UTC)


def _now_iso() -> str:
    return _now().isoformat()


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _normalize_action(value: Any) -> str:
    return _normalize(value).lower().replace("-", "_")


def _serialize(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat() if value.tzinfo else value.replace(tzinfo=UTC).isoformat()
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_serialize(item) for item in value]
    return value


def _operations_collection():
    return get_database()[OPERATIONS_COLLECTION]


def _events_collection():
    return get_database()[EVENTS_COLLECTION]


def execution_enabled(env: Any | None = None) -> bool:
    environment = env if env is not None else os.environ
    raw = _normalize(environment.get(EXECUTION_KILL_SWITCH)).lower()
    return raw not in {"1", "true", "yes", "on", "enabled"}


def ensure_continuity_runtime_indexes() -> None:
    operations = _operations_collection()
    operations.create_index([("operation_id", ASCENDING)], unique=True, name="continuity_operation_id_unique")
    operations.create_index([("idempotency_key", ASCENDING)], unique=True, name="continuity_idempotency_unique")
    operations.create_index([("state", ASCENDING), ("updated_at", DESCENDING)], name="continuity_state_updated")
    operations.create_index([("target.target_id", ASCENDING), ("updated_at", DESCENDING)], name="continuity_target_updated")

    events = _events_collection()
    events.create_index([("event_id", ASCENDING)], unique=True, name="continuity_event_id_unique")
    events.create_index([("operation_id", ASCENDING), ("created_at", ASCENDING)], name="continuity_operation_events")
    events.create_index([("target_id", ASCENDING), ("created_at", DESCENDING)], name="continuity_target_events")

    tombstones = get_database()[admin_control_service.ACCOUNT_DELETION_TOMBSTONES_COLLECTION]
    tombstones.create_index([("deletion_id", ASCENDING)], unique=True, name="account_deletion_id_unique")
    tombstones.create_index([("user_id", ASCENDING)], unique=True, name="account_deletion_user_unique")
    tombstones.create_index([("original_email_sha256", ASCENDING)], name="account_deletion_email_hash")


def _actor_id(actor: dict[str, Any] | None) -> str:
    actor = actor or {}
    return _normalize(actor.get("_id") or actor.get("id") or actor.get("user_id"))


def _actor_email(actor: dict[str, Any] | None) -> str:
    return _normalize((actor or {}).get("email")).lower()


def _actor_name(actor: dict[str, Any] | None) -> str:
    actor = actor or {}
    full_name = _normalize(actor.get("full_name"))
    if full_name:
        return full_name
    return " ".join(
        value for value in (_normalize(actor.get("first_name")), _normalize(actor.get("last_name"))) if value
    )


def canonical_officer_role(actor: dict[str, Any] | None) -> str:
    actor = actor or {}
    email = _actor_email(actor)
    access_context = actor.get("_access_context") or {}
    role_values = {
        _normalize(actor.get("role")).lower(),
        _normalize(actor.get("department_role")).lower(),
        _normalize(actor.get("access_tier")).lower(),
    }
    role_values.update(_normalize(item).lower() for item in (actor.get("role_codes") or []))
    role_values.update(_normalize(item).lower() for item in (access_context.get("role_codes") or []))

    if email == CEO_MASTER_ADMIN_EMAIL.lower():
        return "SUPERADMIN"
    if role_values.intersection({"executive_tech_admin", "cto", "technical_admin"}):
        return "EXECUTIVE_TECH_ADMIN"
    if role_values.intersection({"coo", "operations_admin", "operations"}):
        return "operations_admin"
    if role_values.intersection({"cfo", "finance_admin", "finance"}):
        return "finance_admin"
    if role_values.intersection({"cmo", "marketing_admin", "marketing"}):
        return "CMO"
    return ""


def _actor_snapshot(actor: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "actor_user_id": _actor_id(actor),
        "actor_email": _actor_email(actor),
        "actor_name": _actor_name(actor),
        "actor_role": canonical_officer_role(actor),
    }


def _taxonomy_module():
    module_name = "app.core." + "continuity" + "_kernel_taxonomy"
    return import_module(module_name)


def _validator_module():
    module_name = "app.core." + "continuity" + "_kernel_validator"
    try:
        return import_module(module_name)
    except ModuleNotFoundError as exc:
        # The legacy isolated validator uses the repository-root import path
        # (``backend.app``), while the deployed API is commonly launched from
        # ``backend/`` with ``app`` as the top-level package.  Make the
        # repository root available only for this compatibility import.
        if exc.name != "backend":
            raise
        repository_root = str(Path(__file__).resolve().parents[3])
        if repository_root not in sys.path:
            sys.path.insert(0, repository_root)
        fallback_name = "backend.app.core." + "continuity" + "_kernel_validator"
        return import_module(fallback_name)


def _assert_action_allowed_for_actor(spec: ActionSpec, actor: dict[str, Any] | None) -> str:
    role = canonical_officer_role(actor)
    if not role:
        raise PermissionError("The authenticated admin role is not recognized by Continuity Kernel policy.")
    allowed_categories = _taxonomy_module().allowed_categories_for_role(role)
    if spec.repair_category not in allowed_categories:
        raise PermissionError(f"Role {role} cannot approve {spec.repair_category} operations.")
    return role


def _assert_action_actor_scope(action: str, actor: dict[str, Any] | None) -> None:
    normalized_action = _normalize(action)
    if normalized_action not in {
        "account_permanent_delete",
        "orphan_identity_reconciliation",
        "customer_package_provision",
    }:
        return
    if _actor_email(actor) == str(CEO_MASTER_ADMIN_EMAIL).strip().lower():
        return
    if normalized_action == "account_permanent_delete":
        raise PermissionError(
            "Permanent account deletion is restricted to the canonical CEO Master Administrator."
        )
    if normalized_action == "orphan_identity_reconciliation":
        raise PermissionError(
            "Manual identity reconciliation is restricted to the canonical CEO Master Administrator."
        )
    raise PermissionError(
        "First-project package provisioning is restricted to the canonical CEO Master Administrator."
    )


def _require_text(value: Any, field: str, *, minimum: int = 1) -> str:
    normalized = _normalize(value)
    if len(normalized) < minimum:
        raise ValueError(f"{field} is required and must contain at least {minimum} characters.")
    return normalized


def _require_permanent_deletion_confirmations(parameters: dict[str, Any]) -> None:
    if parameters.get("initial_confirmation") is not True:
        raise ValueError("The target-account permanent-deletion confirmation is required.")
    if _normalize(parameters.get("final_confirmation")) != admin_control_service.PERMANENT_DELETE_CONFIRMATION_PHRASE:
        raise ValueError(
            f'Type "{admin_control_service.PERMANENT_DELETE_CONFIRMATION_PHRASE}" to authorize permanent deletion.'
        )
    if parameters.get("final_acknowledgement") is not True:
        raise ValueError("The final permanent-closure acknowledgement is required.")


def _require_orphan_reconciliation_confirmations(
    parameters: dict[str, Any],
) -> None:
    if parameters.get("initial_confirmation") is not True:
        raise ValueError(
            "The post-hoc manual-removal reconciliation confirmation is required."
        )
    if (
        _normalize(parameters.get("final_confirmation"))
        != admin_control_service.ORPHAN_RECONCILIATION_CONFIRMATION_PHRASE
    ):
        raise ValueError(
            f'Type "{admin_control_service.ORPHAN_RECONCILIATION_CONFIRMATION_PHRASE}" '
            "to authorize reconciliation."
        )
    if parameters.get("final_acknowledgement") is not True:
        raise ValueError(
            "The final manual-removal reconciliation acknowledgement is required."
        )


def _target_id(spec: ActionSpec, action: str, target: dict[str, Any]) -> str:
    for field in (
        "case_id",
        "project_id",
        "order_id",
        "user_id",
        "identity_email",
        "officer_email",
        "customer_email",
        "session_id",
        "upload_id",
        "target_id",
    ):
        value = _normalize(target.get(field))
        if value:
            return value
    if spec.target_type == "bulk_repair":
        return f"bulk::{action}"
    raise ValueError("A scoped target identifier is required.")


def _validate_target(spec: ActionSpec, action: str, target: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(target, dict):
        raise ValueError("target must be an object.")
    cleaned = _serialize(target)
    for field in spec.required_target_fields:
        _require_text(cleaned.get(field), f"target.{field}")
    cleaned["target_type"] = spec.target_type
    cleaned["target_id"] = _target_id(spec, action, cleaned)
    return cleaned


def _safe_document(document: dict[str, Any] | None, fields: tuple[str, ...]) -> dict[str, Any] | None:
    if not document:
        return None
    payload = {field: document.get(field) for field in fields if field in document}
    if "_id" in document:
        payload["id"] = document.get("_id")
    return _serialize(payload)


def _id_candidates(raw_value: Any) -> list[Any]:
    value = _normalize(raw_value)
    if not value:
        return []
    candidates: list[Any] = [value]
    if ObjectId.is_valid(value):
        candidates.insert(0, ObjectId(value))
    return candidates


def _find_by_id(collection: Any, raw_value: Any) -> dict[str, Any] | None:
    for candidate in _id_candidates(raw_value):
        document = collection.find_one({"_id": candidate})
        if document is not None:
            return document
    return None


def _count(collection: Any, query: dict[str, Any]) -> int:
    try:
        return int(collection.count_documents(query))
    except Exception:
        return 0


def _project_operational_snapshot(project_id: str) -> dict[str, Any]:
    project_id = _require_text(project_id, "project_id")
    db = get_database()
    project = _find_by_id(db["projects"], project_id)
    if project is None:
        raise ValueError("Project not found.")

    project_refs = _id_candidates(project_id)
    entitlement = db["project_entitlements"].find_one({"project_id": {"$in": project_refs}})
    order = db["orders"].find_one(
        {"project_id": {"$in": project_refs}},
        sort=[("updated_at", -1), ("created_at", -1)],
    )
    mint_record = db["mint_records"].find_one(
        {"project_id": {"$in": project_refs}},
        sort=[("version_number", -1), ("updated_at", -1)],
    )

    return {
        "project": _safe_document(
            project,
            (
                "owner_user_id",
                "owner_email",
                "package_code",
                "package_slug",
                "package_name",
                "project_lane",
                "lane",
                "family_id",
                "household_id",
                "status",
                "workflow_state",
                "build_status",
                "mint_status",
            ),
        ),
        "entitlement": _safe_document(
            entitlement,
            (
                "project_id",
                "user_id",
                "package_code",
                "package_name",
                "package_lane",
                "status",
                "active_addons",
                "maintenance_plan",
                "maintenance_status",
            ),
        ),
        "order": _safe_document(
            order,
            (
                "project_id",
                "user_id",
                "status",
                "source",
                "package_code",
                "package_name",
                "package_lane",
                "fulfillment_status",
            ),
        ),
        "mint_record": _safe_document(
            mint_record,
            (
                "project_id",
                "status",
                "canonical_status",
                "version_number",
                "token_id",
                "chain",
                "contract_address",
                "tx_hash",
            ),
        ),
        "membership_count": _count(db["project_members"], {"project_id": {"$in": project_refs}, "status": "active"}),
    }


def build_project_continuity_snapshot(project_id: str) -> dict[str, Any]:
    """Build the canonical admin-safe read model across the Kernel domains."""
    project_id = _require_text(project_id, "project_id")
    db = get_database()
    operational = _project_operational_snapshot(project_id)
    project = _find_by_id(db["projects"], project_id) or {}
    project_refs = _id_candidates(project_id)
    family_id = _normalize(project.get("family_id"))
    household_id = _normalize(project.get("household_id"))
    family_refs = _id_candidates(family_id)
    owner_id = _normalize(project.get("owner_user_id") or project.get("user_id"))
    owner_email = _normalize(project.get("owner_email")).lower()

    owner_query: dict[str, Any]
    if owner_id and owner_email:
        owner_query = {"$or": [{"_id": {"$in": _id_candidates(owner_id)}}, {"email": owner_email}]}
    elif owner_id:
        owner_query = {"_id": {"$in": _id_candidates(owner_id)}}
    else:
        owner_query = {"email": owner_email}
    owner = db["users"].find_one(owner_query) if owner_id or owner_email else None

    entitlement = operational.get("entitlement") or {}
    order = operational.get("order") or {}
    package_code = _normalize(
        entitlement.get("package_code") or project.get("package_code") or project.get("package_slug")
    )
    order_status = _normalize(order.get("status")).lower()
    entitlement_status = _normalize(entitlement.get("status")).lower()

    upload_count = _count(db["uploads"], {"project_id": {"$in": project_refs}})
    upload_count += _count(db["uploaded_files"], {"project_id": {"$in": project_refs}})
    verification_count = _count(db["verification_records"], {"project_id": {"$in": project_refs}})
    lineage_member_count = _count(db["family_members"], {"family_id": {"$in": family_refs}}) if family_refs else 0
    relationship_count = _count(db["relationships"], {"family_id": {"$in": family_refs}}) if family_refs else 0
    certificate = db["issued_certificates"].find_one(
        {"project_id": {"$in": project_refs}}, sort=[("version_number", -1), ("issued_at", -1)]
    )
    audit_count = _count(db["audit_logs"], {"target_id": project_id})

    required_gates = {
        "identity_resolved": owner is not None,
        "paid_order_present": order_status in {"paid", "complete", "completed", "succeeded", "active"},
        "active_entitlement_present": bool(entitlement) and entitlement_status in {"active", "delivered"},
        "workspace_membership_valid": int(operational.get("membership_count") or 0) > 0,
        "lineage_root_present": bool(family_id),
        "package_identity_resolved": bool(package_code),
    }
    reason_codes = [f"{name.upper()}_MISSING" for name, passed in required_gates.items() if not passed]

    return {
        "kernel_version": RUNTIME_VERSION,
        "project_id": project_id,
        "overall_status": "ready" if not reason_codes else "blocked",
        "reason_codes": reason_codes,
        "components": {
            "identity_resolver": {
                "resolved": owner is not None,
                "owner_user_id": owner_id or None,
                "owner_email": owner_email or None,
            },
            "entitlement_graph_resolver": {
                "package_code": package_code or None,
                "status": entitlement_status or None,
                "active_addons": list(entitlement.get("active_addons") or []),
            },
            "workspace_access_resolver": {
                "active_membership_count": int(operational.get("membership_count") or 0),
                "family_id": family_id or None,
                "household_id": household_id or None,
            },
            "lineage_event_ledger": {
                "family_member_count": lineage_member_count,
                "relationship_count": relationship_count,
                "kernel_event_count": _count(_events_collection(), {"target_id": project_id}),
            },
            "viewer_manifest_compiler": {
                "workspace_anchor_present": bool(family_id or household_id),
                "source_upload_count": upload_count,
                "verification_record_count": verification_count,
            },
            "readiness_gate_matrix": required_gates,
            "certificate_delivery_record": {
                "latest": _safe_document(
                    certificate,
                    ("project_id", "family_id", "version_number", "status", "issued_at", "integrity_hash"),
                )
            },
            "mint_readiness_controller": operational.get("mint_record"),
            "officer_policy_layer": {"governed_actions": len(ACTION_SPECS)},
            "self_healing_repair_engine": {
                "enabled": execution_enabled(),
                "open_operations": _count(
                    _operations_collection(),
                    {"target.target_id": project_id, "state": {"$nin": ["audit_closed", "rejected"]}},
                ),
            },
            "audit_timeline": {"project_audit_event_count": audit_count},
        },
        "operational_snapshot": operational,
    }


def _bulk_snapshot() -> dict[str, Any]:
    db = get_database()
    return {
        "projects": _count(db["projects"], {}),
        "orders": _count(db["orders"], {}),
        "project_entitlements": _count(db["project_entitlements"], {}),
        "project_members": _count(db["project_members"], {}),
        "mint_records": _count(db["mint_records"], {}),
    }


def _snapshot_for_action(action: str, target: dict[str, Any]) -> dict[str, Any]:
    project_id = _normalize(target.get("project_id"))
    case_id = _normalize(target.get("case_id"))
    if not project_id and case_id and not case_id.startswith(("order:", "user:")):
        project_id = case_id
    if project_id:
        try:
            return _project_operational_snapshot(project_id)
        except ValueError:
            return {"target": target, "snapshot_status": "project_not_resolved"}
    db = get_database()
    identity_email = _normalize(target.get("identity_email")).lower()
    if identity_email:
        email_sha256 = hashlib.sha256(identity_email.encode("utf-8")).hexdigest()
        return {
            "identity_document_present": bool(
                db["users"].find_one({"email": identity_email})
            ),
            "reconciliation_evidence": _safe_document(
                db[admin_control_service.ACCOUNT_DELETION_TOMBSTONES_COLLECTION].find_one(
                    {"original_email_sha256": email_sha256}
                ),
                (
                    "reconciliation_id",
                    "status",
                    "phase",
                    "evidence_type",
                    "governed_deletion_observed",
                    "completed_at",
                ),
            ),
        }
    user_id = _normalize(target.get("user_id"))
    customer_email = _normalize(target.get("customer_email")).lower()
    if user_id:
        user = _find_by_id(db["users"], user_id)
        return {
            "user": _safe_document(
                user,
                (
                    "email",
                    "full_name",
                    "role",
                    "access_tier",
                    "department_role",
                    "status",
                    "mfa_enabled",
                    "session_token_version",
                ),
            )
        }
    if customer_email:
        user = db["users"].find_one({"email": customer_email})
        return {
            "user": _safe_document(
                user,
                ("email", "full_name", "role", "status", "mfa_enabled"),
            ),
            "customer_email": customer_email,
        }
    order_id = _normalize(target.get("order_id"))
    if order_id:
        order = _find_by_id(db["orders"], order_id)
        return {
            "order": _safe_document(
                order,
                (
                    "status",
                    "payment_status",
                    "payment_verified",
                    "fulfillment_status",
                    "project_id",
                    "package_code",
                    "package_name",
                ),
            )
        }
    session_id = _normalize(target.get("session_id"))
    if session_id:
        session = db["admin_impersonation_sessions"].find_one({"session_id": session_id})
        return {
            "impersonation_session": _safe_document(
                session,
                ("session_id", "status", "case_id", "project_id", "editing_enabled", "expires_at"),
            )
        }
    upload_id = _normalize(target.get("upload_id"))
    if upload_id:
        upload = _find_by_id(db["uploaded_files"], upload_id)
        return {
            "upload": _safe_document(
                upload,
                (
                    "category",
                    "project_id",
                    "family_id",
                    "member_id",
                    "scan_status",
                    "quarantined",
                    "consent_attested",
                    "authority_attested",
                    "verification_status",
                    "master_review_status",
                    "approved_for_cinematic",
                    "storage_provider",
                    "storage_promotion_status",
                ),
            )
        }
    if ACTION_SPECS[action].target_type == "bulk_repair":
        return _bulk_snapshot()
    return {"target": target}


def _preview_action(action: str, target: dict[str, Any], parameters: dict[str, Any]) -> dict[str, Any]:
    if action in {"upload_rescan", "portrait_review", "evidence_review"}:
        from app.routes import uploads as upload_routes

        return upload_routes.preview_admin_upload_action(
            upload_id=_normalize(target.get("upload_id")),
            action=action,
            decision=_normalize(parameters.get("decision")),
        )
    if action == "package_change":
        return admin_control_service.super_admin_preview_package_change(
            project_id=_normalize(target.get("project_id")),
            package_code=_normalize(parameters.get("package_code")),
            project_lane=_normalize(parameters.get("project_lane")),
            order_status=_normalize(parameters.get("order_status")),
        )
    if action == "package_revoke":
        return admin_control_service.super_admin_preview_package_revocation(
            project_id=_normalize(target.get("project_id"))
        )
    if action == "service_controls":
        return admin_control_service.super_admin_preview_service_controls(
            project_id=_normalize(target.get("project_id")), payload=parameters
        )
    if action == "officer_permissions":
        return admin_control_service.super_admin_preview_officer_permissions(
            officer_email=_normalize(target.get("officer_email")),
            role_assignments=list(parameters.get("role_assignments") or []),
            grant_permissions=list(parameters.get("grant_permissions") or []),
            revoke_permissions=list(parameters.get("revoke_permissions") or []),
        )
    if action == "account_lifecycle":
        return admin_control_service.super_admin_preview_account_lifecycle(
            user_id=_normalize(target.get("user_id")),
            action=_normalize(parameters.get("lifecycle_action")),
            archive_owned_records=bool(parameters.get("archive_owned_records")),
        )
    if action == "account_permanent_delete":
        return admin_control_service.super_admin_preview_account_permanent_deletion(
            user_id=_normalize(target.get("user_id")),
            reason_category=_normalize(parameters.get("reason_category")),
        )
    if action == "orphan_identity_reconciliation":
        return admin_control_service.super_admin_preview_orphan_identity_reconciliation(
            identity_email=_normalize(target.get("identity_email")),
            known_user_id=_normalize(parameters.get("known_user_id")),
            reason_category=_normalize(parameters.get("reason_category")),
        )
    if action == "customer_account_create":
        return admin_control_service.super_admin_preview_customer_create(
            payload=dict(parameters.get("user_payload") or parameters)
        )
    if action == "customer_package_provision":
        return admin_control_service.super_admin_preview_customer_package_provision(
            user_id=_normalize(target.get("user_id")),
            payload=dict(parameters),
        )
    if action == "legacy_admin_remediation":
        review = admin_control_service.legacy_admin_security_review()
        if not review.get("found"):
            return {
                **review,
                "blocked": True,
                "warnings": ["The legacy privileged account no longer exists."],
            }
        if _normalize(review.get("user_id")) != _normalize(target.get("user_id")):
            raise ValueError("Legacy administrator remediation target does not match the reviewed identity.")
        return {
            **review,
            "blocked": not bool(review.get("safe_to_suspend")),
            "warnings": (
                []
                if review.get("safe_to_suspend")
                else ["Legacy administrator remediation requires manual dependency review."]
            ),
        }
    return {
        "action": action,
        "target": target,
        "parameters": parameters,
        "preview_type": "governed_execution_plan",
    }


def _enrich_before_snapshot(before_snapshot: dict[str, Any], preview: dict[str, Any]) -> dict[str, Any]:
    action_before = preview.get("before")
    if action_before is None and preview.get("current_package") is not None:
        action_before = {"current_package": preview.get("current_package")}
    if action_before is None:
        return before_snapshot
    return {
        "operational_snapshot": before_snapshot,
        "action_before": _serialize(action_before),
    }


def _preview_blocked_reasons(preview: dict[str, Any]) -> list[str]:
    if preview.get("blocked") is True:
        return ["ACTION_PREVIEW_BLOCKED"]
    validation = preview.get("validation")
    if isinstance(validation, dict) and validation.get("blocked") is True:
        return ["ACTION_PREVIEW_BLOCKED"]
    return []


def _idempotency_payload_matches(
    existing: dict[str, Any],
    *,
    action: str,
    target: dict[str, Any],
    parameters: dict[str, Any],
) -> bool:
    return (
        _normalize(existing.get("action")) == action
        and _serialize(existing.get("target")) == target
        and _serialize(existing.get("parameters")) == parameters
    )


def _operation_audit_context(operation: dict[str, Any]) -> dict[str, Any]:
    return {
        "continuity_runtime_version": RUNTIME_VERSION,
        "operation_id": operation.get("operation_id"),
        "evidence_packet_id": operation.get("evidence_packet_id"),
        "idempotency_key": operation.get("idempotency_key"),
        "repair_category": operation.get("repair_category"),
        "risk_level": operation.get("risk_level"),
    }


def _evidence_attempt(operation: dict[str, Any]) -> int:
    return int(operation.get("execution_retry_count") or 0)


def _write_audit(
    *,
    operation: dict[str, Any],
    actor: dict[str, Any] | None,
    action: str,
    result: str,
    before: Any = None,
    after: Any = None,
) -> None:
    operation_id = _normalize(operation.get("operation_id"))
    audit_idempotency_key = (
        f"continuity:{operation_id}:{action}:{_evidence_attempt(operation)}"
    )
    write_audit_log(
        actor_user_id=_actor_id(actor) or None,
        actor_email=_actor_email(actor) or None,
        actor_name=_actor_name(actor) or None,
        action=f"continuity_runtime.{action}",
        target_type=_normalize(operation.get("target_type")) or "continuity_operation",
        target_id=_normalize(operation.get("target_id")) or operation_id,
        before=_serialize(before) if isinstance(before, dict) else {},
        after=_serialize(after) if isinstance(after, dict) else {},
        context=_operation_audit_context(operation),
        result=result,
        idempotency_key=audit_idempotency_key,
    )


def _record_event(
    operation: dict[str, Any],
    *,
    event_type: str,
    actor: dict[str, Any] | None,
    details: dict[str, Any] | None = None,
) -> None:
    operation_id = _normalize(operation.get("operation_id"))
    event_identity = (
        f"{operation_id}:{event_type}:{_evidence_attempt(operation)}"
    )
    event_id = (
        "ckevt_"
        + hashlib.sha256(event_identity.encode("utf-8")).hexdigest()[:32]
    )
    events = _events_collection()
    if events.find_one({"event_id": event_id}) is not None:
        return
    event = {
        "event_id": event_id,
        "operation_id": operation_id,
        "event_type": event_type,
        "state": operation.get("state"),
        "target_type": operation.get("target_type"),
        "target_id": operation.get("target_id"),
        "repair_category": operation.get("repair_category"),
        "actor": _actor_snapshot(actor),
        "details": _serialize(details or {}),
        "created_at": _now(),
    }
    try:
        events.insert_one(event)
    except DuplicateKeyError:
        # A prior attempt committed the same deterministic event but failed
        # before the operation checkpoint could be updated.
        return


def _record_stage_evidence(
    operation: dict[str, Any],
    *,
    stage: str,
    event_type: str,
    actor: dict[str, Any] | None,
    audit_action: str,
    audit_result: str,
    details: dict[str, Any] | None = None,
    before: Any = None,
    after: Any = None,
) -> dict[str, Any]:
    status_field = f"{stage}_evidence_status"
    errors_field = f"{stage}_evidence_errors"
    if _normalize(operation.get(status_field)) == "complete":
        return operation

    errors: list[str] = []
    try:
        _record_event(
            operation,
            event_type=event_type,
            actor=actor,
            details=details,
        )
    except Exception as exc:
        errors.append(
            f"continuity_event:{_normalize(exc) or exc.__class__.__name__}"
        )
    try:
        _write_audit(
            operation=operation,
            actor=actor,
            action=audit_action,
            result=audit_result,
            before=before,
            after=after,
        )
    except Exception as exc:
        errors.append(f"audit_log:{_normalize(exc) or exc.__class__.__name__}")

    status_value = "incomplete" if errors else "complete"
    _operations_collection().update_one(
        {"operation_id": operation.get("operation_id")},
        {
            "$set": {
                status_field: status_value,
                errors_field: errors,
                "updated_at": _now(),
            }
        },
    )
    updated = _get_operation_document(_normalize(operation.get("operation_id")))
    if errors:
        raise RuntimeError(
            f"Continuity {stage} evidence is incomplete; retry the same "
            "idempotent operation to resume evidence recording: "
            + ", ".join(errors)
        )
    return updated


def _serialize_operation(document: dict[str, Any] | None) -> dict[str, Any] | None:
    if not document:
        return None
    payload = _serialize(document)
    payload["id"] = payload.pop("_id", None)
    return payload


def _get_operation_document(operation_id: str) -> dict[str, Any]:
    operation_id = _require_text(operation_id, "operation_id")
    document = _operations_collection().find_one({"operation_id": operation_id})
    if document is None:
        raise ValueError("Continuity operation not found.")
    return document


def _transition(
    operation_id: str,
    *,
    expected_state: str,
    next_state: str,
    actor: dict[str, Any] | None,
    action: str,
    reason_codes: list[str] | None = None,
    extra_set: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = _now()
    transition = {
        "previous_state": expected_state,
        "next_state": next_state,
        "actor": _actor_snapshot(actor),
        "action": action,
        "reason_codes": list(reason_codes or []),
        "timestamp": now,
    }
    updates: dict[str, Any] = {"state": next_state, "updated_at": now, **(extra_set or {})}
    result = _operations_collection().update_one(
        {"operation_id": operation_id, "state": expected_state},
        {"$set": updates, "$push": {"transitions": transition}},
    )
    if int(getattr(result, "matched_count", 0)) != 1:
        current = _get_operation_document(operation_id)
        if _normalize(current.get("state")) == next_state:
            return current
        raise RuntimeError(
            f"Continuity operation state changed concurrently; expected {expected_state}, found {current.get('state')}."
        )
    return _get_operation_document(operation_id)


def request_operation(
    *,
    action: str,
    target: dict[str, Any],
    parameters: dict[str, Any] | None,
    reason: str,
    idempotency_key: str,
    actor: dict[str, Any] | None,
) -> dict[str, Any]:
    if not execution_enabled():
        raise RuntimeError("Continuity execution is disabled by the emergency kill switch.")

    normalized_action = _normalize_action(action)
    spec = ACTION_SPECS.get(normalized_action)
    if spec is None:
        raise ValueError("Unsupported Continuity Kernel action.")
    actor_snapshot = _actor_snapshot(actor)
    if not actor_snapshot["actor_user_id"]:
        raise PermissionError("Authenticated actor id is required.")
    if not actor_snapshot["actor_role"]:
        raise PermissionError("Authenticated actor role is not recognized.")
    _assert_action_actor_scope(normalized_action, actor)

    reason_value = _require_text(reason, "reason", minimum=3)
    idempotency_value = _require_text(idempotency_key, "idempotency_key", minimum=8)
    clean_target = _validate_target(spec, normalized_action, target)
    # The Kernel's idempotency key is authoritative all the way down to
    # downstream providers. A caller cannot substitute a different key in the
    # free-form parameters payload.
    clean_parameters = _serialize(
        {
            **(parameters or {}),
            "reason": reason_value,
            "continuity_idempotency_key": idempotency_value,
        }
    )
    if normalized_action == "account_permanent_delete":
        _require_permanent_deletion_confirmations(clean_parameters)
    if normalized_action == "orphan_identity_reconciliation":
        _require_orphan_reconciliation_confirmations(clean_parameters)

    existing = _operations_collection().find_one({"idempotency_key": idempotency_value})
    if existing is not None:
        if not _idempotency_payload_matches(
            existing,
            action=normalized_action,
            target=clean_target,
            parameters=clean_parameters,
        ):
            raise ValueError("Idempotency key is already bound to a different Continuity operation.")
        existing = _record_stage_evidence(
            existing,
            stage="request",
            event_type="operation_requested",
            actor=actor,
            audit_action="operation_requested",
            audit_result="success",
            details={"reason": existing.get("reason")},
            before=existing.get("before_snapshot"),
            after=existing.get("proposed_after_snapshot"),
        )
        return _serialize_operation(existing) or {}

    before_snapshot = _snapshot_for_action(normalized_action, clean_target)
    proposed_after_snapshot = _preview_action(normalized_action, clean_target, clean_parameters)
    before_snapshot = _enrich_before_snapshot(before_snapshot, proposed_after_snapshot)
    blocked_reasons = _preview_blocked_reasons(proposed_after_snapshot)
    operation_id = f"ckop_{uuid4().hex}"
    now = _now()
    target_id = _normalize(clean_target.get("target_id"))
    rollback_plan = {
        "strategy": "restore_from_before_snapshot",
        "before_snapshot_ref": f"operation:{operation_id}:before_snapshot",
        "automatic": False,
        "requires_explicit_rollback_authorization": True,
    }
    if normalized_action == "account_permanent_delete":
        rollback_plan = {
            "strategy": "irreversible_identity_erasure",
            "before_snapshot_ref": f"operation:{operation_id}:before_snapshot",
            "automatic": False,
            "restoration_prohibited": True,
            "evidence_only": True,
        }
    if normalized_action == "orphan_identity_reconciliation":
        rollback_plan = {
            "strategy": "post_hoc_manual_removal_evidence_and_access_closure",
            "before_snapshot_ref": f"operation:{operation_id}:before_snapshot",
            "automatic": False,
            "restoration_prohibited": True,
            "evidence_only": True,
        }
    operation = {
        "operation_id": operation_id,
        "evidence_packet_id": f"ckevidence_{uuid4().hex}",
        "runtime_version": RUNTIME_VERSION,
        "action": normalized_action,
        "repair_category": spec.repair_category,
        "risk_level": spec.risk_level,
        "mutates_business_data": spec.mutates_business_data,
        "target_type": spec.target_type,
        "target_id": target_id,
        "target": clean_target,
        "parameters": clean_parameters,
        "reason": reason_value,
        "idempotency_key": idempotency_value,
        "state": "review_requested",
        "request_evidence_status": "pending",
        "request_evidence_errors": [],
        "requested_by": actor_snapshot,
        "approved_by": None,
        "executed_by": None,
        "before_snapshot": _serialize(before_snapshot),
        "proposed_after_snapshot": _serialize(proposed_after_snapshot),
        "rollback_plan": rollback_plan,
        "blocked_reasons": blocked_reasons,
        "transitions": [
            {
                "previous_state": "dry_run_created",
                "next_state": "review_requested",
                "actor": actor_snapshot,
                "action": "request_review",
                "reason_codes": [],
                "timestamp": now,
            }
        ],
        "created_at": now,
        "updated_at": now,
    }
    try:
        _operations_collection().insert_one(operation)
    except DuplicateKeyError:
        existing = _operations_collection().find_one({"idempotency_key": idempotency_value})
        if existing is not None:
            if not _idempotency_payload_matches(
                existing,
                action=normalized_action,
                target=clean_target,
                parameters=clean_parameters,
            ):
                raise ValueError("Idempotency key is already bound to a different Continuity operation.")
            existing = _record_stage_evidence(
                existing,
                stage="request",
                event_type="operation_requested",
                actor=actor,
                audit_action="operation_requested",
                audit_result="success",
                details={"reason": existing.get("reason")},
                before=existing.get("before_snapshot"),
                after=existing.get("proposed_after_snapshot"),
            )
            return _serialize_operation(existing) or {}
        raise

    operation = _record_stage_evidence(
        operation,
        stage="request",
        event_type="operation_requested",
        actor=actor,
        audit_action="operation_requested",
        audit_result="success",
        details={"reason": reason_value},
        before=before_snapshot,
        after=proposed_after_snapshot,
    )
    return _serialize_operation(operation) or {}


def _structured_override(operation: dict[str, Any], actor: dict[str, Any], reason: str) -> dict[str, Any]:
    actor_id = _actor_id(actor)
    return {
        "override_id": f"ckoverride_{uuid4().hex}",
        "override_type": "SUPERADMIN_EMERGENCY_OVERRIDE",
        "requested_by": _normalize((operation.get("requested_by") or {}).get("actor_user_id")),
        "approved_by": actor_id,
        "approval_role": "SUPERADMIN",
        "reason_code": "SOLO_FOUNDER_OWNER_OPERATED_EXECUTION",
        "reason_detail": reason,
        "target_type": operation.get("target_type"),
        "target_id": operation.get("target_id"),
        "repair_category": operation.get("repair_category"),
        "risk_level": operation.get("risk_level"),
        "expires_at": (_now() + timedelta(minutes=30)).isoformat(),
        "audit_context": {
            "operation_id": operation.get("operation_id"),
            "governance_posture": "solo_founder_owner_operated",
        },
    }


def approve_operation(
    operation_id: str,
    *,
    approval_reason: str,
    actor: dict[str, Any] | None,
    solo_founder_override_acknowledged: bool = False,
) -> dict[str, Any]:
    operation = _get_operation_document(operation_id)
    if operation.get("state") in {"approved_for_apply", "apply_scheduled", "apply_executed", "audit_closed"}:
        operation = _record_stage_evidence(
            operation,
            stage="approval",
            event_type="operation_approved",
            actor=actor,
            audit_action="operation_approved",
            audit_result="success",
            details={"approval_reason": operation.get("approval_reason")},
        )
        return _serialize_operation(operation) or {}
    if operation.get("state") != "review_requested":
        raise ValueError("Operation must be in review_requested state before approval.")
    if operation.get("blocked_reasons"):
        raise ValueError(
            "Operation cannot be approved while preflight blockers remain: "
            + ", ".join(str(reason) for reason in operation.get("blocked_reasons") or [])
        )

    action = _normalize(operation.get("action"))
    _assert_action_actor_scope(action, actor)
    spec = ACTION_SPECS[action]
    role = _assert_action_allowed_for_actor(spec, actor)
    reason_value = _require_text(approval_reason, "approval_reason", minimum=3)
    requester_id = _normalize((operation.get("requested_by") or {}).get("actor_user_id"))
    approver_id = _actor_id(actor)
    structured_override = None
    if operation.get("risk_level") == "high" and requester_id == approver_id:
        if role != "SUPERADMIN" or not solo_founder_override_acknowledged:
            raise PermissionError(
                "High-risk same-requester approval requires SUPERADMIN and explicit solo-founder override acknowledgement."
            )
        structured_override = _structured_override(operation, actor or {}, reason_value)

    operation = _transition(
        operation_id,
        expected_state="review_requested",
        next_state="officer_reviewing",
        actor=actor,
        action="begin_officer_review",
    )
    approved_at = _now()
    operation = _transition(
        operation_id,
        expected_state="officer_reviewing",
        next_state="approved_for_apply",
        actor=actor,
        action="approve_for_apply",
        reason_codes=["SOLO_FOUNDER_OVERRIDE" if structured_override else "OFFICER_APPROVAL"],
        extra_set={
            "approved_by": _actor_snapshot(actor),
            "approval_role": role,
            "approval_reason": reason_value,
            "approved_at": approved_at,
            "structured_override": structured_override,
            "approval_evidence_status": "pending",
            "approval_evidence_errors": [],
        },
    )
    operation = _record_stage_evidence(
        operation,
        stage="approval",
        event_type="operation_approved",
        actor=actor,
        audit_action="operation_approved",
        audit_result="success",
        details={"approval_reason": reason_value},
    )
    return _serialize_operation(operation) or {}


def reject_operation(operation_id: str, *, rejection_reason: str, actor: dict[str, Any] | None) -> dict[str, Any]:
    operation = _get_operation_document(operation_id)
    if operation.get("state") == "rejected":
        operation = _record_stage_evidence(
            operation,
            stage="rejection",
            event_type="operation_rejected",
            actor=actor,
            audit_action="operation_rejected",
            audit_result="success",
            details={"rejection_reason": operation.get("rejection_reason")},
        )
        return _serialize_operation(operation) or {}
    if operation.get("state") not in {"review_requested", "officer_reviewing"}:
        raise ValueError("Only an operation under review can be rejected.")
    action = _normalize(operation.get("action"))
    _assert_action_actor_scope(action, actor)
    spec = ACTION_SPECS[action]
    _assert_action_allowed_for_actor(spec, actor)
    reason = _require_text(rejection_reason, "rejection_reason", minimum=3)
    expected = _normalize(operation.get("state"))
    if expected == "review_requested":
        operation = _transition(
            operation_id,
            expected_state="review_requested",
            next_state="officer_reviewing",
            actor=actor,
            action="begin_officer_review",
        )
        expected = "officer_reviewing"
    operation = _transition(
        operation_id,
        expected_state=expected,
        next_state="rejected",
        actor=actor,
        action="reject_operation",
        reason_codes=["OFFICER_REJECTED"],
        extra_set={
            "rejection_reason": reason,
            "rejected_at": _now(),
            "rejection_evidence_status": "pending",
            "rejection_evidence_errors": [],
        },
    )
    operation = _record_stage_evidence(
        operation,
        stage="rejection",
        event_type="operation_rejected",
        actor=actor,
        audit_action="operation_rejected",
        audit_result="success",
        details={"rejection_reason": reason},
    )
    return _serialize_operation(operation) or {}


def _evidence_packet(operation: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
    requested_by = _normalize((operation.get("requested_by") or {}).get("actor_user_id"))
    approved_by = _normalize((operation.get("approved_by") or {}).get("actor_user_id"))
    executed_by = _actor_id(actor)
    packet = {
        "dry_run_id": operation.get("operation_id"),
        "evidence_packet_id": operation.get("evidence_packet_id"),
        "actor_user_id": requested_by,
        "requested_by": requested_by,
        "reviewed_by": approved_by,
        "approved_by": approved_by,
        "executed_by": executed_by,
        "approval_role": operation.get("approval_role"),
        "target_type": operation.get("target_type"),
        "target_id": operation.get("target_id"),
        "repair_category": operation.get("repair_category"),
        "before_snapshot": operation.get("before_snapshot") or {},
        "proposed_after_snapshot": operation.get("proposed_after_snapshot") or {},
        "diff_summary": {
            "action": operation.get("action"),
            "reason": operation.get("reason"),
            "mutates_business_data": operation.get("mutates_business_data"),
        },
        "blocked_reasons": operation.get("blocked_reasons") or [],
        "risk_level": operation.get("risk_level"),
        "rollback_plan": operation.get("rollback_plan") or {},
        "idempotency_key": operation.get("idempotency_key"),
        "created_at": _serialize(operation.get("created_at")),
        "approved_at": _serialize(operation.get("approved_at")),
        "executed_at": _now_iso(),
        "audit_context": _operation_audit_context(operation),
    }
    if operation.get("structured_override"):
        packet["structured_override"] = operation.get("structured_override")
    return packet


def _authorization_decision(operation: dict[str, Any]) -> dict[str, Any]:
    approved_by = operation.get("approved_by") or {}
    decision = {
        "actor_user_id": approved_by.get("actor_user_id"),
        "actor_role": operation.get("approval_role"),
        "requested_action": operation.get("action"),
        "repair_category": operation.get("repair_category"),
        "target_type": operation.get("target_type"),
        "target_id": operation.get("target_id"),
        "decision": "approved_for_apply",
        "reason_codes": ["OFFICER_APPROVED"],
        "policy_source": f"continuity_runtime_v{RUNTIME_VERSION}",
        "evaluated_at": _now_iso(),
    }
    if operation.get("structured_override"):
        decision["structured_override"] = operation.get("structured_override")
    return decision


def _scheduled_transition(operation: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_packet_id": operation.get("evidence_packet_id"),
        "previous_state": "approved_for_apply",
        "next_state": "apply_scheduled",
        "actor_user_id": _actor_id(actor),
        "action": "schedule_approved_operation",
        "transition_allowed": True,
        "reason_codes": ["VALIDATED_FOR_EXECUTION"],
        "timestamp": _now_iso(),
        "audit_context": _operation_audit_context(operation),
    }


def _rollback_verification(operation: dict[str, Any]) -> dict[str, Any]:
    rollback_plan = dict(operation.get("rollback_plan") or {})
    irreversible = _normalize(operation.get("action")) == "account_permanent_delete"
    return {
        "evidence_packet_id": operation.get("evidence_packet_id"),
        "rollback_plan": rollback_plan,
        "before_snapshot_ref": rollback_plan.get("before_snapshot_ref"),
        "target_type": operation.get("target_type"),
        "target_id": operation.get("target_id"),
        "verification_status": (
            "irreversible_evidence_reference_verified"
            if irreversible
            else "before_snapshot_reference_verified"
        ),
        "reason_codes": (
            ["BEFORE_SNAPSHOT_CAPTURED", "IRREVERSIBLE_ACTION_EVIDENCE_ONLY"]
            if irreversible
            else ["BEFORE_SNAPSHOT_CAPTURED", "MANUAL_ROLLBACK_AUTHORIZATION_REQUIRED"]
        ),
        "verified_at": _now_iso(),
        "audit_context": _operation_audit_context(operation),
    }


def _execution_failure_count(result: Any) -> int:
    if not isinstance(result, dict):
        return 0
    failure_count = result.get("failure_count")
    if isinstance(failure_count, (int, float)) and not isinstance(failure_count, bool):
        return max(0, int(failure_count))
    failed_count = result.get("failed_count")
    if isinstance(failed_count, (int, float)) and not isinstance(failed_count, bool):
        return max(0, int(failed_count))
    failed = result.get("failed")
    if isinstance(failed, (int, float)) and not isinstance(failed, bool):
        return max(0, int(failed))
    if isinstance(failed, list):
        return len(failed)
    return 0


def _invoke_stripe_operation(
    *,
    stripe_action: str,
    parameters: dict[str, Any],
    actor: dict[str, Any] | None,
) -> dict[str, Any]:
    action = _normalize(stripe_action).lower()
    reason = _normalize(parameters.get("reason"))
    idempotency_key = _normalize(parameters.get("continuity_idempotency_key"))
    common = {"admin_user": actor or {}, "reason": reason, "idempotency_key": idempotency_key}
    if action == "ensure_customer":
        return stripe_admin_operations_service.ensure_customer(
            **common,
            customer_email=_normalize(parameters.get("customer_email")),
        )
    if action == "payment_link":
        return stripe_admin_operations_service.create_payment_link(
            **common,
            price_id=_normalize(parameters.get("price_id")),
            quantity=max(1, int(parameters.get("quantity") or 1)),
        )
    if action == "invoice":
        return stripe_admin_operations_service.create_and_send_invoice(
            **common,
            customer_email=_normalize(parameters.get("customer_email")),
            amount_cents=int(parameters.get("amount_cents") or 0),
            description=_normalize(parameters.get("description")),
            days_until_due=max(1, int(parameters.get("days_until_due") or 7)),
        )
    if action == "invoice_retry":
        return stripe_admin_operations_service.retry_invoice_payment(
            **common,
            invoice_id=_normalize(parameters.get("invoice_id")),
        )
    if action == "subscription_create":
        return stripe_admin_operations_service.create_subscription(
            **common,
            customer_email=_normalize(parameters.get("customer_email")),
            price_id=_normalize(parameters.get("price_id")),
        )
    if action == "subscription_change":
        return stripe_admin_operations_service.change_subscription_price(
            **common,
            subscription_id=_normalize(parameters.get("subscription_id")),
            price_id=_normalize(parameters.get("price_id")),
        )
    if action == "subscription_pause":
        return stripe_admin_operations_service.pause_subscription(
            **common,
            subscription_id=_normalize(parameters.get("subscription_id")),
        )
    if action == "subscription_resume":
        return stripe_admin_operations_service.resume_subscription(
            **common,
            subscription_id=_normalize(parameters.get("subscription_id")),
        )
    if action == "subscription_cancel":
        return stripe_admin_operations_service.cancel_subscription(
            **common,
            subscription_id=_normalize(parameters.get("subscription_id")),
            at_period_end=bool(parameters.get("at_period_end", True)),
            confirm=bool(parameters.get("confirm")),
        )
    if action == "payment_method_link":
        return stripe_admin_operations_service.send_payment_method_update_link(
            **common,
            customer_email=_normalize(parameters.get("customer_email")),
        )
    raise ValueError("Unsupported governed Stripe operation.")


def _record_post_execution_evidence(
    operation: dict[str, Any],
    *,
    actor: dict[str, Any] | None,
    execution_result: dict[str, Any],
    after_snapshot: dict[str, Any],
    execution_outcome: str,
    failure_count: int,
) -> dict[str, Any]:
    evidence_errors: list[str] = []
    try:
        _record_event(
            operation,
            event_type="operation_executed",
            actor=actor,
            details={
                "result": execution_result,
                "execution_outcome": execution_outcome,
                "execution_failure_count": failure_count,
            },
        )
    except Exception as exc:
        evidence_errors.append(f"continuity_event:{_normalize(exc) or exc.__class__.__name__}")
    try:
        _write_audit(
            operation=operation,
            actor=actor,
            action="operation_executed",
            result=execution_outcome,
            before=operation.get("before_snapshot"),
            after=after_snapshot,
        )
    except Exception as exc:
        evidence_errors.append(f"audit_log:{_normalize(exc) or exc.__class__.__name__}")

    evidence_status = "incomplete" if evidence_errors else "complete"
    try:
        _operations_collection().update_one(
            {"operation_id": operation.get("operation_id"), "state": "apply_executed"},
            {
                "$set": {
                    "evidence_recording_status": evidence_status,
                    "evidence_recording_errors": evidence_errors,
                    "updated_at": _now(),
                }
            },
        )
        return _get_operation_document(_normalize(operation.get("operation_id")))
    except Exception:
        fallback = dict(operation)
        fallback["evidence_recording_status"] = evidence_status
        fallback["evidence_recording_errors"] = evidence_errors
        return fallback


def _invoke_action(
    action: str, target: dict[str, Any], parameters: dict[str, Any], actor: dict[str, Any] | None
) -> dict[str, Any]:
    if action in CASE_ACTION_SPECS:
        return admin_control_service.execute_case_action(
            case_id=_normalize(target.get("case_id")), action=action, actor=actor
        )

    reason = _normalize(parameters.get("reason"))
    if action == "manual_fulfillment":
        return manual_fulfillment_service.execute_fulfillment_action(
            actor or {},
            order_id=_normalize(target.get("order_id")),
            action=_normalize(parameters.get("fulfillment_action")),
            reason=reason,
            idempotency_key=_normalize(parameters.get("continuity_idempotency_key")),
        )
    if action == "stripe_operation":
        return _invoke_stripe_operation(
            stripe_action=_normalize(parameters.get("stripe_action")),
            parameters=parameters,
            actor=actor,
        )
    if action == "customer_account_create":
        payload = dict(parameters.get("user_payload") or parameters)
        payload["reason"] = reason
        return admin_control_service.super_admin_create_customer(
            payload=payload,
            actor=actor,
        )
    if action == "customer_package_provision":
        payload = dict(parameters)
        payload["reason"] = reason
        return admin_control_service.super_admin_provision_customer_package(
            user_id=_normalize(target.get("user_id")),
            payload=payload,
            actor=actor,
        )
    if action == "user_profile_update":
        return admin_control_service.super_admin_update_user(
            user_id=_normalize(target.get("user_id")),
            payload=dict(parameters.get("user_payload") or {}),
            actor=actor,
        )
    if action == "user_password_reset":
        return admin_issue_password_reset(
            _normalize(target.get("user_id")),
            admin_user_id=_actor_id(actor),
            admin_display=_actor_name(actor) or _actor_email(actor),
            admin_email=_actor_email(actor),
        )
    if action == "project_ownership_transfer":
        return admin_control_service.super_admin_transfer_project_ownership(
            project_id=_normalize(target.get("project_id")),
            new_owner_user_id=_normalize(parameters.get("new_owner_user_id")),
            reason=reason,
            actor=actor,
        )
    if action == "impersonation_start":
        return admin_control_service.start_admin_impersonation(
            case_id=_normalize(target.get("case_id")),
            reason=reason,
            actor=actor,
        )
    if action == "impersonation_stop":
        return admin_control_service.stop_admin_impersonation(
            session_id=_normalize(target.get("session_id")),
            reason=reason,
            actor=actor,
        )
    if action == "legacy_admin_remediation":
        review = admin_control_service.legacy_admin_security_review()
        if not review.get("found"):
            raise ValueError("The legacy privileged account no longer exists.")
        if _normalize(review.get("user_id")) != _normalize(target.get("user_id")):
            raise ValueError("Legacy administrator remediation target does not match the reviewed identity.")
        return admin_control_service.legacy_admin_security_review(
            apply=True,
            reason=reason,
            actor=actor,
        )
    if action == "upload_rescan":
        from app.routes import uploads as upload_routes

        return upload_routes.admin_rescan_upload(
            upload_id=_normalize(target.get("upload_id")),
            current_user=actor or {},
        )
    if action == "portrait_review":
        from app.routes import uploads as upload_routes

        decision = _normalize(parameters.get("decision")).lower()
        if decision not in {"approved", "rejected"}:
            raise ValueError("Portrait review decision must be approved or rejected.")
        return upload_routes.update_upload_cinematic_approval(
            upload_id=_normalize(target.get("upload_id")),
            payload=upload_routes.UploadCinematicApprovalPayload(
                approved_for_cinematic=decision == "approved",
                verification_status=decision,
                consent_status=decision,
                review_notes=_normalize(parameters.get("review_notes")),
            ),
            current_user=actor or {},
        )
    if action == "evidence_review":
        from app.routes import uploads as upload_routes

        return upload_routes.update_upload_verification_review(
            upload_id=_normalize(target.get("upload_id")),
            payload=upload_routes.UploadVerificationReviewPayload(
                decision=_normalize(parameters.get("decision")).lower(),
                review_notes=_normalize(parameters.get("review_notes")),
            ),
            current_user=actor or {},
        )

    limit = max(1, min(int(parameters.get("limit") or 500), admin_control_service.MAX_BULK_ACTION_LIMIT))
    if action == "repair_missing_entitlements":
        return admin_control_service.repair_missing_entitlements(limit=limit)
    if action == "assign_missing_lanes":
        return admin_control_service.assign_missing_lanes(limit=limit)
    if action == "link_unlinked_paid_orders":
        return admin_control_service.link_unlinked_paid_orders(limit=limit)
    if action == "normalize_broken_package_records":
        return admin_control_service.normalize_broken_package_records(limit=limit)
    if action == "refresh_mint_readiness":
        return admin_control_service.refresh_mint_readiness(limit=limit)
    if action == "repair_selected_records":
        return admin_control_service.repair_selected_records(
            project_ids=list(parameters.get("project_ids") or []),
            order_ids=list(parameters.get("order_ids") or []),
        )
    if action == "repair_all_safe_records":
        return admin_control_service.repair_all_safe_records(limit=limit)

    project_id = _normalize(target.get("project_id"))
    if action == "package_change":
        return admin_control_service.super_admin_apply_package_change(
            project_id=project_id,
            package_code=_normalize(parameters.get("package_code")),
            project_lane=_normalize(parameters.get("project_lane")),
            order_status=_normalize(parameters.get("order_status")),
            reason=reason,
            actor=actor,
        )
    if action == "package_revoke":
        return admin_control_service.super_admin_apply_package_revocation(
            project_id=project_id, reason=reason, actor=actor
        )
    if action == "package_restore":
        return admin_control_service.super_admin_restore_package(project_id=project_id, reason=reason, actor=actor)
    if action == "service_controls":
        payload = dict(parameters)
        payload["reason"] = reason
        payload["confirmed"] = True
        return admin_control_service.super_admin_apply_service_controls(
            project_id=project_id, payload=payload, actor=actor
        )
    if action == "officer_permissions":
        return admin_control_service.super_admin_apply_officer_permissions(
            officer_email=_normalize(target.get("officer_email")),
            role_assignments=list(parameters.get("role_assignments") or []),
            grant_permissions=list(parameters.get("grant_permissions") or []),
            revoke_permissions=list(parameters.get("revoke_permissions") or []),
            actor=actor,
        )
    if action == "account_lifecycle":
        return admin_control_service.super_admin_apply_account_lifecycle(
            user_id=_normalize(target.get("user_id")),
            action=_normalize(parameters.get("lifecycle_action")),
            reason=reason,
            archive_owned_records=bool(parameters.get("archive_owned_records")),
            actor=actor,
        )
    if action == "account_permanent_delete":
        return admin_control_service.super_admin_apply_account_permanent_deletion(
            user_id=_normalize(target.get("user_id")),
            reason_category=_normalize(parameters.get("reason_category")),
            reason=reason,
            confirmation_email=_normalize(parameters.get("confirmation_email")),
            initial_confirmation=parameters.get("initial_confirmation") is True,
            final_confirmation=_normalize(parameters.get("final_confirmation")),
            final_acknowledgement=parameters.get("final_acknowledgement") is True,
            continuity_operation_id=_normalize(parameters.get("continuity_operation_id")),
            actor=actor,
        )
    if action == "orphan_identity_reconciliation":
        return admin_control_service.super_admin_apply_orphan_identity_reconciliation(
            identity_email=_normalize(target.get("identity_email")),
            known_user_id=_normalize(parameters.get("known_user_id")),
            reason_category=_normalize(parameters.get("reason_category")),
            reason=reason,
            confirmation_email=_normalize(parameters.get("confirmation_email")),
            initial_confirmation=parameters.get("initial_confirmation") is True,
            final_confirmation=_normalize(parameters.get("final_confirmation")),
            final_acknowledgement=parameters.get("final_acknowledgement") is True,
            continuity_operation_id=_normalize(parameters.get("continuity_operation_id")),
            actor=actor,
        )
    if action == "case_repair":
        payload = dict(parameters.get("repair_payload") or parameters)
        payload["reason"] = reason
        return admin_control_service.super_admin_repair_case_action(
            case_id=_normalize(target.get("case_id")),
            action=_normalize(parameters.get("repair_action") or payload.get("action")),
            payload=payload,
            actor=actor,
        )
    raise ValueError("No executor is registered for the requested Continuity action.")


def execute_operation(operation_id: str, *, actor: dict[str, Any] | None) -> dict[str, Any]:
    if not execution_enabled():
        raise RuntimeError("Continuity execution is disabled by the emergency kill switch.")
    operation = _get_operation_document(operation_id)
    if operation.get("state") == "apply_executed":
        operation = _record_post_execution_evidence(
            operation,
            actor=actor,
            execution_result=dict(operation.get("execution_result") or {}),
            after_snapshot=dict(operation.get("after_snapshot") or {}),
            execution_outcome=_normalize(operation.get("execution_outcome")) or "success",
            failure_count=int(operation.get("execution_failure_count") or 0),
        )
        return _serialize_operation(operation) or {}
    if operation.get("state") == "audit_closed":
        operation = _record_stage_evidence(
            operation,
            stage="closure",
            event_type="operation_audit_closed",
            actor=actor,
            audit_action="operation_audit_closed",
            audit_result="success",
        )
        return _serialize_operation(operation) or {}
    action = _normalize(operation.get("action"))
    _assert_action_actor_scope(action, actor)
    spec = ACTION_SPECS[action]
    _assert_action_allowed_for_actor(spec, actor)
    if operation.get("state") == "apply_failed":
        operation = _record_stage_evidence(
            operation,
            stage="failure",
            event_type="operation_failed",
            actor=actor,
            audit_action="operation_failed",
            audit_result="failed",
            details={"error": operation.get("execution_error")},
        )
        operation = _transition(
            operation_id,
            expected_state="apply_failed",
            next_state="approved_for_apply",
            actor=actor,
            action="retry_failed_operation",
            reason_codes=["RETRY_SAME_IDEMPOTENT_OPERATION"],
            extra_set={
                "execution_retry_count": int(operation.get("execution_retry_count") or 0) + 1,
                "execution_retry_requested_at": _now(),
                "execution_error": None,
                "execution_failed_at": None,
            },
        )
        _record_event(
            operation,
            event_type="operation_retry_requested",
            actor=actor,
            details={"previous_state": "apply_failed"},
        )
    elif operation.get("state") == "apply_scheduled":
        action_started_at = operation.get("business_action_started_at")
        if action_started_at is None:
            operation = _transition(
                operation_id,
                expected_state="apply_scheduled",
                next_state="approved_for_apply",
                actor=actor,
                action="recover_pre_execution_evidence",
                reason_codes=["PRE_EXECUTION_EVIDENCE_RECOVERY"],
                extra_set={
                    "execution_retry_count": int(operation.get("execution_retry_count") or 0) + 1,
                    "execution_retry_requested_at": _now(),
                },
            )
        else:
            started_at = operation.get("execution_started_at")
            if isinstance(started_at, str):
                try:
                    started_at = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                except Exception:
                    started_at = None
            stale_before = _now() - timedelta(minutes=STALE_EXECUTION_RETRY_MINUTES)
            if not isinstance(started_at, datetime) or started_at > stale_before:
                raise ValueError("Operation execution is already in progress and is not stale.")
            operation = _transition(
                operation_id,
                expected_state="apply_scheduled",
                next_state="approved_for_apply",
                actor=actor,
                action="recover_stale_execution",
                reason_codes=["STALE_EXECUTION_RECOVERY"],
                extra_set={
                    "execution_retry_count": int(operation.get("execution_retry_count") or 0) + 1,
                    "execution_retry_requested_at": _now(),
                },
            )
    if operation.get("state") != "approved_for_apply":
        raise ValueError("Operation must be approved_for_apply before execution.")

    operation = _record_stage_evidence(
        operation,
        stage="request",
        event_type="operation_requested",
        actor=actor,
        audit_action="operation_requested",
        audit_result="success",
        details={"reason": operation.get("reason")},
        before=operation.get("before_snapshot"),
        after=operation.get("proposed_after_snapshot"),
    )
    operation = _record_stage_evidence(
        operation,
        stage="approval",
        event_type="operation_approved",
        actor=actor,
        audit_action="operation_approved",
        audit_result="success",
        details={"approval_reason": operation.get("approval_reason")},
    )

    packet = _evidence_packet(operation, actor or {})
    authorization = _authorization_decision(operation)
    transition = _scheduled_transition(operation, actor or {})
    rollback_verification = _rollback_verification(operation)
    validator_result = _validator_module().validate_apply_request(
        packet,
        authorization,
        transition,
        rollback_verification,
    )
    if not validator_result.get("passed"):
        _operations_collection().update_one(
            {"operation_id": operation_id},
            {
                "$set": {
                    "validator_result": _serialize(validator_result),
                    "blocked_reasons": list(validator_result.get("reason_codes") or []),
                    "updated_at": _now(),
                }
            },
        )
        raise ValueError("Continuity evidence validation failed: " + ", ".join(validator_result.get("reason_codes") or []))

    operation = _transition(
        operation_id,
        expected_state="approved_for_apply",
        next_state="apply_scheduled",
        actor=actor,
        action="schedule_approved_operation",
        reason_codes=["VALIDATED_FOR_EXECUTION"],
        extra_set={
            "executed_by": _actor_snapshot(actor),
            "execution_started_at": _now(),
            "evidence_packet": _serialize(packet),
            "authorization_decision": _serialize(authorization),
            "validator_result": _serialize(validator_result),
            "rollback_verification": _serialize(rollback_verification),
            "scheduling_evidence_status": "pending",
            "scheduling_evidence_errors": [],
            "business_action_started_at": None,
        },
    )
    operation = _record_stage_evidence(
        operation,
        stage="scheduling",
        event_type="operation_scheduled",
        actor=actor,
        audit_action="operation_execution_started",
        audit_result="started",
        details={"validator_result": validator_result},
        before=operation.get("before_snapshot"),
    )
    action_start = _operations_collection().update_one(
        {
            "operation_id": operation_id,
            "state": "apply_scheduled",
            "business_action_started_at": {"$in": [None, ""]},
        },
        {"$set": {"business_action_started_at": _now(), "updated_at": _now()}},
    )
    if int(getattr(action_start, "matched_count", 0)) != 1:
        raise RuntimeError(
            "Continuity business action start could not be claimed idempotently."
        )
    operation = _get_operation_document(operation_id)

    try:
        execution_parameters = dict(operation.get("parameters") or {})
        execution_parameters["continuity_operation_id"] = operation_id
        execution_result = _invoke_action(
            _normalize(operation.get("action")),
            dict(operation.get("target") or {}),
            execution_parameters,
            actor,
        )
        after_snapshot = _snapshot_for_action(
            _normalize(operation.get("action")), dict(operation.get("target") or {})
        )
        failure_count = _execution_failure_count(execution_result)
        execution_outcome = "partial_failure" if failure_count else "success"
        execution_reason_codes = ["EXECUTION_PARTIAL_FAILURE"] if failure_count else ["EXECUTION_SUCCEEDED"]
        operation = _transition(
            operation_id,
            expected_state="apply_scheduled",
            next_state="apply_executed",
            actor=actor,
            action="execute_approved_operation",
            reason_codes=execution_reason_codes,
            extra_set={
                "execution_result": _serialize(execution_result),
                "after_snapshot": _serialize(after_snapshot),
                "execution_outcome": execution_outcome,
                "execution_failure_count": failure_count,
                "evidence_recording_status": "pending",
                "execution_completed_at": _now(),
            },
        )
    except Exception as exc:
        operation = _transition(
            operation_id,
            expected_state="apply_scheduled",
            next_state="apply_failed",
            actor=actor,
            action="execute_approved_operation",
            reason_codes=["EXECUTION_FAILED"],
            extra_set={
                "execution_error": _normalize(exc) or exc.__class__.__name__,
                "execution_failed_at": _now(),
                "failure_evidence_status": "pending",
                "failure_evidence_errors": [],
            },
        )
        try:
            _record_stage_evidence(
                operation,
                stage="failure",
                event_type="operation_failed",
                actor=actor,
                audit_action="operation_failed",
                audit_result="failed",
                details={"error": _normalize(exc) or exc.__class__.__name__},
            )
        except Exception:
            # Preserve the domain execution exception. The evidence checkpoint
            # remains incomplete and is repaired before an execution retry.
            pass
        raise

    operation = _record_post_execution_evidence(
        operation,
        actor=actor,
        execution_result=execution_result,
        after_snapshot=after_snapshot,
        execution_outcome=execution_outcome,
        failure_count=failure_count,
    )
    return _serialize_operation(operation) or {}


def close_operation(operation_id: str, *, actor: dict[str, Any] | None) -> dict[str, Any]:
    operation = _get_operation_document(operation_id)
    if operation.get("state") == "audit_closed":
        operation = _record_stage_evidence(
            operation,
            stage="closure",
            event_type="operation_audit_closed",
            actor=actor,
            audit_action="operation_audit_closed",
            audit_result="success",
        )
        return _serialize_operation(operation) or {}
    if operation.get("state") not in {"apply_executed", "rollback_completed"}:
        raise ValueError("Only executed or rolled-back operations can be audit-closed.")
    if operation.get("execution_outcome") == "partial_failure":
        raise ValueError("Partial-failure operations require remediation before audit closure.")
    if operation.get("evidence_recording_status") != "complete":
        raise ValueError("Execution evidence must be complete before audit closure.")
    action = _normalize(operation.get("action"))
    _assert_action_actor_scope(action, actor)
    spec = ACTION_SPECS[action]
    _assert_action_allowed_for_actor(spec, actor)
    expected = _normalize(operation.get("state"))
    operation = _transition(
        operation_id,
        expected_state=expected,
        next_state="audit_closed",
        actor=actor,
        action="close_operation_audit",
        reason_codes=["AUDIT_CLOSED"],
        extra_set={
            "audit_closed_at": _now(),
            "closure_evidence_status": "pending",
            "closure_evidence_errors": [],
        },
    )
    operation = _record_stage_evidence(
        operation,
        stage="closure",
        event_type="operation_audit_closed",
        actor=actor,
        audit_action="operation_audit_closed",
        audit_result="success",
    )
    return _serialize_operation(operation) or {}


def execute_governed_action(
    *,
    action: str,
    target: dict[str, Any],
    parameters: dict[str, Any] | None,
    reason: str,
    idempotency_key: str,
    actor: dict[str, Any] | None,
    confirmed: bool,
    solo_founder_override_acknowledged: bool,
) -> dict[str, Any]:
    """Run request -> approval -> execution for the canonical CEO workflow."""
    if confirmed is not True:
        raise ValueError("confirmed must be true for governed execution.")
    operation = request_operation(
        action=action,
        target=target,
        parameters={**(parameters or {}), "reason": _normalize(reason)},
        reason=reason,
        idempotency_key=idempotency_key,
        actor=actor,
    )
    operation_id = _normalize(operation.get("operation_id"))
    if operation.get("blocked_reasons"):
        return operation
    if operation.get("state") == "review_requested":
        operation = approve_operation(
            operation_id,
            approval_reason=reason,
            actor=actor,
            solo_founder_override_acknowledged=solo_founder_override_acknowledged,
        )
    if operation.get("state") == "approved_for_apply":
        operation = execute_operation(operation_id, actor=actor)
    elif operation.get("state") in {
        "apply_failed",
        "apply_scheduled",
        "apply_executed",
        "audit_closed",
    }:
        operation = execute_operation(operation_id, actor=actor)
    return operation


def get_operation(operation_id: str) -> dict[str, Any]:
    return _serialize_operation(_get_operation_document(operation_id)) or {}


def list_operations(
    *, state: str = "", target_id: str = "", limit: int = 50
) -> dict[str, Any]:
    query: dict[str, Any] = {}
    if _normalize(state):
        query["state"] = _normalize(state)
    if _normalize(target_id):
        query["target_id"] = _normalize(target_id)
    bounded_limit = max(1, min(int(limit or 50), MAX_OPERATION_LIST_LIMIT))
    items = [
        _serialize_operation(item)
        for item in _operations_collection().find(query).sort("updated_at", -1).limit(bounded_limit)
    ]
    return {"items": [item for item in items if item], "count": len(items)}


def list_operation_events(operation_id: str) -> dict[str, Any]:
    operation_id = _require_text(operation_id, "operation_id")
    items = [
        _serialize(item)
        for item in _events_collection().find({"operation_id": operation_id}).sort("created_at", 1)
    ]
    return {"operation_id": operation_id, "items": items, "count": len(items)}


def runtime_status() -> dict[str, Any]:
    operations = _operations_collection()
    state_counts = {
        state: _count(operations, {"state": state})
        for state in (
            "review_requested",
            "officer_reviewing",
            "approved_for_apply",
            "apply_scheduled",
            "apply_executed",
            "apply_failed",
            "rejected",
            "audit_closed",
        )
    }
    return {
        "kernel_name": "Tomb of Light Continuity Kernel",
        "runtime_version": RUNTIME_VERSION,
        "execution_enabled": execution_enabled(),
        "kill_switch": EXECUTION_KILL_SWITCH,
        "governance_posture": "solo_founder_owner_operated_with_officer_policy_support",
        "action_count": len(ACTION_SPECS),
        "actions": {
            name: {
                "repair_category": spec.repair_category,
                "risk_level": spec.risk_level,
                "target_type": spec.target_type,
                "mutates_business_data": spec.mutates_business_data,
            }
            for name, spec in sorted(ACTION_SPECS.items())
        },
        "state_counts": state_counts,
        "components": [
            "identity_resolver",
            "entitlement_graph_resolver",
            "workspace_access_resolver",
            "lineage_event_ledger",
            "viewer_manifest_compiler",
            "readiness_gate_matrix",
            "certificate_delivery_record",
            "mint_readiness_controller",
            "officer_policy_layer",
            "self_healing_repair_engine",
            "audit_timeline",
        ],
    }


__all__ = [
    "ACTION_SPECS",
    "RUNTIME_VERSION",
    "approve_operation",
    "build_project_continuity_snapshot",
    "canonical_officer_role",
    "close_operation",
    "ensure_continuity_runtime_indexes",
    "execute_governed_action",
    "execute_operation",
    "execution_enabled",
    "get_operation",
    "list_operation_events",
    "list_operations",
    "reject_operation",
    "request_operation",
    "runtime_status",
]
