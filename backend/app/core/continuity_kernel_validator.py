"""
Continuity Kernel isolated validator module.

This module does not execute repairs.
This module does not write to the database.
This module does not queue mint work.
This module does not mutate certificates.
This module only validates future apply-mode evidence and governance contracts.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from backend.app.core.continuity_kernel_taxonomy import (
    CANONICAL_OFFICER_ROLES,
    CANONICAL_OFFICER_ROLE_SET,
    CANONICAL_REPAIR_CATEGORIES,
    CANONICAL_REPAIR_CATEGORY_SET,
    FINANCE_CATEGORIES,
    MARKETING_CATEGORIES,
    OPERATIONS_CATEGORIES,
    READ_ONLY_PREVIEW_CATEGORIES,
    ROLE_TO_ALLOWED_CATEGORIES,
    SUPERADMIN_ONLY_CATEGORIES,
    TECHNICAL_CATEGORIES,
    allowed_categories_for_role,
    is_canonical_repair_category,
    is_canonical_role,
    is_finance_category,
)


class RepairCategory(str, Enum):
    MISSING_ENTITLEMENT_REPAIR = "missing_entitlement_repair"
    PACKAGE_LANE_NORMALIZATION = "package_lane_normalization"
    WORKSPACE_MEMBERSHIP_REPAIR = "workspace_membership_repair"
    UPLOAD_READINESS_REPAIR = "upload_readiness_repair"
    VIEWER_READINESS_REPAIR = "viewer_readiness_repair"
    CERTIFICATE_ISSUANCE_CONSISTENCY_REPAIR = "certificate_issuance_consistency_repair"
    MINT_READINESS_REPAIR = "mint_readiness_repair"
    ADMIN_REPAIR_SAFETY = "admin_repair_safety"
    BILLING_ORDER_PAYMENT_REPAIR = "billing_order_payment_repair"
    AUDIT_RECORD_CORRECTION_METADATA = "audit_record_correction_metadata"


class ApplyState(str, Enum):
    DRY_RUN_CREATED = "dry_run_created"
    REVIEW_REQUESTED = "review_requested"
    OFFICER_REVIEWING = "officer_reviewing"
    APPROVED_FOR_APPLY = "approved_for_apply"
    REJECTED = "rejected"
    APPLY_SCHEDULED = "apply_scheduled"
    APPLY_EXECUTED = "apply_executed"
    APPLY_FAILED = "apply_failed"
    ROLLBACK_REQUIRED = "rollback_required"
    ROLLBACK_COMPLETED = "rollback_completed"
    AUDIT_CLOSED = "audit_closed"


class ValidatorDecision(str, Enum):
    PASS = "pass"
    FAIL = "fail"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


SUPERADMIN_CATEGORIES = frozenset(CANONICAL_REPAIR_CATEGORIES)


EVIDENCE_REQUIRED_FIELDS = {
    "dry_run_id",
    "evidence_packet_id",
    "actor_user_id",
    "requested_by",
    "reviewed_by",
    "approved_by",
    "executed_by",
    "approval_role",
    "target_type",
    "target_id",
    "repair_category",
    "before_snapshot",
    "proposed_after_snapshot",
    "diff_summary",
    "blocked_reasons",
    "risk_level",
    "rollback_plan",
    "idempotency_key",
    "created_at",
    "approved_at",
    "executed_at",
    "audit_context",
}

AUTHORIZATION_REQUIRED_FIELDS = {
    "actor_user_id",
    "actor_role",
    "requested_action",
    "repair_category",
    "target_type",
    "target_id",
    "decision",
    "reason_codes",
    "policy_source",
    "evaluated_at",
}

TRANSITION_REQUIRED_FIELDS = {
    "evidence_packet_id",
    "previous_state",
    "next_state",
    "actor_user_id",
    "action",
    "transition_allowed",
    "reason_codes",
    "timestamp",
    "audit_context",
}

ROLLBACK_REQUIRED_FIELDS = {
    "evidence_packet_id",
    "rollback_plan",
    "before_snapshot_ref",
    "target_type",
    "target_id",
    "verification_status",
    "reason_codes",
    "verified_at",
    "audit_context",
}

ALLOWED_APPLY_TRANSITIONS = {
    (ApplyState.DRY_RUN_CREATED.value, ApplyState.REVIEW_REQUESTED.value),
    (ApplyState.REVIEW_REQUESTED.value, ApplyState.OFFICER_REVIEWING.value),
    (ApplyState.OFFICER_REVIEWING.value, ApplyState.APPROVED_FOR_APPLY.value),
    (ApplyState.OFFICER_REVIEWING.value, ApplyState.REJECTED.value),
    (ApplyState.APPROVED_FOR_APPLY.value, ApplyState.APPLY_SCHEDULED.value),
    (ApplyState.APPLY_SCHEDULED.value, ApplyState.APPLY_EXECUTED.value),
    (ApplyState.APPLY_SCHEDULED.value, ApplyState.APPLY_FAILED.value),
    (ApplyState.APPLY_FAILED.value, ApplyState.ROLLBACK_REQUIRED.value),
    (ApplyState.ROLLBACK_REQUIRED.value, ApplyState.ROLLBACK_COMPLETED.value),
    (ApplyState.APPLY_EXECUTED.value, ApplyState.AUDIT_CLOSED.value),
    (ApplyState.ROLLBACK_COMPLETED.value, ApplyState.AUDIT_CLOSED.value),
}

FINANCE_ONLY_CATEGORIES = FINANCE_CATEGORIES

PROHIBITED_ACTION_SIGNALS = {
    "PROHIBITED_QUEUE_MINT_WORK": (
        "queue mint work directly",
        "queueing mint work directly",
        "queue mint",
    ),
    "PROHIBITED_MUTATE_IMMUTABLE_CERTIFICATE": (
        "mutate immutable issued certificate",
        "mutating immutable issued certificate",
        "immutable issued certificate mutation",
    ),
    "PROHIBITED_DELETE_CUSTOMER_RECORD": (
        "delete customer record",
        "deleting customer record",
    ),
    "PROHIBITED_BYPASS_AUTH": ("bypass auth",),
    "PROHIBITED_BYPASS_ENTITLEMENT": ("bypass entitlement",),
    "PROHIBITED_BYPASS_VERIFICATION": ("bypass verification",),
    "PROHIBITED_BYPASS_MINT_READINESS": ("bypass mint readiness",),
    "PROHIBITED_BYPASS_AUDIT_LOGGING": ("bypass audit logging",),
    "PROHIBITED_BYPASS_OFFICER_PERMISSIONS": ("bypass officer permissions",),
    "PROHIBITED_HARDCODE_CUSTOMER_PROD_VALUES": (
        "hard-code customer-specific production values",
        "hardcode customer-specific production values",
    ),
}

STRUCTURED_OVERRIDE_REQUIRED_FIELDS = {
    "override_id",
    "override_type",
    "requested_by",
    "approved_by",
    "approval_role",
    "reason_code",
    "reason_detail",
    "target_type",
    "target_id",
    "repair_category",
    "risk_level",
    "expires_at",
    "audit_context",
}

STRUCTURED_JUSTIFICATION_REQUIRED_FIELDS = {
    "justification_id",
    "justification_type",
    "provided_by",
    "reason_code",
    "reason_detail",
    "related_field",
    "target_type",
    "target_id",
    "repair_category",
    "audit_context",
}

ALLOWED_OVERRIDE_TYPES = {
    "SUPERADMIN_EMERGENCY_OVERRIDE",
    "CEO_APPROVED_FINANCE_OVERRIDE",
    "APPROVER_IDENTITY_MISMATCH_OVERRIDE",
    "HIGH_RISK_SAME_ACTOR_OVERRIDE",
}

ALLOWED_JUSTIFICATION_TYPES = {
    "APPROVED_BY_ACTOR_MISMATCH",
    "TRANSITION_ACTOR_TRACEABILITY",
    "ROLLBACK_REFERENCE_JUSTIFICATION",
    "FINANCE_TECH_SCOPE_JUSTIFICATION",
}

ROLE_COMPATIBILITY_OVERRIDE_SIGNALS = {
    "role compatibility override",
    "approval role compatibility override",
    "approval_role_compatibility_override",
}

APPROVED_BY_JUSTIFICATION_SIGNALS = {
    "approved_by mismatch justified",
    "approved_by justified",
    "delegated approver justification",
}

SYSTEM_REVIEWED_ACTOR_SIGNALS = {
    "system-reviewed actor",
    "system reviewed actor",
    "system_reviewed_actor",
}

MARKETING_RESTRICTED_ACTOR_IDS = {"marketing_admin", "cmo"}
CEO_EQUIVALENT_APPROVAL_ROLES = {"SUPERADMIN", "CEO", "CEO_EQUIVALENT", "CHIEF_EXECUTIVE_OFFICER"}


@dataclass(frozen=True)
class ValidationAccumulator:
    reason_codes: list[str]
    errors: list[str]
    warnings: list[str]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_accumulator() -> ValidationAccumulator:
    return ValidationAccumulator(reason_codes=[], errors=[], warnings=[])


def _add_error(acc: ValidationAccumulator, reason_code: str, message: str) -> None:
    acc.reason_codes.append(reason_code)
    acc.errors.append(message)


def _finish_result(validator_name: str, acc: ValidationAccumulator) -> dict[str, Any]:
    return {
        "validator_name": validator_name,
        "passed": len(acc.errors) == 0,
        "reason_codes": acc.reason_codes,
        "errors": acc.errors,
        "warnings": acc.warnings,
        "evaluated_at": _utc_now(),
    }


def _find_missing_fields(payload: dict[str, Any], required_fields: set[str]) -> list[str]:
    return sorted([field for field in required_fields if field not in payload])


def _is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def _flatten_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(f"{k} {_flatten_to_text(v)}" for k, v in value.items())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_flatten_to_text(item) for item in value)
    return str(value)


def _has_override(text: str) -> bool:
    lowered = text.lower()
    return (
        "emergency override" in lowered
        or "emergency_override" in lowered
        or "superadmin override" in lowered
        or "superadmin_override" in lowered
        or "ceo override" in lowered
        or "ceo_override" in lowered
    )


def _has_role_compatibility_override(text: str) -> bool:
    lowered = text.lower()
    return any(signal in lowered for signal in ROLE_COMPATIBILITY_OVERRIDE_SIGNALS)


def _has_approved_by_justification(text: str) -> bool:
    lowered = text.lower()
    return any(signal in lowered for signal in APPROVED_BY_JUSTIFICATION_SIGNALS)


def _is_transition_actor_traceable(
    transition_actor_user_id: str,
    approved_by: str,
    executed_by: str,
    authorization_actor_user_id: str,
    context_text: str,
) -> bool:
    traceable_actor_ids = {approved_by, executed_by, authorization_actor_user_id}
    if transition_actor_user_id != "" and transition_actor_user_id in traceable_actor_ids:
        return True
    lowered = context_text.lower()
    return any(signal in lowered for signal in SYSTEM_REVIEWED_ACTOR_SIGNALS)


def _rollback_plan_references_before_snapshot(rollback_plan: Any) -> bool:
    rollback_plan_text = _flatten_to_text(rollback_plan).lower()
    return "before_snapshot" in rollback_plan_text or "before_snapshot_ref" in rollback_plan_text


def _scan_prohibited_text_fields(fields: list[Any], acc: ValidationAccumulator) -> None:
    combined_text = " ".join(_flatten_to_text(field) for field in fields).lower()
    for reason_code, signals in PROHIBITED_ACTION_SIGNALS.items():
        if any(signal in combined_text for signal in signals):
            _add_error(acc, reason_code, f"Prohibited action signal detected: {reason_code}")


def _normalize_role(role: Any) -> str:
    if _is_blank(role):
        return ""
    return str(role).strip()


def _merge_nested_result(acc: ValidationAccumulator, result: dict[str, Any]) -> None:
    if result.get("passed", False):
        return
    acc.reason_codes.extend(result.get("reason_codes", []))
    acc.errors.extend(result.get("errors", []))
    acc.warnings.extend(result.get("warnings", []))


def _extract_structured_override(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    for key in ("structured_override", "override"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return None


def _extract_structured_justification(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    for key in ("structured_justification", "justification"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return None


def _parse_iso8601_utc(raw_value: Any) -> datetime | None:
    value = _flatten_to_text(raw_value).strip()
    if value == "":
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def validate_structured_override(override: dict[str, Any], packet: dict[str, Any] | None = None) -> dict[str, Any]:
    acc = _new_accumulator()
    validator_name = "validate_structured_override"

    if not isinstance(override, dict):
        _add_error(acc, "INVALID_STRUCTURED_OVERRIDE", "override must be a dictionary/object")
        return _finish_result(validator_name, acc)

    missing_fields = _find_missing_fields(override, STRUCTURED_OVERRIDE_REQUIRED_FIELDS)
    if missing_fields:
        _add_error(
            acc,
            "MISSING_REQUIRED_FIELDS",
            f"Missing required structured override fields: {', '.join(missing_fields)}",
        )
        return _finish_result(validator_name, acc)

    for field in STRUCTURED_OVERRIDE_REQUIRED_FIELDS:
        if _is_blank(override.get(field)):
            _add_error(acc, "BLANK_STRUCTURED_OVERRIDE_FIELD", f"Structured override field {field} must not be blank")

    override_type = _flatten_to_text(override.get("override_type")).strip()
    if override_type not in ALLOWED_OVERRIDE_TYPES:
        _add_error(acc, "UNKNOWN_OVERRIDE_TYPE", f"Unknown override_type: {override_type}")

    approval_role = _normalize_role(override.get("approval_role"))
    if approval_role in {"CMO", "marketing_admin"}:
        _add_error(acc, "MARKETING_ADMIN_CANNOT_OVERRIDE", "CMO/marketing_admin cannot create or approve overrides")

    requested_by = _flatten_to_text(override.get("requested_by")).strip().lower()
    approved_by = _flatten_to_text(override.get("approved_by")).strip().lower()
    if requested_by in MARKETING_RESTRICTED_ACTOR_IDS or approved_by in MARKETING_RESTRICTED_ACTOR_IDS:
        _add_error(acc, "MARKETING_ADMIN_CANNOT_OVERRIDE", "CMO/marketing_admin cannot create or approve overrides")

    if override_type == "SUPERADMIN_EMERGENCY_OVERRIDE" and approval_role not in CEO_EQUIVALENT_APPROVAL_ROLES:
        _add_error(
            acc,
            "INVALID_OVERRIDE_APPROVAL_ROLE",
            "SUPERADMIN_EMERGENCY_OVERRIDE requires SUPERADMIN or CEO-equivalent approval_role",
        )

    if _flatten_to_text(override.get("risk_level")).strip().lower() not in {level.value for level in RiskLevel}:
        _add_error(acc, "UNKNOWN_RISK_LEVEL", f"Unknown risk_level: {_flatten_to_text(override.get('risk_level')).strip()}")

    expires_at = _parse_iso8601_utc(override.get("expires_at"))
    if expires_at is None:
        _add_error(acc, "INVALID_OVERRIDE_EXPIRY", "expires_at must be a valid ISO-8601 timestamp")
    elif expires_at <= datetime.now(timezone.utc):
        _add_error(acc, "EXPIRED_OVERRIDE", "Structured override is expired and fails closed")

    if packet is not None and isinstance(packet, dict):
        for field in ("target_type", "target_id", "repair_category"):
            override_value = _flatten_to_text(override.get(field)).strip()
            packet_value = _flatten_to_text(packet.get(field)).strip()
            if override_value != packet_value:
                _add_error(
                    acc,
                    "OVERRIDE_PACKET_SCOPE_MISMATCH",
                    f"Structured override {field} must match packet {field}",
                )

    _scan_prohibited_text_fields([override], acc)
    return _finish_result(validator_name, acc)


def validate_structured_justification(
    justification: dict[str, Any], packet: dict[str, Any] | None = None
) -> dict[str, Any]:
    acc = _new_accumulator()
    validator_name = "validate_structured_justification"

    if not isinstance(justification, dict):
        _add_error(acc, "INVALID_STRUCTURED_JUSTIFICATION", "justification must be a dictionary/object")
        return _finish_result(validator_name, acc)

    missing_fields = _find_missing_fields(justification, STRUCTURED_JUSTIFICATION_REQUIRED_FIELDS)
    if missing_fields:
        _add_error(
            acc,
            "MISSING_REQUIRED_FIELDS",
            f"Missing required structured justification fields: {', '.join(missing_fields)}",
        )
        return _finish_result(validator_name, acc)

    for field in STRUCTURED_JUSTIFICATION_REQUIRED_FIELDS:
        if _is_blank(justification.get(field)):
            _add_error(
                acc,
                "BLANK_STRUCTURED_JUSTIFICATION_FIELD",
                f"Structured justification field {field} must not be blank",
            )

    justification_type = _flatten_to_text(justification.get("justification_type")).strip()
    if justification_type not in ALLOWED_JUSTIFICATION_TYPES:
        _add_error(acc, "UNKNOWN_JUSTIFICATION_TYPE", f"Unknown justification_type: {justification_type}")

    provided_by = _flatten_to_text(justification.get("provided_by")).strip().lower()
    if provided_by in MARKETING_RESTRICTED_ACTOR_IDS:
        _add_error(
            acc,
            "MARKETING_ADMIN_CANNOT_APPROVE",
            "CMO/marketing_admin justification cannot approve repair execution",
        )

    if packet is not None and isinstance(packet, dict):
        for field in ("target_type", "target_id", "repair_category"):
            justification_value = _flatten_to_text(justification.get(field)).strip()
            packet_value = _flatten_to_text(packet.get(field)).strip()
            if justification_value != packet_value:
                _add_error(
                    acc,
                    "JUSTIFICATION_PACKET_SCOPE_MISMATCH",
                    f"Structured justification {field} must match packet {field}",
                )

    _scan_prohibited_text_fields([justification], acc)
    return _finish_result(validator_name, acc)


def _validate_role_for_category(
    role: str,
    category: str,
    context_text: str,
    acc: ValidationAccumulator,
    structured_override: dict[str, Any] | None = None,
    packet: dict[str, Any] | None = None,
) -> None:
    if not is_canonical_repair_category(category):
        _add_error(acc, "UNKNOWN_REPAIR_CATEGORY", f"Unknown repair category: {category}")
        return

    if not is_canonical_role(role):
        _add_error(acc, "UNKNOWN_ACTOR_ROLE", f"Unknown actor role: {role}")
        return

    if role in {"CMO", "marketing_admin"}:
        _add_error(acc, "MARKETING_ADMIN_CANNOT_APPROVE", "CMO/marketing_admin cannot approve repair execution")
        return

    if is_finance_category(category) and role == "EXECUTIVE_TECH_ADMIN":
        if not isinstance(structured_override, dict):
            _add_error(
                acc,
                "STRUCTURED_OVERRIDE_REQUIRED",
                "EXECUTIVE_TECH_ADMIN cannot approve finance-only category without structured CEO/SUPERADMIN override",
            )
            return

        structured_override_result = validate_structured_override(structured_override, packet=packet)
        _merge_nested_result(acc, structured_override_result)
        if not structured_override_result.get("passed", False):
            return

        if (
            _flatten_to_text(structured_override.get("override_type")).strip() != "CEO_APPROVED_FINANCE_OVERRIDE"
            or _normalize_role(structured_override.get("approval_role")) not in CEO_EQUIVALENT_APPROVAL_ROLES
        ):
            _add_error(
                acc,
                "FINANCE_CATEGORY_REQUIRES_OVERRIDE",
                "Finance-only override must be CEO_APPROVED_FINANCE_OVERRIDE with CEO/SUPERADMIN approval_role",
            )
            return
        return

    if category not in allowed_categories_for_role(role):
        _add_error(acc, "ROLE_CATEGORY_MISMATCH", f"Role {role} is not allowed to approve category {category}")


def validate_evidence_packet(packet: dict[str, Any]) -> dict[str, Any]:
    acc = _new_accumulator()
    validator_name = "validate_evidence_packet"

    missing_fields = _find_missing_fields(packet, EVIDENCE_REQUIRED_FIELDS)
    if missing_fields:
        _add_error(acc, "MISSING_REQUIRED_FIELDS", f"Missing required evidence fields: {', '.join(missing_fields)}")
        return _finish_result(validator_name, acc)

    if _is_blank(packet.get("rollback_plan")):
        _add_error(acc, "MISSING_ROLLBACK_PLAN", "rollback_plan is required")

    if _is_blank(packet.get("audit_context")):
        _add_error(acc, "MISSING_AUDIT_CONTEXT", "audit_context is required")

    role = _normalize_role(packet.get("approval_role"))
    category = _flatten_to_text(packet.get("repair_category")).strip()
    structured_override = _extract_structured_override(packet)
    _validate_role_for_category(
        role,
        category,
        _flatten_to_text(packet.get("audit_context")),
        acc,
        structured_override=structured_override,
        packet=packet,
    )

    _scan_prohibited_text_fields(
        [
            packet.get("proposed_after_snapshot"),
            packet.get("diff_summary"),
            packet.get("repair_category"),
            packet.get("audit_context"),
        ],
        acc,
    )

    risk_level = _flatten_to_text(packet.get("risk_level")).lower().strip()
    requested_by = _flatten_to_text(packet.get("requested_by")).strip()
    executed_by = _flatten_to_text(packet.get("executed_by")).strip()
    audit_context_text = _flatten_to_text(packet.get("audit_context"))

    if (
        risk_level == RiskLevel.HIGH.value
        and requested_by != ""
        and executed_by != ""
        and requested_by == executed_by
        and role != "SUPERADMIN"
    ):
        _add_error(
            acc,
            "HIGH_RISK_REQUESTER_EXECUTOR_CONFLICT",
            "High-risk requests require separate requester/executor unless SUPERADMIN emergency override is present",
        )
    elif risk_level == RiskLevel.HIGH.value and requested_by != "" and executed_by != "" and requested_by == executed_by:
        if not isinstance(structured_override, dict):
            _add_error(
                acc,
                "STRUCTURED_OVERRIDE_REQUIRED",
                "High-risk same requester/executor requires a valid StructuredOverrideSchema emergency override",
            )
        else:
            structured_override_result = validate_structured_override(structured_override, packet=packet)
            _merge_nested_result(acc, structured_override_result)
            if structured_override_result.get("passed", False):
                if _flatten_to_text(structured_override.get("override_type")).strip() != "SUPERADMIN_EMERGENCY_OVERRIDE":
                    _add_error(
                        acc,
                        "INVALID_OVERRIDE_TYPE_FOR_HIGH_RISK",
                        "High-risk same requester/executor requires SUPERADMIN_EMERGENCY_OVERRIDE",
                    )

    return _finish_result(validator_name, acc)


def validate_authorization_decision(decision: dict[str, Any]) -> dict[str, Any]:
    acc = _new_accumulator()
    validator_name = "validate_authorization_decision"

    missing_fields = _find_missing_fields(decision, AUTHORIZATION_REQUIRED_FIELDS)
    if missing_fields:
        _add_error(
            acc,
            "MISSING_REQUIRED_FIELDS",
            f"Missing required authorization fields: {', '.join(missing_fields)}",
        )
        return _finish_result(validator_name, acc)

    role = _normalize_role(decision.get("actor_role"))
    category = _flatten_to_text(decision.get("repair_category")).strip()
    override_context = " ".join(
        [
            _flatten_to_text(decision.get("reason_codes")),
            _flatten_to_text(decision.get("policy_source")),
            _flatten_to_text(decision.get("decision")),
        ]
    )
    _validate_role_for_category(
        role,
        category,
        override_context,
        acc,
        structured_override=_extract_structured_override(decision),
        packet=decision,
    )

    decision_value = _flatten_to_text(decision.get("decision")).lower().strip()
    if decision_value not in {"approve", "approved", "allow", "allowed", "approved_for_apply"}:
        _add_error(acc, "AUTHORIZATION_NOT_APPROVED", "Authorization decision must be explicit approval")

    _scan_prohibited_text_fields(
        [
            decision.get("requested_action"),
            decision.get("repair_category"),
            decision.get("reason_codes"),
            decision.get("policy_source"),
        ],
        acc,
    )

    return _finish_result(validator_name, acc)


def validate_apply_state_transition(transition: dict[str, Any]) -> dict[str, Any]:
    acc = _new_accumulator()
    validator_name = "validate_apply_state_transition"

    missing_fields = _find_missing_fields(transition, TRANSITION_REQUIRED_FIELDS)
    if missing_fields:
        _add_error(acc, "MISSING_REQUIRED_FIELDS", f"Missing required transition fields: {', '.join(missing_fields)}")
        return _finish_result(validator_name, acc)

    if _is_blank(transition.get("audit_context")):
        _add_error(acc, "MISSING_AUDIT_CONTEXT", "audit_context is required")

    previous_state = _flatten_to_text(transition.get("previous_state")).strip()
    next_state = _flatten_to_text(transition.get("next_state")).strip()
    state_pair = (previous_state, next_state)
    if state_pair not in ALLOWED_APPLY_TRANSITIONS:
        _add_error(
            acc,
            "INVALID_APPLY_STATE_TRANSITION",
            f"Transition {previous_state} -> {next_state} is not allowed",
        )

    if transition.get("transition_allowed") is not True:
        _add_error(acc, "TRANSITION_NOT_ALLOWED_FLAG", "transition_allowed must be true")

    _scan_prohibited_text_fields(
        [transition.get("action"), transition.get("audit_context"), transition.get("reason_codes")],
        acc,
    )

    return _finish_result(validator_name, acc)


def validate_rollback_verification(rollback: dict[str, Any]) -> dict[str, Any]:
    acc = _new_accumulator()
    validator_name = "validate_rollback_verification"

    missing_fields = _find_missing_fields(rollback, ROLLBACK_REQUIRED_FIELDS)
    if missing_fields:
        _add_error(acc, "MISSING_REQUIRED_FIELDS", f"Missing required rollback fields: {', '.join(missing_fields)}")
        return _finish_result(validator_name, acc)

    if _is_blank(rollback.get("rollback_plan")):
        _add_error(acc, "MISSING_ROLLBACK_PLAN", "rollback_plan is required")

    if _is_blank(rollback.get("audit_context")):
        _add_error(acc, "MISSING_AUDIT_CONTEXT", "audit_context is required")

    _scan_prohibited_text_fields(
        [rollback.get("rollback_plan"), rollback.get("audit_context"), rollback.get("reason_codes")],
        acc,
    )

    return _finish_result(validator_name, acc)


def validate_apply_request(
    packet: dict[str, Any],
    authorization: dict[str, Any],
    transition: dict[str, Any],
    rollback: dict[str, Any] | None = None,
    consumed_idempotency_keys: set[str] | None = None,
) -> dict[str, Any]:
    acc = _new_accumulator()
    validator_name = "validate_apply_request"

    packet_result = validate_evidence_packet(packet)
    authorization_result = validate_authorization_decision(authorization)
    transition_result = validate_apply_state_transition(transition)
    rollback_result = validate_rollback_verification(rollback) if rollback is not None else None

    nested_results = [packet_result, authorization_result, transition_result]
    if rollback_result is not None:
        nested_results.append(rollback_result)

    for result in nested_results:
        _merge_nested_result(acc, result)

    idempotency_key = _flatten_to_text(packet.get("idempotency_key")).strip()
    if _is_blank(idempotency_key):
        _add_error(acc, "IDEMPOTENCY_KEY_BLANK", "idempotency_key must not be blank")

    if consumed_idempotency_keys is not None and not _is_blank(idempotency_key) and idempotency_key in consumed_idempotency_keys:
        _add_error(acc, "IDEMPOTENCY_KEY_ALREADY_CONSUMED", f"idempotency_key already consumed: {idempotency_key}")

    if _flatten_to_text(packet.get("evidence_packet_id")).strip() != _flatten_to_text(transition.get("evidence_packet_id")).strip():
        _add_error(acc, "EVIDENCE_PACKET_ID_MISMATCH", "evidence_packet_id mismatch between packet and transition")

    if _flatten_to_text(packet.get("repair_category")).strip() != _flatten_to_text(authorization.get("repair_category")).strip():
        _add_error(acc, "REPAIR_CATEGORY_MISMATCH", "repair_category mismatch between packet and authorization")

    if _flatten_to_text(packet.get("target_type")).strip() != _flatten_to_text(authorization.get("target_type")).strip():
        _add_error(acc, "TARGET_TYPE_MISMATCH", "target_type mismatch between packet and authorization")

    if _flatten_to_text(packet.get("target_id")).strip() != _flatten_to_text(authorization.get("target_id")).strip():
        _add_error(acc, "TARGET_ID_MISMATCH", "target_id mismatch between packet and authorization")

    approval_role = _normalize_role(packet.get("approval_role"))
    authorization_actor_role = _normalize_role(authorization.get("actor_role"))
    packet_audit_context_text = _flatten_to_text(packet.get("audit_context"))
    compatibility_context = " ".join(
        [
            packet_audit_context_text,
            _flatten_to_text(authorization.get("reason_codes")),
            _flatten_to_text(authorization.get("policy_source")),
        ]
    )
    if approval_role != authorization_actor_role and not _has_role_compatibility_override(compatibility_context):
        _add_error(
            acc,
            "APPROVAL_AUTHORIZATION_ROLE_MISMATCH",
            "approval_role and authorization actor_role mismatch without explicit compatibility override",
        )

    approved_by = _flatten_to_text(packet.get("approved_by")).strip()
    authorization_actor_user_id = _flatten_to_text(authorization.get("actor_user_id")).strip()
    packet_structured_justification = _extract_structured_justification(packet)
    if approved_by != authorization_actor_user_id:
        if not isinstance(packet_structured_justification, dict):
            _add_error(
                acc,
                "STRUCTURED_JUSTIFICATION_REQUIRED",
                "approved_by mismatch requires a valid StructuredJustificationSchema",
            )
        else:
            justification_result = validate_structured_justification(packet_structured_justification, packet=packet)
            _merge_nested_result(acc, justification_result)
            if (
                justification_result.get("passed", False)
                and _flatten_to_text(packet_structured_justification.get("justification_type")).strip()
                != "APPROVED_BY_ACTOR_MISMATCH"
            ):
                _add_error(
                    acc,
                    "INVALID_JUSTIFICATION_TYPE",
                    "approved_by mismatch requires APPROVED_BY_ACTOR_MISMATCH justification_type",
                )

    transition_actor_user_id = _flatten_to_text(transition.get("actor_user_id")).strip()
    if not _is_transition_actor_traceable(
        transition_actor_user_id=transition_actor_user_id,
        approved_by=approved_by,
        executed_by=_flatten_to_text(packet.get("executed_by")).strip(),
        authorization_actor_user_id=authorization_actor_user_id,
        context_text=" ".join(
            [
                _flatten_to_text(transition.get("audit_context")),
                _flatten_to_text(transition.get("reason_codes")),
            ]
        ),
    ):
        transition_structured_justification = _extract_structured_justification(transition)
        if not isinstance(transition_structured_justification, dict):
            _add_error(
                acc,
                "STRUCTURED_JUSTIFICATION_REQUIRED",
                "transition actor traceability mismatch requires a valid StructuredJustificationSchema",
            )
        else:
            transition_justification_result = validate_structured_justification(
                transition_structured_justification,
                packet=packet,
            )
            _merge_nested_result(acc, transition_justification_result)
            if (
                transition_justification_result.get("passed", False)
                and _flatten_to_text(transition_structured_justification.get("justification_type")).strip()
                != "TRANSITION_ACTOR_TRACEABILITY"
            ):
                _add_error(
                    acc,
                    "INVALID_JUSTIFICATION_TYPE",
                    "transition actor traceability mismatch requires TRANSITION_ACTOR_TRACEABILITY justification_type",
                )

    if rollback is not None:
        if _flatten_to_text(packet.get("evidence_packet_id")).strip() != _flatten_to_text(rollback.get("evidence_packet_id")).strip():
            _add_error(
                acc,
                "ROLLBACK_EVIDENCE_PACKET_ID_MISMATCH",
                "evidence_packet_id mismatch between packet and rollback verification",
            )

        if _flatten_to_text(packet.get("target_type")).strip() != _flatten_to_text(rollback.get("target_type")).strip():
            _add_error(acc, "ROLLBACK_TARGET_TYPE_MISMATCH", "target_type mismatch between packet and rollback verification")

        if _flatten_to_text(packet.get("target_id")).strip() != _flatten_to_text(rollback.get("target_id")).strip():
            _add_error(acc, "ROLLBACK_TARGET_ID_MISMATCH", "target_id mismatch between packet and rollback verification")

        if not _rollback_plan_references_before_snapshot(rollback.get("rollback_plan")):
            _add_error(
                acc,
                "ROLLBACK_PLAN_MISSING_BEFORE_SNAPSHOT_REFERENCE",
                "rollback_plan must reference before_snapshot or before_snapshot_ref",
            )

    return _finish_result(validator_name, acc)
