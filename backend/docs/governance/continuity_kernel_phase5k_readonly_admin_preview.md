# Continuity Kernel Phase 5K: Read-Only Admin Preview Contract

Phase 5K defines a read-only Admin Control Center preview contract for future Continuity Kernel dry-run evidence and validator results.

## 1. Read-only preview purpose

The Admin Control Center preview exists only to present non-operational dry-run review data.

- display dry-run evidence summary
- display validator_result summary
- display blocked reasons
- display risk level
- display target selector
- display rollback plan summary
- display structured_override summary if present
- display structured_justification summary if present
- display governance state
- never execute repairs
- never approve apply
- never schedule apply
- never mutate data

## 2. Preview input contract

The read-only preview contract accepts these top-level inputs:

- evidence_packet
- authorization_decision
- apply_transition
- rollback_verification
- structured_override
- structured_justification
- validator_result

## 3. Preview output contract

The read-only preview contract produces these top-level preview fields:

- preview_id
- target_type
- target_id
- repair_category
- risk_level
- status
- blocked_reasons
- errors
- warnings
- diff_summary
- rollback_summary
- override_summary
- justification_summary
- validator_passed
- allowed_actions

## 4. Allowed read-only actions

- view_preview
- copy_case_summary
- export_dry_run_summary
- request_review

## 5. Prohibited actions

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

## 6. Admin preview status values

- preview_ready
- blocked
- invalid_payload
- missing_evidence
- validation_failed
- review_required

## 7. Officer visibility rules

- SUPERADMIN may view all preview categories
- EXECUTIVE_TECH_ADMIN may view technical repair previews
- operations_admin may view workspace/upload/viewer/readiness previews
- finance_admin may view billing/order/payment previews
- marketing_admin may not view repair execution preview actions
- CMO/marketing_admin cannot approve or execute anything from preview

## 8. Non-operational guardrail

- Phase 5K does not wire preview into admin UI.
- Phase 5K does not create backend routes.
- Phase 5K does not create apply mode.
- Phase 5K does not create repair scripts.
- Phase 5K does not touch live data.
- Phase 5K only defines read-only preview contracts and tests.
