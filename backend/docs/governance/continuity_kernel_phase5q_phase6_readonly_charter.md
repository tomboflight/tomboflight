## Continuity Kernel Phase 5Q: Phase 6 Read-Only Wiring Charter

### 1. Purpose

Phase 5Q defines the first safe Phase 6 runtime/admin integration path and approval charter.

Phase 6 must proceed read-only-first.

The following are explicitly prohibited in Phase 6 until separately approved in a later phase:

- apply mode
- repair execution
- database writes
- customer data mutation
- mint queueing
- certificate mutation

### 2. Phase 6 allowed scope

Only the following scope is allowed for the first Phase 6 step:

- read-only admin preview only
- feature-flagged
- disabled by default
- no customer-facing exposure
- no apply/schedule/execute/rollback action
- no database writes
- no repair script creation
- no mutation of entitlement, workspace, certificate, mint, or customer records

### 3. Phase 6 feature flag requirements

Before implementation, the feature flag contract must be documented and approved:

- flag name must be documented before implementation
- default must be false/off
- production default must be off
- staging may enable only after explicit approval
- flag must guard every runtime/admin preview path
- no apply-related path may be enabled by the flag

### 4. Phase 6 first allowed integration

A read-only admin preview endpoint or internal admin helper may be considered for first integration only.

That first integration:

- must call isolated preview shaping only
- must return read-only preview object only
- must not call database write methods
- must not alter state
- must not enqueue jobs
- must not create audit mutations yet unless separately approved
- must not expose full sensitive rollback/override/justification payloads

### 5. Phase 6 required approval gate

Before implementation, a PR must prove all of the following:

- route/service wiring scope is read-only
- feature flag default is off
- no apply/repair execution path exists
- no DB write methods are called
- no mint queueing exists
- no certificate/customer mutation exists
- no frontend/admin button triggers mutation
- tests prove disabled-by-default behavior
- tests prove no prohibited actions are returned

### 6. Phase 6 prohibited behavior

The following behavior remains prohibited:

- approve_apply
- schedule_apply
- execute_apply
- rollback_apply
- mutate_entitlement
- mutate_workspace_member
- mutate_certificate
- queue_mint
- delete_customer_record
- bypass_validator
- bypass_audit
- automatic apply after dry-run
- accepting validator_result as user input approval

### 7. Phase 6 testing requirements

Before and during any approved read-only integration work:

- architecture tests must pass
- contract tests must pass
- CI guardrails must pass
- new read-only integration tests must prove feature flag off behavior
- new read-only integration tests must prove no prohibited actions
- new read-only integration tests must prove no DB writes

### 8. Non-operational guardrail

- Phase 5Q does not implement Phase 6.
- Phase 5Q does not wire runtime routes.
- Phase 5Q does not create apply mode.
- Phase 5Q does not create repair scripts.
- Phase 5Q does not touch live data.
- Phase 5Q only defines the Phase 6 read-only wiring charter and tests the charter.
