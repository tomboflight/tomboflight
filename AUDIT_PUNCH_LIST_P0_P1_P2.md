# Platform Reliability Punch List (P0 / P1 / P2)

Date: 2026-04-18
Scope: backend + frontend static audit follow-up for vaults, storage/uploads, cinematic view, family tree/linked tree, link-key integrity, and admin/customer boundary hardening.

## P0 — Blocker security/integrity fixes (ship before feature work)

### 1) Link-key entitlement integrity must be strict paid-order + active-entitlement

**Risk**: Link-key access can currently be inferred from project package fields, allowing access drift if project metadata is edited.

**File-level fixes**
- `backend/app/services/link_key_service.py`
  - Remove fallback access signal from raw `project` package fields in `_project_has_access_signal`.
  - Require BOTH:
    - active project entitlement document (`project_entitlements.status == active`) and
    - a valid paid package order for the same project.
  - Fail closed (`False`) when either record is missing or inconsistent.
  - Add consistency check between entitlement `package_code` and paid order package code.
- `backend/app/services/workspace_access_service.py`
  - Align entitlement resolution with the same hard requirement used by link keys so access policy is consistent across systems.
- `backend/app/routes/link_keys.py`
  - Return explicit `403` detail when entitlement/order requirement fails (instead of generic access denial).
- `backend/tests/test_household_invites_and_orders.py`
- `backend/tests/test_project_entitlement_access.py`
- `backend/tests/test_security_hardening.py`
  - Add/extend tests proving project document edits alone cannot enable link keys.

**Acceptance checks**
- Project with `project.package_code` set manually but **no** active entitlement + paid order cannot:
  - generate link key,
  - fetch active link key,
  - use existing key endpoints.
- Mismatched package data (order says A, entitlement says B) is blocked and audit-logged.
- Test command: `pytest backend/tests/test_project_entitlement_access.py backend/tests/test_household_invites_and_orders.py backend/tests/test_security_hardening.py -q`

---

### 2) Vault routes must enforce workspace entitlement/context, not auth-only

**Risk**: Vault endpoints are authenticated but not consistently gated by workspace entitlement/capabilities.

**File-level fixes**
- `backend/app/routes/vault.py`
  - Add workspace resolution (`resolve_workspace_context`) + capability checks (`require_workspace_capability`) for every vault route using `project_id` and item-derived project context.
  - Enforce workspace member role checks where needed (`require_workspace_member_role`) for create/update/share/release operations.
  - Require `project_id` for create/list endpoints and enforce context on all item-bound endpoints.
- `backend/app/services/vault_service.py`
  - Add server-side verification that item `project_id` belongs to caller’s resolved workspace context.
  - Reject cross-workspace item access even if a raw item/grant ID is known.
- `backend/tests/test_linking_tree_vault.py`
- `backend/tests/test_workspace_access_roles.py`
  - Add tests for cross-project denial and role-bound vault actions.

**Acceptance checks**
- User with access to Project A cannot read/update/grant/release vault item in Project B (even with direct item ID).
- Customer role without required workspace role cannot create grants/release rules.
- Test command: `pytest backend/tests/test_linking_tree_vault.py backend/tests/test_workspace_access_roles.py -q`

---

### 3) Vault route integrity bug: path `item_id` must match payload `vault_item_id`

**Risk**: Grant/release create routes ignore URL `item_id` and trust payload item reference.

**File-level fixes**
- `backend/app/routes/vault.py`
  - In `POST /vault/items/{item_id}/grants` and `POST /vault/items/{item_id}/release-rules`:
    - enforce `payload.vault_item_id == item_id`.
    - otherwise return `400` with deterministic error message.
  - Prefer deriving service call item ID from path and remove dual-source ambiguity.
- `backend/app/schemas/vault.py`
  - Optionally deprecate/remap `vault_item_id` in payload for these nested routes to avoid repeated IDs.
- `backend/tests/test_linking_tree_vault.py`
  - Add explicit mismatch test cases.

**Acceptance checks**
- Route rejects mismatch between path and payload item ID.
- Route succeeds when IDs match and caller is authorized.
- Test command: `pytest backend/tests/test_linking_tree_vault.py -q`

## P1 — Major reliability hardening (immediately after P0)

### 4) Upload/storage production posture and policy consistency

**File-level fixes**
- `backend/app/services/upload_service.py`
  - Complete storage abstraction usage for all write/read paths.
  - Add immutable storage reference fields (`storage_provider`, `storage_object_key`, `storage_bucket`).
- `backend/app/routes/uploads.py`
  - Ensure every list/download path enforces workspace entitlement and privacy scope checks uniformly.
  - Require signed/private download flow for all non-public assets.
- `backend/app/services/r2_storage_service.py`
  - Remove partial/optional logic paths that silently fall back to local disk in production mode.
- `backend/tests/test_upload_visibility.py`
- `backend/tests/test_asset_delivery.py`
  - Add tests for privacy scope + signed URL expiry + cross-workspace denial.

**Acceptance checks**
- No production upload path returns permanent local file URL.
- Upload metadata can be filtered by project/family/member/category reliably.
- Test command: `pytest backend/tests/test_upload_visibility.py backend/tests/test_asset_delivery.py -q`

