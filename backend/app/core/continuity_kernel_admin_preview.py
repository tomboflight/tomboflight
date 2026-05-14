"""
Continuity Kernel isolated read-only admin preview module.

This module is read-only.
This module is non-operational.
This module does not execute repairs.
This module does not approve apply.
This module does not schedule apply.
This module does not write to the database.
This module does not queue mint work.
This module does not mutate certificates.
This module does not alter customer records.
This module only shapes in-memory Continuity Kernel payloads into read-only preview objects.
"""

from copy import deepcopy
from datetime import datetime, timezone
from importlib import import_module
from typing import Any
from uuid import uuid4

_taxonomy = import_module("backend.app.core.continuity_kernel_taxonomy")


ALLOWED_READ_ONLY_ACTIONS = (
    "view_preview",
    "copy_case_summary",
    "export_dry_run_summary",
    "request_review",
)

PROHIBITED_ACTIONS = (
    "approve_apply",
    "schedule_apply",
    "execute_apply",
    "rollback_apply",
    "mutate_entitlement",
    "mutate_workspace_member",
    "mutate_certificate",
    "queue_mint",
    "delete_customer_record",
    "bypass_validator",
    "bypass_audit",
)

PREVIEW_STATUS_VALUES = (
    "preview_ready",
    "blocked",
    "invalid_payload",
    "missing_evidence",
    "validation_failed",
    "review_required",
)

_CANONICAL_PAYLOAD_KEYS = (
    "evidence_packet",
    "authorization_decision",
    "apply_transition",
    "rollback_verification",
    "structured_override",
    "structured_justification",
    "validator_result",
)


CANONICAL_OFFICER_ROLES = _taxonomy.CANONICAL_OFFICER_ROLES
CANONICAL_OFFICER_ROLE_SET = _taxonomy.CANONICAL_OFFICER_ROLE_SET
CANONICAL_REPAIR_CATEGORIES = _taxonomy.CANONICAL_REPAIR_CATEGORIES
CANONICAL_REPAIR_CATEGORY_SET = _taxonomy.CANONICAL_REPAIR_CATEGORY_SET
TECHNICAL_CATEGORIES = _taxonomy.TECHNICAL_CATEGORIES
OPERATIONS_CATEGORIES = _taxonomy.OPERATIONS_CATEGORIES
FINANCE_CATEGORIES = _taxonomy.FINANCE_CATEGORIES
MARKETING_CATEGORIES = _taxonomy.MARKETING_CATEGORIES
SUPERADMIN_ONLY_CATEGORIES = _taxonomy.SUPERADMIN_ONLY_CATEGORIES
READ_ONLY_PREVIEW_CATEGORIES = _taxonomy.READ_ONLY_PREVIEW_CATEGORIES
ROLE_TO_PREVIEW_CATEGORIES = _taxonomy.ROLE_TO_PREVIEW_CATEGORIES
is_canonical_role = _taxonomy.is_canonical_role
is_canonical_repair_category = _taxonomy.is_canonical_repair_category
preview_categories_for_role = _taxonomy.preview_categories_for_role


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned if cleaned else default
    return str(value)


def _safe_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return deepcopy(value)
    if isinstance(value, tuple):
        return list(value)
    return []


def _is_non_empty_dict(value: Any) -> bool:
    return isinstance(value, dict) and bool(value)


def summarize_rollback(rollback_verification: dict) -> dict:
    rollback_data = deepcopy(rollback_verification) if isinstance(rollback_verification, dict) else {}
    return {
        "present": bool(rollback_data),
        "target_type": _safe_text(rollback_data.get("target_type")),
        "target_id": _safe_text(rollback_data.get("target_id")),
        "verification_status": _safe_text(rollback_data.get("verification_status")),
        "reason_codes": _safe_list(rollback_data.get("reason_codes")),
        "has_rollback_plan": "rollback_plan" in rollback_data and bool(rollback_data.get("rollback_plan")),
    }


def summarize_override(structured_override: dict | None) -> dict:
    override_data = deepcopy(structured_override) if isinstance(structured_override, dict) else {}
    return {
        "present": bool(override_data),
        "override_type": _safe_text(override_data.get("override_type")),
        "approved_by": _safe_text(override_data.get("approved_by")),
        "approval_role": _safe_text(override_data.get("approval_role")),
        "reason_code": _safe_text(override_data.get("reason_code")),
        "target_type": _safe_text(override_data.get("target_type")),
        "target_id": _safe_text(override_data.get("target_id")),
        "repair_category": _safe_text(override_data.get("repair_category")),
        "risk_level": _safe_text(override_data.get("risk_level")),
    }


