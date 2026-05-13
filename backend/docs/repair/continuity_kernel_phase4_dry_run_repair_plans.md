# Tomb of Light Continuity Kernel — Phase 4 Dry-Run Repair Plans

Status: documentation-only dry-run repair planning. No runtime service logic changes, no route changes, no database behavior changes, and no production data mutation.

## Global Safety Baseline
- Dry-run is the default for every repair category in this phase.
- Future `--apply` behavior is out of scope for Phase 4 and may only be introduced in a future approved implementation.
- Officer-policy approval is required before any future `--apply` mode can execute.
- Every repair plan must include a scoped target selector (for example project, order, workspace, certificate, or mint record identifier constraints).
- Every repair plan must remain idempotent when re-run against unchanged source data.
- Every repair plan must include rollback notes before any future apply-mode implementation is considered.
- Every repair plan must remain tied to audit logging with actor/action/target/context fields.
- Required dry-run output is explicit before/after diff data and blocked-reason details where applicable.

## 1) Missing Entitlement Repair Plan
- Detection scope: paid order exists with no corresponding project entitlement.
- Normalize package identity before proposing any correction (`package_code`, `package_slug`, `package_lane`).
- Validate project/user/email correlation before producing a proposal.
- Dry-run output only: proposed entitlement diff with target selectors and validation notes.
- No write operation is allowed unless a future approved `--apply` flow exists.
- Idempotency notes: repeated dry-run executions produce the same proposed diff when source records are unchanged.
- Rollback notes: future apply-mode rollback must restore previous entitlement linkage snapshot.
- Audit event required for each dry-run execution with actor/action/target/context.

## 2) Package/Lane Normalization Repair Plan
- Detection scope: `package_code`/`package_slug`/`package_lane` drift across continuity records.
- Dry-run output: explicit before/after normalized package values.
- Preserve canonical source-of-truth boundaries in `package_catalog` and `package_mapping`.
- Idempotency notes: normalized outputs remain stable across repeated dry-runs.
- Rollback notes: future apply-mode rollback must restore prior package identity values.
- Audit event required for each dry-run execution with actor/action/target/context.

## 3) Workspace/Co-Owner Membership Repair Plan
- Detection scope: owner/co_owner/member access inconsistency.
- Preserve `project_members` as the source of truth.
- Do not overwrite active members while evaluating inconsistencies.
- Dry-run output: before/after membership diff with scoped target selector.
- Idempotency notes: unchanged membership inputs yield unchanged dry-run outputs.
- Rollback notes: future apply-mode rollback must restore pre-repair membership state.
- Audit event required for each dry-run execution with actor/action/target/context.

## 4) Viewer Manifest Readiness Repair Plan
- Detection scope: missing or stale viewer manifest readiness signals.
- Do not rebuild production viewer payload in Phase 4.
- Dry-run output: expected inputs, readiness gaps, and blocked reasons.
- Idempotency notes: repeated dry-runs with unchanged readiness inputs produce identical blocked/output summaries.
- Rollback notes: future apply-mode rollback must reinstate prior readiness signaling snapshot.
- Audit event required for each dry-run execution with actor/action/target/context.

## 5) Certificate Issuance Consistency Repair Plan
- Detection scope: generated certificate payload versus issued certificate boundary drift.
- Do not mutate immutable issued certificates.
- Propose versioned correction metadata only in dry-run output.
- Dry-run output: before/after boundary diff and version-correction proposal details.
- Idempotency notes: repeated dry-runs must not introduce additional proposed mutations for unchanged records.
- Rollback notes: future apply-mode rollback must restore prior version-reference linkage without rewriting immutable issued artifacts.
- Audit event required for each dry-run execution with actor/action/target/context.

## 6) Mint Readiness Repair Plan
- Detection scope: mint readiness mismatch between readiness, eligibility, and approval states.
- Do not queue mint work directly from a repair plan.
- Dry-run output: readiness mismatch diff, required gate checks, and blocked reasons.
- Require readiness/eligibility/approval gate checks before any future apply consideration.
- Idempotency notes: unchanged readiness inputs return identical dry-run mismatch results.
- Rollback notes: future apply-mode rollback must restore prior readiness-state references.
- Audit event required for each dry-run execution with actor/action/target/context.

## 7) Admin Repair Safety Plan
- Applies to all repair categories in this document.
- Required controls:
  - dry-run default
  - explicit future `--apply` mode only after officer-policy approval
  - scoped target selector
  - idempotency notes
  - rollback notes
  - audit actor/action/target/context requirements
- Phase 4 remains dry-run-only planning and verification; no executable repair script or live apply pathway is created here.
