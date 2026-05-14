"""
Continuity Kernel in-memory approval fixture helpers for isolated tests only.

These fixtures are in-memory test helpers only and are not production approvals.
They do not wire routes, do not access databases, and do not execute repairs.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _future_utc(days: int = 365) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _build_valid_approval_fixture(
    *,
    fixture_id: str,
    actor_user_id: str,
    actor_role: str,
    repair_category: str,
    target_type: str,
    target_id: str,
) -> dict:
    now = _utc_now()
    evidence_packet_id = f"evidence::{fixture_id}"
    before_snapshot_ref = f"before_snapshot_ref::{evidence_packet_id}"

    evidence_packet = {
        "dry_run_id": f"dry-run::{fixture_id}",
        "evidence_packet_id": evidence_packet_id,
        "actor_user_id": actor_user_id,
        "requested_by": actor_user_id,
        "reviewed_by": actor_user_id,
        "approved_by": actor_user_id,
        "executed_by": "",
        "approval_role": actor_role,
        "target_type": target_type,
        "target_id": target_id,
        "repair_category": repair_category,
        "before_snapshot": {"fixture": fixture_id, "state": "before"},
        "proposed_after_snapshot": {"fixture": fixture_id, "state": "after"},
        "diff_summary": f"isolated fixture diff summary for {fixture_id}",
        "blocked_reasons": [],
        "risk_level": "medium",
        "rollback_plan": {
            "strategy": "restore_before_snapshot_reference",
            "before_snapshot_ref": before_snapshot_ref,
        },
        "idempotency_key": f"idem::{fixture_id}",
        "created_at": now,
        "approved_at": now,
        "executed_at": "",
        "audit_context": {
            "source": "continuity_kernel_test_fixtures",
            "phase": "6e",
            "non_operational": True,
            "in_memory_only": True,
        },
    }

    authorization_decision = {
        "actor_user_id": actor_user_id,
        "actor_role": actor_role,
        "requested_action": "approve",
        "repair_category": repair_category,
        "target_type": target_type,
        "target_id": target_id,
        "decision": "approved_for_apply",
        "reason_codes": ["ISOLATED_TEST_FIXTURE_APPROVAL"],
        "policy_source": "phase6e_in_memory_fixture",
        "evaluated_at": now,
    }

    apply_transition = {
        "evidence_packet_id": evidence_packet_id,
        "previous_state": "officer_reviewing",
        "next_state": "approved_for_apply",
        "actor_user_id": actor_user_id,
        "action": "approve_for_apply_transition",
        "transition_allowed": True,
        "reason_codes": ["ISOLATED_TEST_FIXTURE_TRANSITION_ALLOWED"],
        "timestamp": now,
        "audit_context": {
            "source": "continuity_kernel_test_fixtures",
            "phase": "6e",
            "non_operational": True,
            "in_memory_only": True,
        },
    }

    rollback_verification = {
        "evidence_packet_id": evidence_packet_id,
        "rollback_plan": deepcopy(evidence_packet["rollback_plan"]),
        "before_snapshot_ref": before_snapshot_ref,
        "target_type": target_type,
        "target_id": target_id,
        "verification_status": "verified",
        "reason_codes": ["ISOLATED_TEST_FIXTURE_ROLLBACK_VERIFIED"],
        "verified_at": now,
        "audit_context": {
            "source": "continuity_kernel_test_fixtures",
            "phase": "6e",
            "non_operational": True,
            "in_memory_only": True,
        },
    }

    structured_override = {
        "override_id": f"override::{fixture_id}",
        "override_type": "SUPERADMIN_EMERGENCY_OVERRIDE",
        "requested_by": actor_user_id,
        "approved_by": actor_user_id,
        "approval_role": "SUPERADMIN",
        "reason_code": "ISOLATED_TEST_FIXTURE_OVERRIDE",
        "reason_detail": "in-memory fixture metadata only",
        "target_type": target_type,
        "target_id": target_id,
        "repair_category": repair_category,
        "risk_level": "medium",
        "expires_at": _future_utc(365),
        "audit_context": {
            "source": "continuity_kernel_test_fixtures",
            "phase": "6e",
            "non_operational": True,
            "in_memory_only": True,
        },
    }

    structured_justification = {
        "justification_id": f"justification::{fixture_id}",
        "justification_type": "TRANSITION_ACTOR_TRACEABILITY",
        "provided_by": actor_user_id,
        "reason_code": "ISOLATED_TEST_FIXTURE_JUSTIFICATION",
        "reason_detail": "in-memory fixture metadata only",
        "related_field": "transition_actor_user_id",
        "target_type": target_type,
        "target_id": target_id,
        "repair_category": repair_category,
        "audit_context": {
            "source": "continuity_kernel_test_fixtures",
            "phase": "6e",
            "non_operational": True,
            "in_memory_only": True,
        },
    }

    return {
        "evidence_packet": evidence_packet,
        "authorization_decision": authorization_decision,
        "apply_transition": apply_transition,
        "rollback_verification": rollback_verification,
        "structured_override": structured_override,
        "structured_justification": structured_justification,
        "validator_result": {},
    }


def build_valid_workspace_membership_approval_fixture() -> dict:
    return _build_valid_approval_fixture(
        fixture_id="workspace-membership",
        actor_user_id="ops-fixture-actor",
        actor_role="operations_admin",
        repair_category="workspace_membership_repair",
        target_type="workspace",
        target_id="ws-phase6e-001",
    )


def build_valid_viewer_readiness_approval_fixture() -> dict:
    return _build_valid_approval_fixture(
        fixture_id="viewer-readiness",
        actor_user_id="ops-viewer-actor",
        actor_role="operations_admin",
        repair_category="viewer_readiness_repair",
        target_type="viewer_manifest",
        target_id="viewer-phase6e-001",
    )


def build_valid_billing_order_approval_fixture() -> dict:
    return _build_valid_approval_fixture(
        fixture_id="billing-order",
        actor_user_id="finance-fixture-actor",
        actor_role="finance_admin",
        repair_category="billing_order_payment_repair",
        target_type="order",
        target_id="order-phase6e-001",
    )


__all__ = [
    "build_valid_workspace_membership_approval_fixture",
    "build_valid_viewer_readiness_approval_fixture",
    "build_valid_billing_order_approval_fixture",
]