---

### 5) Cinematic/viewer policy verification must be end-to-end strict

**File-level fixes**
- `backend/app/routes/uploads.py`
  - Validate cinematic approval endpoints against entitlement + privacy policy + family visibility.
- `backend/app/routes/experience.py`
- `backend/app/services/public_manifest_service.py`
  - Ensure viewer manifest generation excludes assets not approved for cinematic or not visible to requesting principal.
- `viewer/js/script.js`
  - Fail-safe rendering when manifest omits restricted assets (no stale-client bypass).
- `backend/tests/test_viewer_rendering_safety.py`
- `backend/tests/test_asset_delivery.py`
  - Add negative tests for unapproved/private asset leakage in cinematic payloads.

**Acceptance checks**
- Unapproved or out-of-scope assets never appear in cinematic manifest responses.
- Viewer gracefully renders partial manifests without leaking hidden IDs/paths.
- Test command: `pytest backend/tests/test_viewer_rendering_safety.py backend/tests/test_asset_delivery.py -q`

---

### 6) Family tree + linked tree reliability and policy gates

**File-level fixes**
- `backend/app/routes/family_graph.py`
- `backend/app/routes/lineage_graph.py`
- `backend/app/routes/linked_network.py`
- `backend/app/services/linked_network_service.py`
  - Centralize eligibility check for linked-family visibility and enforce it across all graph endpoints.
  - Require entitlement capability for linked household network (`can_access_linked_households`) with no project-field fallback.
- `family-graph.js`
- `tree-view.html`
  - Preserve workspace context keys in all navigation actions and fallback flows.
- `backend/tests/test_regression_workspace_and_ui.py`
- `backend/tests/test_linking_tree_vault.py`
  - Add regression tests for wrong-workspace graph reads and stale-link behavior.

**Acceptance checks**
- Linked graph endpoints return 403 for entitled=false even if tree IDs exist.
- Client cannot open a different family tree via stale URL params.
- Test command: `pytest backend/tests/test_regression_workspace_and_ui.py backend/tests/test_linking_tree_vault.py -q`

## P2 — Operational excellence and “$10M operation” readiness

### 7) Admin/customer boundary certification across all promised flows

**File-level fixes**
- `backend/app/dependencies/auth.py`
  - Finalize explicit admin-only dependency wrappers for internal control-plane routes.
- `backend/app/routes/admin_maintenance.py`
- `backend/app/routes/mint_records.py`
- `backend/app/routes/project_entitlements.py`
  - Ensure every admin route uses permission dependency, no implicit role fallback.
- `backend/tests/test_account_separation.py`
- `backend/tests/test_admin_console.py`
  - Expand matrix coverage (admin vs owner vs collaborator vs viewer).

**Acceptance checks**
- Customer tokens cannot call internal admin routes.
- Internal admins cannot accidentally mutate customer data without project scoping and audit trail.
- Test command: `pytest backend/tests/test_account_separation.py backend/tests/test_admin_console.py -q`

---

### 8) Audit logging + observability completion

**File-level fixes**
- `backend/app/services/audit_log_service.py`
- `backend/app/routes/uploads.py`
- `backend/app/routes/vault.py`
- `backend/app/routes/link_keys.py`
  - Ensure actor/scope/action/outcome logs for create/update/delete/download/grant/revoke/approve events.
- Add runbook docs:
  - `docs/ops/audit-events-matrix.md`
  - `docs/ops/security-alerting-baseline.md`

**Acceptance checks**
- Every sensitive mutation is queryable by actor, project_id, family_id, and event type.
- Security review can reconstruct event chain without DB forensics.

---

### 9) Full “all buttons/all promises” E2E certification gate

**File-level fixes**
- Add E2E spec pack (Cypress/Playwright depending on stack):
  - `tests/e2e/admin-customer-boundary.spec.*`
  - `tests/e2e/vault-upload-cinematic.spec.*`
  - `tests/e2e/family-tree-linked-network.spec.*`
  - `tests/e2e/link-keys-entitlement.spec.*`
- Add CI workflow gate:
  - `.github/workflows/e2e-release-gate.yml`

**Acceptance checks**
- Release is blocked unless full critical path passes:
  - signup/login,
  - purchase/entitlement,
  - upload/review/approve,
  - cinematic visibility,
  - family/linked tree navigation,
  - vault grant/release,
  - admin-only control-plane actions.

## Cross-cutting implementation rule

- Prefer a **single policy engine function** per concern (entitlement access, workspace visibility, privacy visibility) and call it from all routes/services.
- Add deny-by-default behavior whenever project/family/workspace context is missing.

## Suggested execution order (strict)

1. P0.3 (vault path/payload integrity bug)
2. P0.2 (vault entitlement/context enforcement)
3. P0.1 (link-key strict entitlement + paid order)
4. P1.4 (upload/storage hardening)
5. P1.5 (cinematic policy verification)
6. P1.6 (tree/linked tree reliability)
7. P2.7/P2.8 (admin boundary + audit observability)
8. P2.9 (full E2E release gate)
