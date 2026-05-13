# Tomb of Light Continuity Kernel — Phase 5A Apply-Mode Governance

Status: governance-only planning for future apply-mode controls. No runtime service logic changes, no route changes, no database behavior changes, and no production data mutation.

## 1) Apply-Mode Governance Principle
- Dry-run remains the default for Continuity Kernel repair workflows.
- Apply mode is never automatic.
- Apply mode must never be automatic after dry-run.
- Apply mode must require explicit officer authorization.
- Apply mode must require prior dry-run evidence.
- Apply mode must be scoped to a target selector.
- Apply mode must be idempotent.
- Apply mode must produce audit evidence.

## 2) Officer Approval Matrix
Roles in scope:
- CEO / SUPERADMIN
- EXECUTIVE_TECH_ADMIN
- COO / operations_admin
- CFO / finance_admin
- CMO / marketing_admin

Approval rules:
- CEO / SUPERADMIN may approve all repair categories.
- EXECUTIVE_TECH_ADMIN may approve technical repair categories but may not approve finance-only repair decisions unless CEO-approved.
- COO / operations_admin may approve operations, workspace, upload, and readiness repairs but may not approve finance ownership, mint execution, or superadmin changes.
- CFO / finance_admin may approve billing, order, and payment-related repairs but may not approve workspace, mint execution, or lineage changes.
- CMO / marketing_admin cannot approve repair execution.

## 3) Repair Category Authorization
### Missing entitlement repair
- Request: technical operators and authorized admin reviewers.
- Review: technical review panel.
- Approve: CEO / SUPERADMIN or EXECUTIVE_TECH_ADMIN.
- Execute (future apply mode only): authorized repair executor after approval and evidence checks.

### Package/lane normalization
- Request: technical operators and authorized admin reviewers.
- Review: technical review panel.
- Approve: CEO / SUPERADMIN or EXECUTIVE_TECH_ADMIN.
- Execute (future apply mode only): authorized repair executor after approval and evidence checks.

### Workspace/co-owner membership repair
- Request: operations_admin, workspace operators, and technical operators.
- Review: operations + technical review.
- Approve: CEO / SUPERADMIN, EXECUTIVE_TECH_ADMIN, or operations_admin (within permitted scope).
- Execute (future apply mode only): authorized repair executor after approval and evidence checks.

### Viewer manifest readiness repair
- Request: operations_admin and technical operators.
- Review: readiness review team.
- Approve: CEO / SUPERADMIN, EXECUTIVE_TECH_ADMIN, or operations_admin (within permitted scope).
- Execute (future apply mode only): authorized repair executor after approval and evidence checks.

### Certificate issuance consistency repair
- Request: technical operators and certificate governance reviewers.
- Review: technical + governance review.
- Approve: CEO / SUPERADMIN or EXECUTIVE_TECH_ADMIN.
- Execute (future apply mode only): authorized repair executor after approval and evidence checks.

### Mint readiness repair
- Request: technical operators and readiness reviewers.
- Review: readiness + technical review.
- Approve: CEO / SUPERADMIN or EXECUTIVE_TECH_ADMIN.
- Execute (future apply mode only): authorized repair executor after approval and evidence checks.

### Admin repair safety
- Request: senior technical operators only.
- Review: admin safety review panel.
- Approve: CEO / SUPERADMIN only.
- Execute (future apply mode only): explicitly authorized repair executor after approval and evidence checks.

### Billing/order linkage repair
- Request: finance_admin and technical operators.
- Review: finance + technical review.
- Approve: CEO / SUPERADMIN or finance_admin (within permitted billing/order/payment scope).
- Execute (future apply mode only): authorized repair executor after approval and evidence checks.

### Audit record correction metadata
- Request: audit/governance operators.
- Review: governance review panel.
- Approve: CEO / SUPERADMIN; EXECUTIVE_TECH_ADMIN only for technical metadata corrections; finance_admin only for finance metadata scope.
- Execute (future apply mode only): authorized repair executor after approval and evidence checks.

## 4) Required Apply-Mode Evidence Packet
Every future apply request must include all fields below:
- dry_run_id
- actor_user_id
- requested_by
- approved_by
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
- timestamp
- audit_context

## 5) Prohibited Apply Actions
The following actions are prohibited:
- Automatic apply after dry-run.
- Apply without officer approval.
- Apply without audit logging.
- Apply without rollback notes.
- Apply without scoped target selector.
- Mutating immutable issued certificates.
- Queueing mint work directly from a repair action.
- Bypassing auth, entitlement, verification, mint readiness, audit logging, or officer permissions.
- Deleting customer records as part of repair.
- Hard-coding customer-specific production values.

## 6) Apply-Mode State Machine
Future allowed states:
- dry_run_created
- review_requested
- officer_reviewing
- approved_for_apply
- rejected
- apply_scheduled
- apply_executed
- apply_failed
- rollback_required
- rollback_completed
- audit_closed

## 7) Audit Evidence Requirements
Every future apply-mode state transition must write audit actor/action/target/context evidence with sufficient context to trace requester, reviewer, approver, executor, target selector, and outcome.

## 8) Rollback Governance
Rollback is a first-class governance plan, not an afterthought:
- Rollback must be generated before apply.
- Rollback must use prior snapshot references.
- Rollback must not mutate immutable certificate artifacts.
- Rollback must not reverse audit logs.
- Rollback itself must create a new audit event.

## 9) Phase 5A Non-Implementation Guardrail
- This phase does not implement apply mode.
- This phase does not create repair scripts.
- This phase does not modify runtime services.
- This phase only defines governance and tests the governance documentation.
