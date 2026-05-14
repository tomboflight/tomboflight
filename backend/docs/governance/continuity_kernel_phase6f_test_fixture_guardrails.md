# Continuity Kernel Phase 6F: Test-Fixture Isolation Guardrails

## 1. Purpose

- protect approval_fixture_payload from production/runtime misuse
- preserve valid fixture tests
- keep no runtime wiring
- keep no apply mode
- keep no DB access

## 2. Fixture input guardrail

- approval_fixture_payload is test-only
- approval_fixture_payload must require explicit test_context=True or equivalent isolated test marker
- without explicit test marker, helper must fail closed or ignore fixture payload
- fixture payloads are not production approvals
- fixture payloads are not admin approvals
- fixture payloads are not database records
- fixture payloads are not apply authorization
- fixture payloads must not be accepted from user input

## 3. Required fail-closed behavior

- approval_fixture_payload without test marker fails closed
- approval_fixture_payload with invalid test marker fails closed
- approval_fixture_payload with test marker but invalid fixture fails closed
- feature flag still required even for fixture preview path
- prohibited actions remain prohibited
- no DB writes
- no mint queueing
- no certificate/customer mutation

## 4. Non-operational guardrail

- Phase 6F does not wire runtime routes.
- Phase 6F does not wire services.
- Phase 6F does not create admin UI actions.
- Phase 6F does not create apply mode.
- Phase 6F does not create repair scripts.
- Phase 6F does not touch live data.
