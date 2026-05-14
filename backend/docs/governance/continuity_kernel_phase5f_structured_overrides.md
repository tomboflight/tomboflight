# Continuity Kernel Phase 5F: Structured Overrides and Justifications

Phase 5F hardens the isolated Continuity Kernel validator by replacing text-signal override/justification handling with structured contracts.

## StructuredOverrideSchema

Required fields:
- override_id
- override_type
- requested_by
- approved_by
- approval_role
- reason_code
- reason_detail
- target_type
- target_id
- repair_category
- risk_level
- expires_at
- audit_context

## StructuredJustificationSchema

Required fields:
- justification_id
- justification_type
- provided_by
- reason_code
- reason_detail
- related_field
- target_type
- target_id
- repair_category
- audit_context

## Allowed override types
- SUPERADMIN_EMERGENCY_OVERRIDE
- CEO_APPROVED_FINANCE_OVERRIDE
- APPROVER_IDENTITY_MISMATCH_OVERRIDE
- HIGH_RISK_SAME_ACTOR_OVERRIDE

## Allowed justification types
- APPROVED_BY_ACTOR_MISMATCH
- TRANSITION_ACTOR_TRACEABILITY
- ROLLBACK_REFERENCE_JUSTIFICATION
- FINANCE_TECH_SCOPE_JUSTIFICATION

## Structured override rules
- override must be a dictionary/object, not a free-text phrase
- override must include override_id
- override must include approved_by
- override must include approval_role
- override approval_role must be SUPERADMIN or CEO-equivalent for emergency override
- override must match target_type, target_id, and repair_category
- override must include risk_level
- override must include reason_code and reason_detail
- override must include audit_context
- expired overrides must fail closed
- unknown override_type must fail closed
- marketing_admin/CMO cannot create or approve overrides
- override must never allow mint queueing directly from repair
- override must never allow immutable issued certificate mutation
- override must never allow customer record deletion

## Structured justification rules
- justification must be a dictionary/object, not a free-text phrase
- justification must include justification_id
- justification must include provided_by
- justification must include reason_code and reason_detail
- justification must match target_type, target_id, and repair_category
- justification must include audit_context
- unknown justification_type must fail closed
- marketing_admin/CMO justification cannot approve repair execution
- justification cannot override prohibited actions

## Non-operational guardrail
- Phase 5F does not wire the validator into runtime routes.
- Phase 5F does not create apply mode.
- Phase 5F does not create repair scripts.
- Phase 5F does not touch live data.
- Phase 5F only strengthens isolated validation and tests.
