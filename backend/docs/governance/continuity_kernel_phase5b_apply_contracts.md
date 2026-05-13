# Tomb of Light Continuity Kernel — Phase 5B Apply-Mode Implementation Contracts

Status: design/test-only contract specification for future apply-mode implementation. This phase does not enable runtime apply behavior.

## 1) Authorization Contract
Future apply-mode authorization must enforce all checks below:
- actor must be authenticated
- actor must have approved role
- actor cannot approve their own apply request unless CEO/SUPERADMIN emergency override is documented
- CMO/marketing_admin cannot approve repair execution
- officer role must match repair category
- superadmin-only categories must require SUPERADMIN
- executor must be separate from requester when risk level is high

## 2) Evidence Packet Contract
Future apply-mode evidence packets must include this object shape and all required fields:
- dry_run_id
- evidence_packet_id
- actor_user_id
- requested_by
- reviewed_by
- approved_by
- executed_by
- approval_role
- target_type
- target_id
- repair_category
- before_snapshot
- proposed_after_snapshot
- diff_summary
- blocked_reasons
- risk_level
- rollback_plan
- idempotency_key
- created_at
- approved_at
- executed_at
- audit_context

## 3) Approval Workflow Contract
Future apply-mode state transitions are restricted to the allowed transitions below:
- dry_run_created -> review_requested
- review_requested -> officer_reviewing
- officer_reviewing -> approved_for_apply
- officer_reviewing -> rejected
- approved_for_apply -> apply_scheduled
- apply_scheduled -> apply_executed
- apply_scheduled -> apply_failed
- apply_failed -> rollback_required
- rollback_required -> rollback_completed
- apply_executed -> audit_closed
- rollback_completed -> audit_closed

## 4) Apply Executor Contract
Future apply executors must enforce these guardrails:
- must verify evidence packet before execution
- must verify approval state is approved_for_apply or apply_scheduled
- must verify idempotency key has not already been consumed
- must write audit event before and after execution
- must never queue mint work directly
- must never mutate immutable issued certificates
- must never delete customer records
- must never bypass auth, entitlement, verification, mint readiness, audit logging, or officer permissions

## 5) Rollback Verification Contract
Future rollback flow must enforce all requirements below:
- rollback plan must exist before apply
- rollback plan must reference before_snapshot
- rollback must not delete audit logs
- rollback must create a new audit event
- rollback must not mutate immutable certificate artifacts
- rollback must verify target selector still matches intended record

## 6) Audit Transition Contract
Every future apply-mode state transition must include:
- actor_user_id
- action
- target_type
- target_id
- previous_state
- next_state
- repair_category
- evidence_packet_id
- audit_context
- timestamp

## 7) Non-Implementation Guardrail
- Phase 5B does not implement apply mode.
- Phase 5B does not create repair scripts.
- Phase 5B does not modify runtime services.
- Phase 5B only defines future implementation contracts and tests the contract documentation.
