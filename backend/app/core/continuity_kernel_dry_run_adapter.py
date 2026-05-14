"""
Continuity Kernel staging-only isolated dry-run adapter module.

This module is staging-only.
This module is non-operational.
This module does not execute repairs.
This module does not write to the database.
This module does not queue mint work.
This module does not mutate certificates.
This module does not alter customer records.
This module does not call production services.
This module only assembles in-memory Continuity Kernel payloads for validation.
"""

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


PAYLOAD_KEY_EVIDENCE_PACKET = "evidence_packet"
PAYLOAD_KEY_AUTHORIZATION_DECISION = "authorization_decision"
PAYLOAD_KEY_APPLY_TRANSITION = "apply_transition"
PAYLOAD_KEY_ROLLBACK_VERIFICATION = "rollback_verification"
PAYLOAD_KEY_STRUCTURED_OVERRIDE = "structured_override"
PAYLOAD_KEY_STRUCTURED_JUSTIFICATION = "structured_justification"
PAYLOAD_KEY_VALIDATOR_RESULT = "validator_result"

CANONICAL_PAYLOAD_KEYS = (
    PAYLOAD_KEY_EVIDENCE_PACKET,
    PAYLOAD_KEY_AUTHORIZATION_DECISION,
    PAYLOAD_KEY_APPLY_TRANSITION,
    PAYLOAD_KEY_ROLLBACK_VERIFICATION,
    PAYLOAD_KEY_STRUCTURED_OVERRIDE,
    PAYLOAD_KEY_STRUCTURED_JUSTIFICATION,
    PAYLOAD_KEY_VALIDATOR_RESULT,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_text(value: Any, placeholder: str = "") -> str:
    if value is None:
        return placeholder
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else placeholder
    return str(value)


def _build_safe_dry_run_id(
    dry_run_source: dict[str, Any],
    target_selector: dict[str, Any],
    repair_category: Any,
) -> str:
    existing_id = _safe_text(dry_run_source.get("dry_run_id"))
    if existing_id:
        return existing_id

    target_type = _safe_text(target_selector.get("target_type"), "unknown_target")
    target_id = _safe_text(target_selector.get("target_id"), "unknown_id")
    category = _safe_text(repair_category, "unknown_category")
    return f"dry-run-placeholder::{target_type}::{target_id}::{category}"


def _build_staging_audit_context(source: Any = None) -> dict[str, Any]:
    context: dict[str, Any] = {
        "mode": "staging_only_dry_run",
        "non_operational": True,
        "assembly_only": True,
        "approval_status": "not_approved_placeholder",
        "apply_mode": "disabled",
    }
    if isinstance(source, dict):
        source_value = deepcopy(source)
        context["source"] = source_value
    return context


def build_evidence_packet_from_dry_run(
    dry_run_source: dict[str, Any],
    target_selector: dict[str, Any],
    actor_context: dict[str, Any],
    repair_category: Any,
    before_snapshot: dict[str, Any],
    proposed_after_snapshot: dict[str, Any],
    diff_summary: Any,
    blocked_reasons: list[Any],
    rollback_plan: dict[str, Any],
    structured_override: dict[str, Any] | None = None,
    structured_justification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_copy = deepcopy(dry_run_source) if isinstance(dry_run_source, dict) else {}
    target_copy = deepcopy(target_selector) if isinstance(target_selector, dict) else {}
    actor_copy = deepcopy(actor_context) if isinstance(actor_context, dict) else {}

    dry_run_id = _build_safe_dry_run_id(source_copy, target_copy, repair_category)
    evidence_packet_id = _safe_text(source_copy.get("evidence_packet_id"), f"evidence::{dry_run_id}")
    actor_user_id = _safe_text(actor_copy.get("actor_user_id"), "")
    requested_by = _safe_text(actor_copy.get("requested_by"), actor_user_id)
    target_type = _safe_text(target_copy.get("target_type"), "")
    target_id = _safe_text(target_copy.get("target_id"), "")
    category = _safe_text(repair_category, "")

    return {
        "dry_run_id": dry_run_id,
        "evidence_packet_id": evidence_packet_id,
        "actor_user_id": actor_user_id,
        "requested_by": requested_by,
        "reviewed_by": "",
        "approved_by": "",
        "executed_by": "",
        "approval_role": "",
        "target_type": target_type,
        "target_id": target_id,
        "repair_category": category,
        "before_snapshot": deepcopy(before_snapshot),
        "proposed_after_snapshot": deepcopy(proposed_after_snapshot),
        "diff_summary": deepcopy(diff_summary),
        "blocked_reasons": deepcopy(blocked_reasons),
        "risk_level": _safe_text(source_copy.get("risk_level"), "pending_placeholder"),
        "rollback_plan": deepcopy(rollback_plan),
        "idempotency_key": _safe_text(source_copy.get("idempotency_key"), f"idem::{dry_run_id}"),
        "created_at": _utc_now(),
        "approved_at": "",
        "executed_at": "",
        "audit_context": _build_staging_audit_context({
            "adapter": "continuity_kernel_dry_run_adapter",
            "dry_run_source": source_copy,
        }),
    }


def build_authorization_decision_placeholder(
    evidence_packet: dict[str, Any],
    actor_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    actor_copy = deepcopy(actor_context) if isinstance(actor_context, dict) else {}
    evidence_copy = deepcopy(evidence_packet) if isinstance(evidence_packet, dict) else {}

    return {
        "actor_user_id": _safe_text(actor_copy.get("actor_user_id"), ""),
        "actor_role": _safe_text(actor_copy.get("actor_role"), "operations_admin"),
        "requested_action": "review_only_placeholder",
        "repair_category": _safe_text(evidence_copy.get("repair_category"), ""),
        "target_type": _safe_text(evidence_copy.get("target_type"), ""),
        "target_id": _safe_text(evidence_copy.get("target_id"), ""),
        "decision": "not_approved_placeholder",
        "approved": False,
        "placeholder": True,
        "reason_codes": ["PLACEHOLDER_NOT_APPROVED", "VALIDATION_NOT_RUN"],
        "policy_source": "staging_dry_run_adapter_placeholder",
        "evaluated_at": _utc_now(),
    }


def build_apply_transition_placeholder(
    evidence_packet: dict[str, Any],
    actor_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    actor_copy = deepcopy(actor_context) if isinstance(actor_context, dict) else {}
    evidence_copy = deepcopy(evidence_packet) if isinstance(evidence_packet, dict) else {}

    return {
        "evidence_packet_id": _safe_text(evidence_copy.get("evidence_packet_id"), ""),
        "state": "staging_only_placeholder",
        "previous_state": "dry_run_created",
        "next_state": "review_requested",
        "actor_user_id": _safe_text(actor_copy.get("actor_user_id"), ""),
        "action": "review_only_placeholder",
        "transition_allowed": False,
        "reason_codes": ["PLACEHOLDER_TRANSITION_NOT_ALLOWED", "VALIDATION_NOT_RUN"],
        "timestamp": _utc_now(),
        "audit_context": _build_staging_audit_context({"component": "apply_transition_placeholder"}),
    }


def build_rollback_verification_placeholder(
    evidence_packet: dict[str, Any],
    rollback_plan: dict[str, Any],
) -> dict[str, Any]:
    evidence_copy = deepcopy(evidence_packet) if isinstance(evidence_packet, dict) else {}

    return {
        "evidence_packet_id": _safe_text(evidence_copy.get("evidence_packet_id"), ""),
        "rollback_plan": deepcopy(rollback_plan),
        "before_snapshot_ref": "",
        "target_type": _safe_text(evidence_copy.get("target_type"), ""),
        "target_id": _safe_text(evidence_copy.get("target_id"), ""),
        "verification_status": "pending_placeholder",
        "reason_codes": ["ROLLBACK_VERIFICATION_NOT_RUN", "VALIDATION_NOT_RUN"],
        "verified_at": _utc_now(),
        "audit_context": _build_staging_audit_context({"component": "rollback_verification_placeholder"}),
    }


def build_validator_result_placeholder(
    validator_name: str = "continuity_kernel_validator.validate_apply_request",
) -> dict[str, Any]:
    return {
        "validator_name": _safe_text(validator_name, "continuity_kernel_validator.placeholder"),
        "status": "output_only_placeholder",
        "source": "staging_dry_run_adapter",
        "passed": False,
        "reason_codes": ["VALIDATION_NOT_RUN"],
        "errors": [],
        "warnings": ["Staging dry-run adapter placeholder result; validation not executed."],
        "evaluated_at": _utc_now(),
    }


def build_staging_dry_run_payload(
    dry_run_source: dict[str, Any],
    target_selector: dict[str, Any],
    actor_context: dict[str, Any],
    repair_category: Any,
    before_snapshot: dict[str, Any],
    proposed_after_snapshot: dict[str, Any],
    diff_summary: Any,
    blocked_reasons: list[Any],
    rollback_plan: dict[str, Any],
    structured_override: dict[str, Any] | None = None,
    structured_justification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_copy = deepcopy(dry_run_source) if isinstance(dry_run_source, dict) else {}
    target_copy = deepcopy(target_selector) if isinstance(target_selector, dict) else {}
    actor_copy = deepcopy(actor_context) if isinstance(actor_context, dict) else {}
    before_copy = deepcopy(before_snapshot)
    after_copy = deepcopy(proposed_after_snapshot)
    diff_copy = deepcopy(diff_summary)
    blocked_copy = deepcopy(blocked_reasons)
    rollback_copy = deepcopy(rollback_plan)
    override_copy = deepcopy(structured_override)
    justification_copy = deepcopy(structured_justification)

    evidence_packet = build_evidence_packet_from_dry_run(
        dry_run_source=source_copy,
        target_selector=target_copy,
        actor_context=actor_copy,
        repair_category=repair_category,
        before_snapshot=before_copy,
        proposed_after_snapshot=after_copy,
        diff_summary=diff_copy,
        blocked_reasons=blocked_copy,
        rollback_plan=rollback_copy,
        structured_override=override_copy,
        structured_justification=justification_copy,
    )

    authorization_decision = build_authorization_decision_placeholder(
        evidence_packet=evidence_packet,
        actor_context=actor_copy,
    )

    apply_transition = build_apply_transition_placeholder(
        evidence_packet=evidence_packet,
        actor_context=actor_copy,
    )

    rollback_verification = build_rollback_verification_placeholder(
        evidence_packet=evidence_packet,
        rollback_plan=rollback_copy,
    )

    validator_result = build_validator_result_placeholder()

    return {
        PAYLOAD_KEY_EVIDENCE_PACKET: evidence_packet,
        PAYLOAD_KEY_AUTHORIZATION_DECISION: authorization_decision,
        PAYLOAD_KEY_APPLY_TRANSITION: apply_transition,
        PAYLOAD_KEY_ROLLBACK_VERIFICATION: rollback_verification,
        PAYLOAD_KEY_STRUCTURED_OVERRIDE: override_copy,
        PAYLOAD_KEY_STRUCTURED_JUSTIFICATION: justification_copy,
        PAYLOAD_KEY_VALIDATOR_RESULT: validator_result,
    }


__all__ = [
    "PAYLOAD_KEY_EVIDENCE_PACKET",
    "PAYLOAD_KEY_AUTHORIZATION_DECISION",
    "PAYLOAD_KEY_APPLY_TRANSITION",
    "PAYLOAD_KEY_ROLLBACK_VERIFICATION",
    "PAYLOAD_KEY_STRUCTURED_OVERRIDE",
    "PAYLOAD_KEY_STRUCTURED_JUSTIFICATION",
    "PAYLOAD_KEY_VALIDATOR_RESULT",
    "CANONICAL_PAYLOAD_KEYS",
    "build_evidence_packet_from_dry_run",
    "build_authorization_decision_placeholder",
    "build_apply_transition_placeholder",
    "build_rollback_verification_placeholder",
    "build_validator_result_placeholder",
    "build_staging_dry_run_payload",
]
