## Continuity Kernel Phase 5R: Phase 6 PR Checklist and Stop Criteria

### 1. Purpose

Phase 5R creates the required checklist for any future Phase 6 PR.

It exists to ensure Phase 6 stays read-only-first, prevent accidental apply mode, prevent database writes, prevent repair execution, and prevent customer-facing exposure.

### 2. Required Phase 6 PR evidence

Every Phase 6 PR must include:

- feature flag name
- proof feature flag default is off
- proof production default is off
- changed file list
- route/service/admin wiring scope
- proof wiring is read-only
- proof no apply mode exists
- proof no repair scripts were created
- proof no database write calls were added
- proof no mint queueing was added
- proof no certificate mutation was added
- proof no customer record mutation was added
- test output
- rollback plan
- manual QA plan
- explicit owner approval

### 3. Required Phase 6 tests

Every Phase 6 PR must include tests proving:

- feature flag off returns unavailable/disabled response
- feature flag on in test/staging returns read-only preview only
- no prohibited actions returned
- no DB write methods called
- no mint queueing called
- no apply/schedule/execute/rollback actions exposed
- no full rollback_plan exposed
- no full override/justification audit_context exposed
- no customer-facing route exposed
- architecture tests pass
- contract tests pass
- CI guardrails pass

### 4. Phase 6 stop criteria

Immediately stop/reject Phase 6 PR if:

- apply mode appears
- repair script appears
- DB write method appears
- mint queueing appears
- certificate mutation appears
- customer mutation appears
- frontend customer exposure appears
- feature flag defaults on
- production default can be on accidentally
- validator_result is accepted as user approval input
- prohibited actions appear in preview
- admin preview exposes full sensitive rollback/override/justification payloads
- Kernel modules are wired outside the approved read-only path

### 5. Phase 6 rollback criteria

A Phase 6 PR must include:

- how to disable the feature flag
- how to remove the route/helper safely
- how to confirm no data was mutated
- how to confirm no jobs were queued
- how to confirm no audit/apply state was created
- how to run architecture and contract tests after rollback

### 6. Phase 6 allowed file scope

Future Phase 6 may only consider:

- one read-only route/helper file or one existing admin route extension
- isolated preview module usage
- tests for disabled/enabled read-only behavior
- docs update

No frontend changes unless separately approved.

### 7. Non-operational guardrail

- Phase 5R does not implement Phase 6.
- Phase 5R does not wire runtime routes.
- Phase 5R does not create apply mode.
- Phase 5R does not create repair scripts.
- Phase 5R does not touch live data.
- Phase 5R only defines the Phase 6 PR checklist and tests the checklist.
