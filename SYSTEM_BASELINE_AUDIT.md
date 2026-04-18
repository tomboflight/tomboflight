# Tomb of Light Baseline Audit (Phase 0)

## Scope

This document captures the current **as-built** architecture and behavior for:

1. Package and entitlement system
2. Account/auth system
3. Workspace and project scoping

It is intended as a pre-change baseline before deeper remediation and UX upgrades.

## 1) System Architecture Map

### Frontend surface

- Multi-page web application with dedicated customer/admin flows (`dashboard.html`, `billing.html`, intake/upload pages, workspace access pages).
- Frontend API calls are routed to FastAPI backend endpoints (e.g., `/billing/*`, `/auth/*`, `/projects/*`).
- Billing frontend resolves user context and package-aware maintenance links using package code keyed payment links.

### Backend service

- FastAPI application (`backend/app/main.py`) composes modular routers for auth, billing, projects, entitlements, uploads, workspace access, family graph, verification, admin consoles, and audit logs.
- Startup lifecycle initializes MongoDB connection and key operational indexes, including:
  - orders indexes
  - project entitlement indexes
  - mint indexes
  - stripe event indexes
- Security headers and CORS are centrally enforced at middleware level.

### Data layer (MongoDB)

Primary collections inferred from services/routes include:

- `users`
- `orders`
- `projects`
- `project_entitlements`
- `project_members`
- `families`
- `family_members`
- additional domain collections (verification, minting, records, logs)

### Purchase-to-workspace flow (current)

Current orchestrated path:

1. User account exists (or pending checkout user is created).
2. Paid package order is written (`orders`).
3. Order reconciliation/provisioning links order to an existing eligible project or creates a new project.
4. Project package fields are normalized (`package_code`, `package_slug`, `project_lane`).
5. Project entitlement record is upserted in `project_entitlements` with resolved package capabilities and maintenance status.
6. Owner membership is ensured in `project_members` to establish workspace access.

## 2) Package & Entitlement Model (Current Behavior)

### Canonical package implementation

The platform currently uses concrete package codes and lanes:

- Portrait lane (self-like scope):
  - `legacy_snapshot`
  - `legacy_portrait_intro`
  - `digital_legacy_portrait`
- Household lane:
  - `household_foundation`
  - `heirloom_legacy_tree`
  - `legacy_plus`
- Network lane:
  - `family_estate_concierge`
- Organization lane:
  - `command_structure_network`

Alias and slug translation normalize incoming identifiers to canonical package codes.

### Entitlement resolution

Entitlements are computed from package baseline + active addons:

- Limits: uploads, storage, members, households, org nodes, zoom layers
- Feature flags: family tree/org chart build capabilities, intake visibility, link key access, certificate capability, narration capability
- Addon expansions are merged into resolved entitlement map

### Upgrade and maintenance behavior

- Upgrade legality is constrained by package `upgrade_targets`.
- Maintenance defaults come from package control policy and are materialized into entitlement lifecycle fields:
  - scheduled start
  - active period start/end
  - renew-at
  - Stripe maintenance subscription metadata

## 3) Account System (Current Behavior)

### Registration/login

- Signup requires legal acceptance fields (terms/privacy/eligibility attestation).
- Password policy validation occurs during registration.
- Login supports:
  - credential validation
  - IP/principal-aware rate limiting
  - lockout after threshold failures
  - MFA-required and MFA-enrollment-required challenge modes
- Auth token is returned and set in HttpOnly auth cookie.
- CSRF token is generated and set in separate cookie.

### Session/security posture

- No-store cache headers are applied for auth responses.
- Security middleware adds HSTS (on secure requests), frame/type hardening, strict referrer policy, and permissions policy.

## 4) Workspace/Project Scoping (Current Behavior)

### Access model

Workspace access is resolved through a layered model:

1. `project_members` membership records (primary)
2. Owner fallback (`owner_user_id` / `owner_email`)
3. Internal admin override roles
4. Family visibility fallback when owner markers are absent

### Default project selection

For authenticated users, active/default project selection prioritizes:

1. Accessible project IDs from membership records
2. Active project entitlements
3. Owner project fallback (or latest project for admins)

### Entitlement binding to workspace

Workspace context resolution combines:

- project record
- active entitlement (if present)
- paid package order fallback

Resolved entitlement capabilities are then transformed into:

- active permission flags (`can_*`)
- lane experience mode
- allowed modules/chambers

## 5) Initial Risk/Gap Notes for Next Audit Phase

These are not code changes yet; they are baseline observations to prioritize in Phase 1 deep audit.

1. **Tier naming abstraction gap**: business-facing tier names (Self/Household/Network/Organization) do not appear as first-class canonical codes; implementation uses product package codes grouped by lane.
2. **Data representation variance**: several services include defensive handling for string/ObjectId variants, suggesting historical inconsistency in stored identifiers.
3. **Provisioning reliance on repair jobs**: order/project/entitlement coherence is reinforced by reconciliation helpers, indicating need to validate real-time path completeness and idempotency under load.
4. **Access-path complexity**: workspace visibility uses multiple fallbacks (membership, owner, shared family data, admin), which is robust but should be formally regression-tested for strict isolation.

## 6) Recommended Next Step

Proceed to a **package entitlement conformance matrix** that enumerates each lane/package against:

- upload/storage/member/node limits
- feature gates
- workspace access behavior
- onboarding/upgrade/downgrade edge states

Then execute automated scenario tests by tier and membership role.
