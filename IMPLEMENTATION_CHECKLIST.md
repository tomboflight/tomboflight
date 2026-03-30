# Tomb of Light Implementation Checklist

Purpose: Convert the platform blueprint into an ordered execution plan that product, engineering, operations, and legal can work through together.

Related blueprint: [PLATFORM_BLUEPRINT.md](/Users/ok/Documents/GitHub/tomboflight/PLATFORM_BLUEPRINT.md)
Detailed on-chain backend reference: [ONCHAIN_ANCHOR_BACKEND_SPEC.md](/Users/ok/Documents/GitHub/tomboflight/ONCHAIN_ANCHOR_BACKEND_SPEC.md)

## How to use this file

- Work top to bottom unless a dependency says otherwise.
- Do not start later phases by bypassing earlier security or data-boundary work.
- Mark an item complete only when its acceptance criteria are true in production-facing code, not just mocked in the UI.
- If a task changes the product model, update the blueprint first and then update this checklist.

## Definition of done

An item is only done when:

- the code path exists
- the UI or API behavior is wired end to end
- access control is enforced
- audit logging exists where required
- basic tests or verification steps are documented and run

## Phase 0: Platform Guardrails

Goal: Make package scoping, routing, uploads, and admin separation trustworthy before adding more capability.

### 0.1 Entitlement-backed access audit

- [ ] Confirm every customer feature gate uses paid orders and active entitlements, not raw project records.
- [ ] Confirm every backend route that exposes package features enforces entitlement-backed access.
- [ ] Confirm admin-only routes reject customer accounts and redirect or fail safely.

Acceptance criteria:

- Customer access cannot be expanded by manually creating or editing a project record.
- Internal admin pages do not function for customer accounts.
- Unauthorized requests return controlled 403 behavior.

### 0.2 Workspace routing normalization

- [ ] Standardize active workspace resolution around `project_id` and `family_id`.
- [ ] Ensure dashboard, intake, uploads, tree, certificate, and link pages all preserve workspace context.
- [ ] Ensure package-specific buttons only appear when the target workspace is actually available.

Acceptance criteria:

- Customer buttons always open the correct project and family.
- Household and network flows do not drift to the wrong family.
- Hidden actions cannot be reopened through stale client links alone.

### 0.3 Upload metadata completeness

- [ ] Ensure every upload record stores `user_id`, `project_id`, `family_id`, `member_id`, `upload_category`, `verification_type`, `evidence_kind`, `created_at`, `uploaded_by_user_id`, `content_type`, and `size_bytes`.
- [ ] Add any missing project-scoping fields to legacy upload flows.
- [ ] Ensure upload listing and download routes are scoped to the entitled project and visible family.

Acceptance criteria:

- Files can be queried by project, family, member, and category.
- A user cannot see uploads from another customer workspace.
- Admin reviewers can filter uploads using metadata instead of filename guesswork.

### 0.4 Audit logging baseline

- [ ] Log project provisioning decisions.
- [ ] Log upload create, delete, and download actions.
- [ ] Log verification decisions and correction decisions.
- [ ] Log admin overrides and relationship edits.

Acceptance criteria:

- Security-sensitive actions leave actor, scope, action, and timestamp records.
- Admin changes are traceable to a specific account.

## Phase 1: Verification Operations

Goal: Build the real review system instead of asking admins to work through customer pages.

### 1.1 Verification status model

- [ ] Introduce a normalized verification state model for member, relationship, family, and project scopes.
- [ ] Support at least `pending`, `approved`, `rejected`, `needs_correction`, and `requires_more_evidence`.
- [ ] Define which statuses are machine-assigned and which require human approval.

Acceptance criteria:

- Verification states are consistent across backend records and UI labels.
- Review decisions update the correct scope without ambiguity.

### 1.2 Verification review queue backend

- [ ] Create a dedicated review queue for uploaded evidence and pending claims.
- [ ] Support filtering by package, project, family, member, status, and upload type.
- [ ] Support reviewer notes and decision history.

Acceptance criteria:

- Admins can fetch only items requiring review.
- Queue entries show enough metadata to review without guessing context.

### 1.3 Verification review console

- [ ] Build an internal review page for evidence review.
- [ ] Show file preview or authenticated download.
- [ ] Show package, project, family, member, and uploader context.
- [ ] Add decision actions for approve, reject, pending, and needs correction.

Acceptance criteria:

