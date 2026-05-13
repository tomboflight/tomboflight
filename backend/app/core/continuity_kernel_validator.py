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

ROLE_TO_ALLOWED_CATEGORIES = {
    "SUPERADMIN": {category.value for category in RepairCategory},
    "EXECUTIVE_TECH_ADMIN": {
        RepairCategory.MISSING_ENTITLEMENT_REPAIR.value,
        RepairCategory.PACKAGE_LANE_NORMALIZATION.value,
        RepairCategory.WORKSPACE_MEMBERSHIP_REPAIR.value,
        RepairCategory.UPLOAD_READINESS_REPAIR.value,
        RepairCategory.VIEWER_READINESS_REPAIR.value,
        RepairCategory.CERTIFICATE_ISSUANCE_CONSISTENCY_REPAIR.value,
        RepairCategory.MINT_READINESS_REPAIR.value,
        RepairCategory.AUDIT_RECORD_CORRECTION_METADATA.value,
    },
    "operations_admin": {
        RepairCategory.WORKSPACE_MEMBERSHIP_REPAIR.value,
        RepairCategory.UPLOAD_READINESS_REPAIR.value,
        RepairCategory.MINT_READINESS_REPAIR.value,
        RepairCategory.VIEWER_READINESS_REPAIR.value,
    },
    "finance_admin": {RepairCategory.BILLING_ORDER_PAYMENT_REPAIR.value},
    "marketing_admin": set(),
    "CMO": set(),
}

FINANCE_ONLY_CATEGORIES = {RepairCategory.BILLING_ORDER_PAYMENT_REPAIR.value}

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
    if transition_actor_user_id in traceable_actor_ids and transition_actor_user_id != "":
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


def _validate_role_for_category(role: str, category: str, context_text: str, acc: ValidationAccumulator) -> None:
    if category not in {item.value for item in RepairCategory}:
        _add_error(acc, "UNKNOWN_REPAIR_CATEGORY", f"Unknown repair category: {category}")
        return

    if role not in ROLE_TO_ALLOWED_CATEGORIES:
        _add_error(acc, "UNKNOWN_ACTOR_ROLE", f"Unknown actor role: {role}")
        return

    if role in {"CMO", "marketing_admin"}:
        _add_error(acc, "MARKETING_ADMIN_CANNOT_APPROVE", "CMO/marketing_admin cannot approve repair execution")
        return

    if category in FINANCE_ONLY_CATEGORIES and role == "EXECUTIVE_TECH_ADMIN" and not _has_override(context_text):
        _add_error(
            acc,
            "FINANCE_CATEGORY_REQUIRES_OVERRIDE",
            "EXECUTIVE_TECH_ADMIN cannot approve finance-only category without CEO/SUPERADMIN override",
        )
        return

    if category not in ROLE_TO_ALLOWED_CATEGORIES[role]:
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
    _validate_role_for_category(role, category, _flatten_to_text(packet.get("audit_context")), acc)

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
        and not (
            role == "SUPERADMIN" and _has_override(audit_context_text)
        )
    ):
        _add_error(
            acc,
            "HIGH_RISK_REQUESTER_EXECUTOR_CONFLICT",
            "High-risk requests require separate requester/executor unless SUPERADMIN emergency override is present",
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
    _validate_role_for_category(role, category, override_context, acc)

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
        if not result.get("passed", False):
            acc.reason_codes.extend(result.get("reason_codes", []))
            acc.errors.extend(result.get("errors", []))
            acc.warnings.extend(result.get("warnings", []))

    idempotency_key = _flatten_to_text(packet.get("idempotency_key")).strip()
    if _is_blank(idempotency_key):
        _add_error(acc, "IDEMPOTENCY_KEY_BLANK", "idempotency_key must not be blank")

    if consumed_idempotency_keys is not None and idempotency_key in consumed_idempotency_keys:
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
    compatibility_context = " ".join(
        [
            _flatten_to_text(packet.get("audit_context")),
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
    if approved_by != authorization_actor_user_id and not _has_approved_by_justification(
        _flatten_to_text(packet.get("audit_context"))
    ):
        _add_error(
            acc,
            "APPROVED_BY_AUTHORIZATION_ACTOR_MISMATCH",
            "approved_by must match authorization.actor_user_id unless explicitly justified in audit_context",
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
        _add_error(
            acc,
            "UNTRACEABLE_TRANSITION_ACTOR",
            "transition actor must trace to approved actor, executor, or system-reviewed actor context",
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
