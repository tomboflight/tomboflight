# Tomb of Light Continuity Kernel — Phase 3 Contract Verification

Status: verification only (no runtime behavior or database behavior changes).

## 1) Workspace and Access Context Contract
- The workspace/access boundary keeps these contract files in place:
  - `backend/app/services/workspace_access_service.py`
  - `backend/app/services/access_context_service.py`
  - `backend/app/services/project_membership_service.py`
  - `backend/app/routes/workspace_access.py`
  - `backend/app/routes/users.py`
- Backward compatibility is preserved with both route contracts:
  - `/users/me/workspace-context`
  - `/users/me/access-context`
- The access-context route remains an alias-compatible surface for workspace context payload retrieval.

## 2) Entitlement and Package Identity Contract
- Entitlement boundaries are split between entitlement computation and persisted project entitlement records:
  - `backend/app/services/entitlement_service.py`
  - `backend/app/services/project_entitlement_service.py`
  - `backend/app/routes/project_entitlements.py`
- Canonical package identity depends on:
  - `package_code`
  - `package_slug`
  - package lane normalization (`lane` / `package_lane`)
- Source-of-truth package boundaries remain:
  - `backend/app/core/package_catalog.py`
  - `backend/app/core/package_mapping.py`
  - `backend/app/core/package_type_catalog.py`
- Contract risk to continue tracking: slug/code drift and lane drift can create entitlement mismatches if package_code/package_slug/package lane normalization diverges.

## 3) Viewer/Public Manifest Contract
- Runtime viewer payloads and public mint metadata manifests remain explicitly separated:
  - private runtime viewer payload contract: `backend/app/services/viewer_manifest_service.py`
  - public mint metadata manifest contract: `backend/app/services/public_manifest_service.py`
  - viewer runtime route: `backend/app/routes/viewer_manifest.py`
- Contract boundary: do not collapse runtime private viewer payload logic into public mint metadata manifest logic.

## 4) Certificate Contract
- Generated lineage certificate payload contract remains distinct from immutable issued certificate record contract:
  - generated payload: `backend/app/services/lineage_certificate_service.py`, `backend/app/routes/lineage_certificate.py`
  - immutable issued records: `backend/app/services/issued_certificate_service.py`, `backend/app/routes/issued_certificates.py`
- Contract boundary: generation is derived payload logic; issuance is immutable record/version lifecycle logic.

## 5) Mint Readiness Contract
- Mint readiness contracts remain distributed across:
  - `backend/app/services/mint_policy_service.py`
  - `backend/app/services/mint_record_service.py`
  - `backend/app/services/mint_job_service.py`
  - `backend/app/routes/mint_policy.py`
  - `backend/app/routes/mint_records.py`
- Queueing mint work must preserve readiness/eligibility/approval gate language before queueing mint work.

## 6) Audit Contract
- Audit services and routes remain present:
  - `backend/app/services/audit_log_service.py`
  - `backend/app/routes/audit_logs.py`
- Contract fields remain actor/action/target/context oriented (`actor_*`, `action`, `target_*`, `context`) with before/after/result support.
- Privileged repair and admin actions remain tied to audit logging language and audit traceability requirements.

## 7) Admin Repair Contract
- Admin repair/control surfaces remain present:
  - `backend/app/services/admin_control_service.py`
  - `backend/app/routes/admin_control_center.py`
  - `backend/app/routes/admin_maintenance.py`
  - `backend/app/services/package_provisioning_service.py`
- Contract boundary: repair operations remain dry-run/apply safety oriented and officer-policy-gated.