- Admins do not need to use customer upload pages to review evidence.
- Review decisions are reflected in customer-facing status views.

### 1.4 Automatic validation and scoring

- [ ] Add automatic checks for required fields, file types, file sizes, duplicate uploads, and member-family consistency.
- [ ] Add rule-based flags for suspicious or low-confidence submissions.
- [ ] Surface validation results in the review queue.

Acceptance criteria:

- Bad uploads are caught before review when possible.
- Reviewers can see why an item was flagged.

### 1.5 Customer review status visibility

- [ ] Show customers when evidence is pending, approved, rejected, or needs correction.
- [ ] Tell customers which member or claim needs attention.
- [ ] Provide guided next steps instead of generic failure states.

Acceptance criteria:

- Customers can understand what is missing and what happens next.
- Support burden drops because the status is explicit in-product.

## Phase 2: Corrections and Record Locking

Goal: Let customers fix mistakes without silently rewriting verified history.

### 2.1 Draft, submitted, and locked states

- [ ] Normalize record lifecycle states for editable customer records.
- [ ] Prevent silent overwrites of verified or certificate-backed facts.
- [ ] Define which fields remain customer-editable after submission.

Acceptance criteria:

- Verified records cannot be freely rewritten from customer UI.
- Customer edits remain possible where appropriate before lock.

### 2.2 Correction request model

- [ ] Add correction request records with original value, requested value, reason, requester, and status.
- [ ] Attach correction requests to member, relationship, family, or project scope.
- [ ] Record reviewer decision and rationale.

Acceptance criteria:

- Every correction request has a full before-and-after history.
- Admins can approve or reject corrections without losing the original data.

### 2.3 Customer correction UI

- [ ] Add correction submission controls where users naturally encounter locked data.
- [ ] Show whether a request is pending, approved, or rejected.
- [ ] Allow upload replacement requests for invalid files.

Acceptance criteria:

- Customers can request legitimate fixes without bypassing controls.
- Locked data changes only through the review flow.

## Phase 3: Collaboration and Invited Access

Goal: Support spouse, partner, and contributor access safely.

### 3.1 Collaborator data model

- [ ] Add project-level collaborator records.
- [ ] Support roles `owner`, `editor`, `uploader`, `reviewer`, and `view_only`.
- [ ] Scope invited access to the correct project and family visibility rules.

Acceptance criteria:

- Invited users do not automatically inherit full owner permissions.
- Permissions are explicit and role-driven.

### 3.2 Invitation flow

- [ ] Add owner-controlled invite creation and revocation.
- [ ] Add invite acceptance flow tied to an authenticated account.
- [ ] Add visibility of who currently has access.

Acceptance criteria:

- Owners can add and remove collaborators without admin intervention.
- Collaborators only gain the permissions assigned.

### 3.3 Permission enforcement

- [ ] Update feature gates to understand collaborator roles.
- [ ] Restrict uploads, edits, downloads, and review actions by role.
- [ ] Expand audit logging for collaborator activity.

Acceptance criteria:

- A `view_only` user cannot upload or edit.
- A collaborator cannot escalate their own role from the client side.

## Phase 4: Cloud Storage and File Protection

Goal: Move from local file storage to production-grade private storage.

### 4.1 Storage abstraction layer

- [ ] Introduce a storage interface that separates file metadata from storage backend implementation.
- [ ] Support current local storage as a development adapter.
- [ ] Add a private cloud adapter for R2 or S3.

Acceptance criteria:

- Upload code does not depend directly on local filesystem paths.
- Storage backend can be swapped by environment configuration.

### 4.2 Private bucket migration

- [ ] Define bucket layout by environment and workspace scope.
- [ ] Migrate upload writes to private cloud storage.
- [ ] Store only metadata and object references in the database.

Acceptance criteria:

- Production uploads no longer depend on local disk.
- No raw public file URLs are exposed.

### 4.3 Download protection

- [ ] Use authenticated or signed download flows.
- [ ] Ensure download checks enforce auth, entitlement, role, and scope.
- [ ] Add cache-control and no-store headers where sensitive.

Acceptance criteria:

- Download links cannot be shared as permanent public URLs.
- Sensitive uploads remain protected in transit and at rest.

### 4.4 Advanced file safety

- [ ] Add malware scanning workflow.
- [ ] Add duplicate file hashing.
- [ ] Add retention and deletion markers for future policy enforcement.

Acceptance criteria:

