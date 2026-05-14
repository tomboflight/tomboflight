# Continuity Kernel Phase 5I: Staging-Only Dry-Run Adapter Contract

Phase 5I defines a staging-only dry-run adapter contract for assembling canonical Continuity Kernel payloads from in-memory dry-run inputs.

## 1. Staging-only adapter purpose

The staging-only dry-run adapter exists to assemble canonical payloads for validation and governance checks.

- assemble canonical payloads for validation
- never execute repairs
- never write to database
- never queue mint work
- never mutate certificates
- never alter customer records
- never call production services
- never bypass governance

## 2. Adapter inputs

The adapter accepts only supplied in-memory dry-run inputs:

- dry_run_source
- target_selector
- actor_context
- repair_category
- before_snapshot
- proposed_after_snapshot
- diff_summary
- blocked_reasons
- rollback_plan
- structured_override
- structured_justification

## 3. Adapter outputs

The adapter assembles staging-only dry-run outputs using canonical top-level keys:

- evidence_packet
- authorization_decision placeholder
- apply_transition placeholder
- rollback_verification placeholder
- validator_result placeholder

## 4. Staging-only restrictions

- adapter output is not approval
- adapter output is not apply authorization
- adapter output is not a repair script
- adapter output is not a database migration
- adapter output is not a customer-facing artifact
- adapter output cannot be used to queue mint work
- adapter output cannot be used to mutate issued certificates

## 5. Producer migration boundary

Producer ownership remains separated across migration boundaries:

- dry_run_engine may produce dry_run_source
- adapter may assemble evidence_packet only from supplied in-memory inputs
- authorization_policy must produce authorization_decision separately
- state_machine must produce apply_transition separately
- rollback_planner must produce rollback_verification separately
- officer_review must produce structured_override separately
- reviewer_notes must produce structured_justification separately
- continuity_kernel_validator produces validator_result

## 6. Non-operational guardrail

- Phase 5I does not wire the adapter into runtime routes.
- Phase 5I does not create apply mode.
- Phase 5I does not create repair scripts.
- Phase 5I does not touch live data.
- Phase 5I only defines staging-only adapter contracts and tests.
