# Continuity Kernel Phase 6D: Staging Payload Alignment

## 1. Purpose

- improve isolated staging payload consistency
- keep read-only helper useful while preserving fail-closed behavior
- keep no runtime wiring
- keep no DB access
- keep no apply mode

## 2. Alignment rules

- evidence_packet, authorization_decision, apply_transition, and rollback_verification must share evidence_packet_id where appropriate
- target_type and target_id must match across packet, authorization, and rollback
- repair_category must match across packet and authorization
- authorization_decision placeholder must remain not approved unless explicitly supplied as valid in-memory test input
- apply_transition placeholder must never be apply_executed
- rollback_verification must reference before_snapshot or before_snapshot_ref
- idempotency_key must not be blank
- audit_context must exist
- allowed_actions must remain empty when validator fails

## 3. Non-operational guardrail

- Phase 6D does not wire runtime routes.
- Phase 6D does not wire services.
- Phase 6D does not create admin UI actions.
- Phase 6D does not create apply mode.
- Phase 6D does not create repair scripts.
- Phase 6D does not touch live data.