- Dangerous uploads can be flagged or quarantined.
- Duplicate evidence can be identified reliably.

## Phase 5: Legal and Compliance Readiness

Goal: Match the product behavior with enforceable policy and operational handling.

### 5.1 Customer-facing legal surfaces

- [ ] Finalize Terms.
- [ ] Finalize Privacy Policy.
- [ ] Finalize upload consent and authority language.
- [ ] Finalize review disclosure language.

Acceptance criteria:

- The product flow and the legal text say the same thing.
- Uploaders are clearly told what review and storage means.

### 5.2 Operational policy set

- [ ] Create retention schedule.
- [ ] Create deletion workflow.
- [ ] Create takedown workflow.
- [ ] Create staff access policy.
- [ ] Create verification review SOP.

Acceptance criteria:

- Internal operations have written handling rules, not just informal habits.
- Legal handling decisions can be followed consistently by staff.

### 5.3 Sensitive-person handling

- [ ] Define handling rules for living persons, minors, and deceased persons.
- [ ] Distinguish narrative content from verified factual content.
- [ ] Define when additional consent or admin review is required.

Acceptance criteria:

- The platform can explain why certain records or uploads require stricter handling.

## Phase 6: Fraud, Payment, and Security Hardening

Goal: Reduce business abuse, account abuse, and improper entitlement activation.

### 6.1 Payment fulfillment controls

- [ ] Ensure entitlements activate only after verified payment confirmation.
- [ ] Audit all upgrade and fulfillment paths.
- [ ] Add dispute and chargeback evidence support.

Acceptance criteria:

- High-value fulfillment cannot be triggered from unverified payment state.
- Payment events are traceable through provisioning.

### 6.2 Session and admin hardening

- [ ] Add MFA for admins.
- [ ] Review token lifetime and session invalidation strategy.
- [ ] Add rate limiting to auth, uploads, and admin review endpoints.

Acceptance criteria:

- Admin access has stronger protection than customer access.
- High-risk endpoints resist brute-force and automated abuse.

### 6.3 Security review pass

- [ ] Review secrets handling.
- [ ] Review public endpoint exposure.
- [ ] Review logging of sensitive data.
- [ ] Review download and upload abuse paths.

Acceptance criteria:

- No obvious secret leakage or public admin exposure remains.
- Logs do not expose private family data unnecessarily.

## Phase 7: Blockchain and Certificate Boundary

Goal: Keep proof on-chain while keeping private family content off-chain.

Detailed implementation reference: [ONCHAIN_ANCHOR_BACKEND_SPEC.md](/Users/ok/Documents/GitHub/tomboflight/ONCHAIN_ANCHOR_BACKEND_SPEC.md)

### 7.1 Certificate issuance boundary

- [ ] Define the exact certificate payload used for issuance and proof anchoring.
- [ ] Separate private certificate content from public proof identifiers.
- [ ] Version certificate issuance and re-issuance.

Acceptance criteria:

- Sensitive family content never needs to be published on-chain.
- Re-issuance and correction events can be tracked cleanly.

### 7.2 On-chain proof layer

- [ ] Store only minimal anchor data on-chain.
- [ ] Keep token provenance and certificate reference verifiable.
- [ ] Do not publish names, photos, family documents, or relationship evidence on-chain.

Acceptance criteria:

- Blockchain data proves authenticity without leaking private family records.

## Cross-cutting verification checklist

Run this across every phase:

- [ ] Backend access control reviewed
- [ ] Customer/admin UX reviewed
- [ ] Audit logging reviewed
- [ ] Test coverage or manual verification documented
- [ ] Legal impact reviewed when data handling changes

## Suggested execution order

1. Phase 0
2. Phase 1
3. Phase 2
4. Phase 4
5. Phase 3
6. Phase 5
7. Phase 6
8. Phase 7

Reasoning:

- Trust boundaries and verification operations come first.
- Record locking should happen before broad collaborator access.
- Cloud storage and security hardening should happen before scale.
- Blockchain proof should come after private-platform boundaries are stable.

## First build tranche

If work starts immediately, the best first tranche is:

- [ ] Finish entitlement enforcement audit
- [ ] Complete upload metadata scoping
- [ ] Build verification review queue backend
- [ ] Build verification review console
- [ ] Add correction request data model
- [ ] Add customer correction request entry points

That tranche gets Tomb of Light from "prototype with package flows" to "controlled private archive and review platform."
