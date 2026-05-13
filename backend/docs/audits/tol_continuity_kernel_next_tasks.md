# Tomb of Light Continuity Kernel — Safe Next Tasks

## Phase 0: audit only
- [ ] Freeze implementation changes; continue inventory/risk mapping only.
- [ ] Confirm package map, role map, entitlement service, manifest builder, and repair-surface ownership boundaries.
- [ ] Record overlap risks without deleting or merging files.

## Phase 1: documentation
- [ ] Publish kernel component contracts (inputs/outputs, invariants, owners).
- [ ] Document canonical source-of-truth per domain (identity, entitlement, workspace, manifest, certificate, mint, audit).
- [ ] Document policy gate reason codes and expected HTTP behaviors.

## Phase 2: architecture tests
- [ ] Add non-invasive architecture tests that assert gate enforcement (auth/entitlement/workspace roles).
- [ ] Add tests for no-bypass behavior on admin/repair/mint endpoints.
- [ ] Add tests that assert viewer/public manifest separation of concerns.

## Phase 3: schema/contract verification
- [ ] Validate collection/document contracts used by kernel boundaries.
- [ ] Verify backward-compatible route contracts for workspace context and entitlement payloads.
- [ ] Verify audit record contract completeness across critical action types.

## Phase 4: dry-run repair plans
- [ ] Build dry-run-only repair plans with explicit diff output and rollback notes.
- [ ] Validate idempotency and scope constraints in staging/sandbox data only.
- [ ] Require officer-policy approvals before any apply mode.

## Phase 5: approved implementation
- [ ] Implement kernel orchestration incrementally behind existing policy gates.
- [ ] Roll out domain by domain with targeted regression tests and audit validation.
- [ ] Enable production changes only after explicit approval and signed-off dry-run evidence.
