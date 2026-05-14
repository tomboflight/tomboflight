# Continuity Kernel Phase 5G: Canonical Payload Placement

Phase 5G defines canonical payload placement rules for future Continuity Kernel producers before any runtime wiring or apply-mode work.

## Canonical top-level payload keys

- evidence_packet
- authorization_decision
- apply_transition
- rollback_verification
- structured_override
- structured_justification
- validator_result

## Canonical nesting rules

- evidence_packet is required for any future apply validation request.
- authorization_decision is required before apply validation can pass.
- apply_transition is required before apply validation can pass.
- rollback_verification is required for any apply request that can affect stored state.
- structured_override must live at top-level key structured_override when used.
- structured_justification must live at top-level key structured_justification when used.
- validator_result must never be accepted as user input for approval; it is output only.

## Producer responsibilities

Future producers may create only the following canonical payload entries:

- dry_run_engine may create evidence_packet.
- authorization_policy may create authorization_decision.
- state_machine may create apply_transition.
- rollback_planner may create rollback_verification.
- officer_review may create structured_override.
- reviewer_notes may create structured_justification.
- continuity_kernel_validator may create validator_result.

## Forbidden producer behavior

- frontend must not create approved authorization_decision.
- frontend must not create validator_result.
- admin UI must not bypass validator.
- dry_run_engine must not create apply_executed transition.
- repair scripts must not create apply-mode payloads without governance.
- no producer may place structured_override inside free-text audit_context.
- no producer may place structured_justification inside free-text audit_context.
- no producer may use legacy free-text override phrases as approval.

## Migration strategy

- Phase A: accept no producer input yet; documentation only.
- Phase B: emit dry-run evidence_packet in staging only.
- Phase C: emit authorization_decision from policy layer only.
- Phase D: emit apply_transition from state machine only.
- Phase E: emit rollback_verification from rollback planner only.
- Phase F: require structured_override / structured_justification for exceptions.
- Phase G: reject legacy free-text override phrases.

## Backward compatibility

- Existing routes must not change in Phase 5G.
- Existing admin actions must not change in Phase 5G.
- Existing repair scripts must not change in Phase 5G.
- Existing customer portal behavior must not change in Phase 5G.
- Existing data records must not be migrated in Phase 5G.

## Non-operational guardrail

- Phase 5G does not wire the validator into runtime routes.
- Phase 5G does not create apply mode.
- Phase 5G does not create repair scripts.
- Phase 5G does not touch live data.
- Phase 5G only defines canonical payload placement and tests the documentation.
