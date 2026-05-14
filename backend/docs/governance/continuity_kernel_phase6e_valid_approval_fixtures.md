# Continuity Kernel Phase 6E: Valid In-Memory Approval Fixtures

## 1. Purpose

- define valid in-memory approval fixtures for testing only
- improve read-only preview testing
- keep no runtime wiring
- keep no DB access
- keep no apply mode
- keep no repair execution

## 2. Fixture scope

- fixtures are in-memory only
- fixtures are not production approvals
- fixtures are not admin approvals
- fixtures are not database records
- fixtures are not apply authorization
- fixtures must not be accepted from user input

## 3. Required fixture components

- evidence_packet
- authorization_decision
- apply_transition
- rollback_verification
- structured_override if needed
- structured_justification if needed

## 4. Valid approval fixture rules

- authorization_decision may be approved only in isolated tests
- actor_role must be canonical and allowed for repair_category
- approved_by must match authorization actor
- apply_transition must use allowed transition only
- rollback_verification must match target and evidence_packet_id
- idempotency_key must be non-blank
- audit_context must exist
- no prohibited actions may appear

## 5. Prohibited fixture behavior

- fixtures must not create apply mode
- fixtures must not create repair scripts
- fixtures must not mutate data
- fixtures must not queue mint work
- fixtures must not mutate certificates
- fixtures must not delete customer records
- fixtures must not bypass validator
- fixtures must not bypass audit

## 6. Non-operational guardrail

- Phase 6E does not wire runtime routes.
- Phase 6E does not wire services.
- Phase 6E does not create admin UI actions.
- Phase 6E does not create apply mode.
- Phase 6E does not create repair scripts.
- Phase 6E does not touch live data.
