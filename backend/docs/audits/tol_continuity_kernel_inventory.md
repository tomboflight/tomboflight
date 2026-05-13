# Tomb of Light Continuity Kernel Inventory (Audit-Only)

Scope: static architecture audit only. No code behavior changes. No data access/write operations.

## Legend
- **Source-of-truth (SoT)**: `Yes`, `Partial`, or `No`
- **Duplicate/Risk**: `None observed`, `Overlap risk`, or `High attention`
- **Preserve**: `Yes` for all audited kernel-critical files

## Inventory

| File path | Responsibility | Likely domain | SoT | Duplicate/Risk | Preserve |
|---|---|---|---|---|---|
| `backend/app/core/package_catalog.py` | Canonical package/addon definitions, capability flags, mint/control policy data | Packages / entitlement baseline | Yes | Overlap risk with other package normalizers, but appears canonical catalog | Yes |
| `backend/app/core/package_mapping.py` | Slug/code alias translation and canonical package identity map | Packages / identity mapping | Partial | Overlap risk with direct package field usage in services | Yes |
| `backend/app/core/package_type_catalog.py` | Lane normalization (`portrait/household/network/organization`) | Package lanes | Yes | None observed | Yes |
| `backend/app/core/role_catalog.py` | Canonical role alias maps for users/admin/project members (`co_owner`, `spouse`, etc.) | Identity / roles / member access | Yes | None observed | Yes |
| `backend/app/routes/package_catalog.py` | Internal package catalog API | Packages | No (API surface) | Overlap risk with public package catalog route | Yes |
| `backend/app/routes/package_catalog_public.py` | Public-safe package catalog API | Packages | No (API surface) | Overlap risk with internal package catalog route | Yes |
| `backend/app/services/entitlement_service.py` | Pure entitlement resolution from package + addons | Entitlement computation | Partial | Overlap risk with persisted entitlement records | Yes |
| `backend/app/services/project_entitlement_service.py` | Persisted project entitlement lifecycle (upsert/read/list/maintenance fields) | Entitlement records | Yes (project runtime entitlement record) | Overlap risk with `entitlement_service` responsibilities | Yes |
| `backend/app/routes/project_entitlements.py` | Entitlement endpoints (apply/read/upgrade/package summary) | Entitlement API | No (API surface) | None observed | Yes |
| `backend/app/services/order_service.py` | Paid order recording/reconciliation triggers, order↔project linkage | Orders / provisioning | Partial | High attention: tightly coupled to entitlement/project provisioning flows | Yes |
| `backend/app/routes/orders.py` | Orders API + admin repair endpoint for paid package access | Orders / repair access point | No (API surface) | Overlap risk with broader admin repair tools | Yes |
| `backend/app/services/package_provisioning_service.py` | Reconcile orders, lanes, and entitlements through repair/orchestration helpers | Provisioning / repair orchestration | Partial | Overlap risk with admin control repair functions | Yes |
| `backend/app/services/project_membership_service.py` | Project-member SoT for access snapshots, owner fallback, membership backfill | Workspace/member access | Yes (membership record logic) | Overlap risk with older owner-only assumptions | Yes |
| `backend/app/services/workspace_access_service.py` | Workspace context resolver (authz + entitlement + project/family visibility) | Workspace access resolver | Yes (runtime workspace gate) | High attention: central gate for auth/entitlement rules | Yes |
| `backend/app/routes/workspace_access.py` | Membership/invite/co-owner household access APIs | Workspace/co-owner/member access | No (API surface) | Overlap risk via legacy alias endpoints | Yes |
| `backend/app/services/access_context_service.py` | Builds user access-context payload from memberships + entitlements | Identity/workspace context | Partial | Overlap risk with `workspace_access_service` context semantics | Yes |
| `backend/app/routes/users.py` | `/users/me/workspace-context` and alias `/users/me/access-context` | User identity/workspace context | No (API surface) | Duplicate endpoint alias (intentional compatibility) | Yes |
| `backend/app/routes/admin_control_center.py` | Admin control center APIs (repair, mint readiness, reports/export, case ops) | Officer/admin policy layer | No (API surface) | High attention: broad privileged operations in one surface | Yes |
| `backend/app/services/admin_control_service.py` | Admin policy checks, case workspace payloads, repair/ops/reporting engine | Officer policy + repair + analytics/reporting | Yes (admin orchestration logic) | Overlap risk with targeted maintenance/provisioning services | Yes |
| `backend/app/routes/uploads.py` | Upload APIs, privacy scopes, verification evidence uploads, scan/audit hooks | Uploads / verification intake | No (API surface) | High attention: security-sensitive file ingress | Yes |
| `backend/app/services/upload_service.py` | File persistence, metadata normalization, upload record schema population | Upload storage records | Yes (upload record shape + write path) | Overlap risk with route-level validation duplication | Yes |
| `backend/app/services/upload_scan_service.py` | Upload scanning/quarantine decision support | Upload verification/safety | Partial | None observed | Yes |
| `backend/app/routes/verification_records.py` | Admin verification actions + verification record creation/workflow | Verification review | No (API surface) | Overlap risk with member status fields in family members | Yes |
| `backend/app/services/verification_record_service.py` | Verification record list/create/backfill schema helpers | Verification records | Yes (record normalization/backfill) | Overlap risk with route-side logic building decisions | Yes |
| `backend/app/routes/tree.py` | Family tree API surface | Family tree | No (API surface) | None observed | Yes |
| `backend/app/services/tree_service.py` | Tree graph traversal/linking/visibility helpers | Family tree/lineage graph | Partial | Overlap risk with lineage graph/query services | Yes |
| `backend/app/routes/lineage_graph.py` | Lineage graph API | Lineage graph | No (API surface) | Overlap risk with `tree` and `family_graph` APIs | Yes |
| `backend/app/services/lineage_graph_service.py` | Lineage graph data service | Lineage graph | Partial | Overlap risk with tree service responsibilities | Yes |
| `backend/app/routes/family_graph.py` | Family graph API for relationship structures | Family graph | No (API surface) | Overlap risk with lineage/tree graph APIs | Yes |
| `backend/app/routes/viewer_manifest.py` | Viewer manifest endpoint with package capability gate | Viewer manifest | No (API surface) | None observed | Yes |
| `backend/app/services/viewer_manifest_service.py` | Runtime viewer manifest compiler from workspace/family/project artifacts | Viewer manifest compiler | Yes (viewer runtime payload) | Overlap risk with public metadata manifest concepts | Yes |
| `backend/app/services/public_manifest_service.py` | Public-safe token metadata manifest generation/storage | Public manifest / mint artifacts | Yes (on-chain metadata path) | Overlap risk with viewer manifest naming semantics | Yes |
| `backend/app/routes/lineage_certificate.py` | On-demand lineage certificate endpoint | Certificates | No (API surface) | Overlap risk with issued certificate endpoints | Yes |
| `backend/app/services/lineage_certificate_service.py` | Build lineage certificate payload from family/project/verification records | Certificates (generated) | Partial | Overlap risk with issued certificate immutable storage | Yes |
| `backend/app/routes/issued_certificates.py` | Issue/list/read immutable certificates with access checks | Certificates (issued records) | No (API surface) | Overlap risk with lineage certificate generation route | Yes |
| `backend/app/services/issued_certificate_service.py` | Immutable certificate versioning and persistence | Certificates (immutable record SoT) | Yes | None observed | Yes |
| `backend/app/routes/mint_policy.py` | Package mint policy endpoint | Mint policy/readiness | No (API surface) | None observed | Yes |
| `backend/app/services/mint_policy_service.py` | Eligibility/readiness policy matrix for on-chain mint | Mint readiness policy | Yes (policy resolver) | Overlap risk with mint fee readiness checks | Yes |
| `backend/app/routes/mint_records.py` | Mint lifecycle endpoints (prepare, approvals, queue, eligibility) | Mint readiness/controller API | No (API surface) | High attention: readiness and approval gate enforcement | Yes |
| `backend/app/services/mint_record_service.py` | Mint record lifecycle, approvals, canonical status rules | Mint readiness controller | Yes (mint record state machine) | None observed | Yes |
| `backend/app/services/mint_job_service.py` | Mint job queue/worker state transitions and sequencing | Mint execution orchestration | Partial | Overlap risk with mint record status ownership | Yes |
| `backend/app/services/nft_runtime_validation_service.py` | Startup validation for mint runtime config/security | Mint runtime readiness | Yes (runtime guardrail) | None observed | Yes |
| `backend/app/routes/audit_logs.py` | Audit log read endpoint for admin users | Audit history | No (API surface) | None observed | Yes |
| `backend/app/services/audit_log_service.py` | Audit write/list primitives used by privileged operations | Audit timeline | Yes (audit record writes) | None observed | Yes |
| `backend/app/routes/admin_maintenance.py` | Admin maintenance/backfill operations | Repair operations | No (API surface) | Overlap risk with admin control center repair actions | Yes |
| `backend/app/routes/consistency.py` | Consistency report endpoint | Repair diagnostics | No (API surface) | None observed | Yes |
| `backend/app/services/consistency_service.py` | Data consistency checks (duplicates/parent-age anomalies) | Repair diagnostics | Partial | None observed | Yes |
| `backend/scripts/audit_larry_workspace_integrity.py` | Read-only workspace integrity audit script | Repair/audit script | No (script-level operational check) | None observed (read-only) | Yes |
| `backend/scripts/enforce_account_separation.py` | Account separation enforcement and repair orchestration script | Repair/migration script | No (script-level operations) | High attention: write-capable operational script | Yes |

## Duplicate Risk Summary (Audit-Only Findings)

No byte-for-byte duplicate files were identified in the audited kernel surface.

Potential overlap/duplication-risk areas to preserve and govern carefully:

1. **Package maps**: `package_catalog.py` + `package_mapping.py` + route-level package normalization usage (overlap risk, not confirmed duplicate).
2. **Role maps**: `role_catalog.py` appears singular and canonical; no duplicate role map file observed.
3. **Entitlement services**: `entitlement_service.py` (compute) and `project_entitlement_service.py` (persist/runtime) have adjacent responsibilities and require strict boundary discipline.
4. **Viewer/public manifests**: `viewer_manifest_service.py` (runtime UX manifest) and `public_manifest_service.py` (on-chain metadata manifest) are distinct but similarly named; naming/ownership confusion risk.
5. **Repair surfaces**: admin control center repair functions, `admin_maintenance` routes, `package_provisioning_service`, and backend scripts create multi-surface repair entry points.

## Preservation Decision

All inventoried files should be preserved at this stage. This audit found **overlap risk**, but no justified deletions or merges should occur before architecture tests and contract verification.