def summarize_justification(structured_justification: dict | None) -> dict:
    justification_data = deepcopy(structured_justification) if isinstance(structured_justification, dict) else {}
    return {
        "present": bool(justification_data),
        "justification_type": _safe_text(justification_data.get("justification_type")),
        "provided_by": _safe_text(justification_data.get("provided_by")),
        "reason_code": _safe_text(justification_data.get("reason_code")),
        "related_field": _safe_text(justification_data.get("related_field")),
        "target_type": _safe_text(justification_data.get("target_type")),
        "target_id": _safe_text(justification_data.get("target_id")),
        "repair_category": _safe_text(justification_data.get("repair_category")),
    }


def allowed_preview_actions_for_role(role: str, repair_category: str) -> list[str]:
    role_text = _safe_text(role)
    category_text = _safe_text(repair_category)

    allowed: list[str] = []
    if is_canonical_role(role_text) and is_canonical_repair_category(category_text):
        allowed_categories = preview_categories_for_role(role_text)
        if category_text in allowed_categories:
            allowed = list(ALLOWED_READ_ONLY_ACTIONS)

    prohibited = set(PROHIBITED_ACTIONS)
    safe_allowed = [action for action in allowed if action in ALLOWED_READ_ONLY_ACTIONS and action not in prohibited]
    return list(dict.fromkeys(safe_allowed))


def build_admin_preview(payload: dict) -> dict:
    payload_copy = deepcopy(payload) if isinstance(payload, dict) else {}

    missing_keys = [key for key in _CANONICAL_PAYLOAD_KEYS if key not in payload_copy]
    evidence_packet = payload_copy.get("evidence_packet") if isinstance(payload_copy.get("evidence_packet"), dict) else {}
    validator_result = payload_copy.get("validator_result") if isinstance(payload_copy.get("validator_result"), dict) else {}
    authorization_decision = (
        payload_copy.get("authorization_decision")
        if isinstance(payload_copy.get("authorization_decision"), dict)
        else {}
    )

    target_type = _safe_text(evidence_packet.get("target_type"))
    target_id = _safe_text(evidence_packet.get("target_id"))
    repair_category = _safe_text(evidence_packet.get("repair_category"))
    risk_level = _safe_text(evidence_packet.get("risk_level"))

    blocked_reasons = _safe_list(evidence_packet.get("blocked_reasons"))
    errors = _safe_list(validator_result.get("errors"))
    warnings = _safe_list(validator_result.get("warnings"))
    diff_summary = deepcopy(evidence_packet.get("diff_summary"))

    validator_passed = validator_result.get("passed") is True

    status = "preview_ready"
    if not _is_non_empty_dict(evidence_packet):
        status = "missing_evidence"
    elif any(not value for value in (target_type, target_id, repair_category)) or missing_keys:
        status = "invalid_payload"
    elif not validator_passed:
        status = "blocked" if blocked_reasons else "validation_failed"
    elif blocked_reasons:
        status = "review_required" if "review_required" in {str(v).lower() for v in blocked_reasons} else "blocked"

    preview_id = _safe_text(evidence_packet.get("preview_id"))
    if not preview_id:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        preview_id = f"preview::{timestamp}::{uuid4().hex[:8]}"

    return {
        "preview_id": preview_id,
        "target_type": target_type,
        "target_id": target_id,
        "repair_category": repair_category,
        "risk_level": risk_level,
        "status": status if status in PREVIEW_STATUS_VALUES else "invalid_payload",
        "blocked_reasons": blocked_reasons,
        "errors": errors,
        "warnings": warnings,
        "diff_summary": diff_summary,
        "rollback_summary": summarize_rollback(payload_copy.get("rollback_verification", {})),
        "override_summary": summarize_override(payload_copy.get("structured_override")),
        "justification_summary": summarize_justification(payload_copy.get("structured_justification")),
        "validator_passed": validator_passed,
        "allowed_actions": allowed_preview_actions_for_role(
            role=_safe_text(authorization_decision.get("actor_role")),
            repair_category=repair_category,
        ),
    }


__all__ = [
    "ALLOWED_READ_ONLY_ACTIONS",
    "PROHIBITED_ACTIONS",
    "PREVIEW_STATUS_VALUES",
    "summarize_rollback",
    "summarize_override",
    "summarize_justification",
    "allowed_preview_actions_for_role",
    "build_admin_preview",
]
