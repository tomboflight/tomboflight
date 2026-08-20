# Continuity Kernel Phase 8 — Operational Runtime

## Decision

Phase 8 replaces the test-only posture for covered admin repairs with an
operational, authenticated execution surface. The earlier read-only preview
route remains available for historical compatibility, but it is no longer the
only Kernel runtime.

The operational runtime is implemented by:

- `backend/app/services/continuity_runtime_service.py`
- `backend/app/routes/admin_continuity_runtime.py`
- `admin-control-center.html`
- `admin-control-center.js`

Runtime version: `8.0.0`.

## What changed from Phases 5–7

The Phase 5 validator, role/category taxonomy, evidence packet, structured
override, and state-transition contracts are now used before an allow-listed
domain write is invoked. The Phase 6 read-only feature flag is not reused as
an execution flag. The Phase 7 staging records remain historical evidence and
do not authorize or block Phase 8 requests.

Phase 8 persists two operational collections:

- `continuity_operations`: request, approval, snapshots, validator result,
  execution result, and lifecycle state.
- `continuity_events`: append-only operation event records.

Unique indexes enforce operation identity, event identity, and idempotency-key
identity. The API creates these indexes during normal database startup.

## Execution posture

Execution is enabled unless the emergency environment variable
`CONTINUITY_EXECUTION_KILL_SWITCH` is explicitly set to `1`, `true`, `yes`,
`on`, or `enabled`.

There is no timer, worker, startup repair, or automatic customer mutation in
Phase 8. A write requires an authenticated admin request, a reason, an
idempotency key, an allowed action, officer approval, evidence validation, and
an explicit execute transition.

The canonical CEO may use a one-step control-center action. It still records:

1. `review_requested`
2. `officer_reviewing`
3. `approved_for_apply`
4. `apply_scheduled`
5. `apply_executed` or `apply_failed`

High-risk same-requester execution requires the persisted
`SUPERADMIN_EMERGENCY_OVERRIDE` acknowledgement. Other officers create a
`review_requested` operation for later approval. The control center shows
recent operations and gives the canonical CEO explicit Approve + Execute and
Close Audit controls.

## Covered live actions

### Case actions

- package synchronization and normalization
- lane assignment
- paid-order linkage
- entitlement generation and refresh
- mint-review readiness repairs
- record repair and mint status reconciliation

Readiness checks and case refresh remain read operations.

### Bulk actions

- missing entitlement repair
- missing lane assignment
- unlinked paid-order repair
- broken package normalization
- mint readiness refresh
- selected-record repair
- all-safe-record repair

Bulk adapter results with nonzero failures are recorded as
`execution_outcome=partial_failure`; they are not represented as full success.

### CEO restricted actions

- package assignment/change, revocation, and restoration
- service controls
- officer permission assignment
- account lifecycle changes
- scoped case repair tools

The runtime delegates only to existing allow-listed domain services. It does
not invent paid-order evidence, mutate Stripe payment status during package
normalization, delete customer records, mutate immutable certificates, or
queue an on-chain mint directly from a repair.

## Kernel component map

| Kernel responsibility | Phase 8 runtime source |
| --- | --- |
| Identity resolver | `users`, project owner fields, canonical officer identity |
| Entitlement graph resolver | `project_entitlements`, package catalog, active add-ons |
| Workspace access resolver | `project_members`, family and household anchors |
| Lineage event ledger | family members, relationships, `continuity_events` |
| Viewer manifest compiler | upload and verification source counts plus workspace anchor |
| Readiness gate matrix | identity, paid-order, entitlement, membership, lineage, package gates |
| Certificate delivery record | latest immutable `issued_certificates` record |
| Mint readiness controller | canonical `mint_records` state |
| Officer policy layer | shared Phase 5 role/category taxonomy and authenticated permissions |
| Self-healing repair engine | allow-listed execution adapters and operation state machine |
| Audit timeline | `audit_logs`, evidence packets, snapshots, transitions, and Kernel events |

## Rollback and failure semantics

Every request captures a before snapshot and a reference-verified rollback
plan before validation. Rollback is deliberately not automatic because the
existing domain services do not share a transaction/session boundary and bulk
repairs may partially complete. An `apply_failed` or `partial_failure`
operation remains open for explicit operator review; it must not be
automatically audit-closed. If the domain write succeeds but a secondary event
or audit-log write fails, the operation remains `apply_executed` with
`evidence_recording_status=incomplete`; this avoids falsely relabeling a real
business mutation as failed while still blocking audit closure.

## Compatibility boundary

The control center routes covered mutations through the Phase 8 Kernel.
Legacy direct API endpoints remain present so existing integrations do not
break during rollout. They are a documented compatibility boundary, not proof
that every historical write surface is already Kernel-governed. A later
hardening phase can deprecate or internally redirect those endpoints after
callers are inventoried.

## Deployment verification

After deployment, an authenticated admin should verify:

- `GET /admin/control-center/kernel/status` reports runtime `8.0.0` and
  `execution_enabled=true`.
- the two unique identity indexes exist on each Kernel collection.
- a deliberate control-center action creates one operation and one ordered
  event trail for its idempotency key.
- a repeated request with that same key does not execute the domain adapter a
  second time.

Production business records must not be changed merely to prove the runtime is
reachable. The first live operation should be an already-required customer or
system repair with a real reason and scoped target.
