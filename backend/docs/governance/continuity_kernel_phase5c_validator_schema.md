# Tomb of Light Continuity Kernel — Phase 5C Validator/Schema Design

Status: design/test-only validator/schema specification for future apply-mode governance. This phase does not enable runtime apply behavior.

## 1) EvidencePacketSchema
Future non-runtime validation schema must require all fields below:
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

## 2) AuthorizationDecisionSchema
Future non-runtime validation schema must require all fields below:
- actor_user_id
- actor_role
- requested_action
- repair_category
- target_type
- target_id
- decision
- reason_codes
- policy_source
- evaluated_at

## 3) ApplyStateTransitionSchema
Future non-runtime validation schema must require all fields below:
- evidence_packet_id
- previous_state
- next_state
- actor_user_id
- action
- transition_allowed
- reason_codes
- timestamp
- audit_context

## 4) RollbackVerificationSchema
Future non-runtime validation schema must require all fields below:
- evidence_packet_id
- rollback_plan
- before_snapshot_ref
- target_type
- target_id
- verification_status
- reason_codes
- verified_at
- audit_context

## 5) ValidatorResultSchema
Future non-runtime validation schema must require all fields below:
- validator_name
- passed
- reason_codes
- errors
- warnings
- evaluated_at

## 6) Fail-Closed Validation Rules
Future validators must fail closed under all conditions below:
- fail closed if required fields are missing
- fail closed if apply state transition is not allowed
- fail closed if CMO/marketing_admin attempts approval
- fail closed if idempotency_key is already consumed
- fail closed if rollback_plan is missing
- fail closed if immutable issued certificate mutation is requested
- fail closed if mint queueing is requested directly from repair
- fail closed if customer record deletion is requested
- fail closed if audit_context is missing
- fail closed if actor role does not match repair category

## 7) Non-Implementation Guardrail
- Phase 5C does not implement validators in runtime code.
- Phase 5C does not create repair scripts.
- Phase 5C does not modify backend/app schemas.
- Phase 5C only documents future validation schemas and tests the documentation.
