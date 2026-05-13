# Tomb of Light Continuity Kernel (Proposed Architecture)

Status: design draft (documentation-only, no behavior change)

The Continuity Kernel is the protected internal architecture layer that controls identity, package entitlement, workspace/co-owner access, uploads, verification, lineage data, viewer manifests, certificates, mint readiness, admin repair, and audit history.

## 1) Identity Resolver
- Canonicalize user identity (`id`, `_id`, `user_id`, email).
- Normalize role aliases and officer/admin role resolution.
- Provide stable actor identity for policy decisions and audit entries.
- Candidate integration points: `role_catalog`, auth dependencies, user/profile access-context services.

## 2) Entitlement Graph Resolver
- Resolve package identity from aliases/slugs to canonical package code.
- Resolve entitlement graph from package + active addons.
- Distinguish computed entitlements from persisted project entitlement records.
- Treat paid-order provenance and entitlement status as first-class gates.

## 3) Workspace Access Resolver
- Resolve active project/family context with membership-first behavior.
- Enforce co-owner/spouse/member role access with owner fallback controls.
- Enforce package capability gates before exposing feature routes.
- Preserve admin override semantics with explicit officer permissions.

## 4) Lineage Event Ledger
- Normalize lineage/family/member/relationship events as append-only domain events.
- Keep verification decisions and lineage relationship mutations traceable.
- Ensure lineage graph and family tree views derive from governed state.

## 5) Viewer Manifest Compiler
- Compile runtime viewer payloads from approved workspace artifacts.
- Separate private runtime viewer manifest concerns from public mint metadata manifests.
- Ensure package capability and visibility/privacy scope checks are enforced pre-compile.

## 6) Readiness Gate Matrix
- Centralize gating outcomes for:
  - paid order present
  - active entitlement present
  - workspace member access valid
  - verification/public-safe approvals complete
  - delivery/public manifest finalized
  - mint fee/readiness signals satisfied
- Return explicit reason codes for each blocked state.

## 7) Certificate Delivery Record
- Separate certificate generation (derived payload) from immutable issued certificate records.
- Version issued certificate records without mutating historical versions.
- Preserve family/project linkage and integrity hashes for downstream proofs.

## 8) Mint Readiness Controller
- Enforce mint policy + runtime readiness + approval chain before queueing jobs.
- Maintain canonical mint record lifecycle state and explicit precedence.
- Keep mint job sequencing and receipt synchronization deterministic and auditable.

## 9) Officer Policy Layer
- Define explicit officer/admin permissions for control center, reports, and repair actions.
- Enforce least privilege on sensitive operations (entitlement repair, mint repair, account state actions).
- Require reason/context payloads for high-impact admin actions.

## 10) Self-Healing Repair Engine
- Implement repair plans as dry-run-first operations.
- Keep repair operations idempotent, scope-limited, and policy-gated.
- Unify repair entry points behind shared contracts to reduce divergence risk.

## 11) Audit Timeline
- Write immutable audit records for critical identity, entitlement, workspace, verification, certificate, mint, and repair actions.
- Standardize action naming and target typing for cross-surface traceability.
- Preserve before/after/context payloads with actor identity.

## Guardrails for Implementation
- No bypass of auth, entitlement, verification, mint readiness, audit logging, or officer permissions.
- No direct live-data mutation outside approved policy-gated flows.
- No consolidation/deletion of files until overlap is proven by architecture tests and contract checks.
