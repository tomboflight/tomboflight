# Tomb of Light Platform Blueprint

Status: Working blueprint

Purpose: Turn Tomb of Light from a working prototype into a controlled production platform for private family archives, lineage verification, premium package fulfillment, and limited on-chain proof anchoring.

Execution companion: See [IMPLEMENTATION_CHECKLIST.md](./IMPLEMENTATION_CHECKLIST.md) for the ordered build sequence.
On-chain backend spec: See [ONCHAIN_ANCHOR_BACKEND_SPEC.md](./ONCHAIN_ANCHOR_BACKEND_SPEC.md) for the detailed minting, metadata, and dashboard architecture.

## 1. Product model

Tomb of Light should operate on one core rule:

1. A customer creates an account.
2. The customer purchases a package or approved add-on.
3. The system creates or updates a project.
4. The project receives an entitlement set.
5. The customer only sees workflows allowed by that entitlement.
6. Every upload, review, correction, and delivery action stays scoped to that project and its related family workspace.

The platform should be entitlement-driven, metadata-driven, and role-restricted by default.

## 2. Core platform principles

- Package access must come from paid orders and active entitlements, not raw project records alone.
- Customer workspaces and admin workspaces must stay separate.
- Family data should be private by default.
- Verified facts must not be silently overwritten.
- Human review remains the final authority for verification decisions.
- Public blockchain state must be minimal and non-sensitive.
- Every critical action should leave an audit trail.

## 3. Core systems to finish

### 3.1 Upload architecture

Uploads must be organized by metadata, not by filename conventions alone.

Every upload record should attach to:

- `user_id`
- `project_id`
- `family_id` when applicable
- `member_id` when applicable
- `upload_category`
- `verification_type`
- `evidence_kind`
- `created_at`
- `uploaded_by_user_id`
- `content_type`
- `size_bytes`

Logical upload groupings:

- Portrait packages
- Household and network packages
- Family-level evidence
- Member-level evidence
- Relationship-supporting evidence
- Future link-request or collaborator attachments

System behavior:

- Detect the active package and workspace automatically.
- Only render upload fields allowed by that package.
- Save uploads into the correct project scope.
- Attach uploads to the correct family or member when selected.
- Prevent uploads outside the user’s entitled project.

### 3.2 Record lifecycle and correction model

Customer data must move through controlled states:

- `draft`
- `submitted`
- `verified_locked`

Customers should be able to correct:

- names
- spelling
- birth years
- notes
- upload mistakes
- intake mistakes
- visibility settings

Customers should not freely overwrite facts that are already:

- reviewed
- approved
- verified
- included in a certificate
- included in a delivered build

When locked data needs to change:

1. The customer submits a correction request.
2. The request enters an admin review queue.
3. The decision is recorded.
4. The original and corrected values remain auditable.

### 3.3 Verification workflow

Verification should be layered.

Layer 1: automatic checks

- required fields present
- allowed file type
- allowed file size
- upload allowed by package
- member belongs to family and project
- duplicate file detection
- missing step detection
- category consistency

Layer 2: rule-based flags

- mismatched names
- impossible dates or age gaps
- duplicate identity conflicts
- weak evidence coverage
- document/member mismatch
- confidence scoring

Layer 3: human review

Admin reviewers decide:

- approved
- rejected
- pending
- needs correction
- requires more evidence

Verification outcomes must update the right scope:

- member
- relationship
- family
- project

### 3.4 Admin workspace and roles

Admin flows should live in an internal workspace, not inside customer pages.

Suggested roles:

- `root_admin`
- `platform_admin`
- `operations_admin`
- `verification_reviewer`
- `finance_admin`
- `marketing_admin`

Admin capabilities should include:

- intake review
- approve/reject/provision actions
- upload review and download
- delete invalid uploads
- family tree corrections
- member and relationship corrections
- verification decisions
- link request review
- package and project state review
- audit log visibility

Minimum admin consoles:

- Intake Queue
- Verification Review Queue
- Family Manager
- Upload Review Console
- Link Request Review
- Audit and History Viewer

### 3.5 Storage, security, and legal handling

Production storage should use private cloud object storage, not local machine storage.

Recommended model:

- Object storage: Cloudflare R2 or AWS S3
- Database stores metadata and storage references only

Access control requirements:

- authenticated access only
- package entitlement checks
- project ownership checks
- role checks
- authenticated or signed downloads
- private bucket policy

Security requirements:

- HTTPS in transit
- encryption at rest
- no public raw file URLs
- admin MFA
- rate limiting
- audit logs
- malware scanning later
- secret management
- no default production secrets

Legal and policy requirements:

- Terms
- Privacy Policy
- upload authority language
- consent disclosures
- reviewer access disclosure
- retention schedule
- deletion workflow
- correction workflow
- takedown workflow
- staff access policy
- SOP for verification review

### 3.6 Collaboration and invited access

Default workspace control belongs to one owner account.

Optional invited roles can be added later:

- owner
- editor
- uploader
- reviewer
- view_only

Partner or spouse access should be invitation-based, never automatic.

### 3.7 Deceased and living records

Deceased individuals should absolutely be represented when they are part of the lineage or archive.

Each member record should support:

- `life_status`: `living`, `deceased`, `unknown`
- exact or approximate dates
- verification status
- source type: `narrative` or `verified`

The system should clearly distinguish narrative history from verified fact.

### 3.8 Hosting and operations

The live platform should not depend on a founder laptop being online.

Production stack requirements:

- hosted frontend
- hosted backend
- hosted database
- hosted object storage
- background jobs for scans, queues, and notifications

Developer machines should only be used for:

- development
- debugging
- deployment
- internal operations

### 3.9 Blockchain and NFT boundary

Detailed implementation reference: [ONCHAIN_ANCHOR_BACKEND_SPEC.md](./ONCHAIN_ANCHOR_BACKEND_SPEC.md)

The platform should keep sensitive family data off-chain.

On-chain:

- token ID
- certificate reference
- proof hash
- issuance metadata
- version or delivery anchor

Off-chain:

- names
- photos
- documents
- member notes
- relationship evidence
- private family structures
- private certificates and archives

Blockchain should prove authenticity and provenance, not store private family identity records.

### 3.10 Fraud, theft, and payment abuse prevention

Technical abuse prevention:

- strict entitlement checks after payment confirmation
- webhook-confirmed fulfillment
- admin-only internal endpoints
- rate limiting
- token and session hardening
- private repo and infrastructure access controls
- audit logs on purchases, upgrades, downloads, and admin actions

Payment abuse prevention:

- Stripe fraud tooling
- fulfillment only after verified payment state
- dispute evidence process
- controls for high-value irreversible delivery

NFT misuse reality:

- images can always be copied visually
- authenticity must come from the official contract, provenance, and private content controls

## 4. Required data boundaries

### 4.1 Project boundary

The project is the commercial and authorization boundary.

The project should determine:

- package code
- package lane
- active entitlements
- collaborator scope
- eligible workflows
- fulfillment history

### 4.2 Family boundary

The family is the content boundary for household and network builds.

The family should determine:

- visible members
- relationships
- family-level uploads
- certificate scope
- sharing rules

### 4.3 Member boundary

The member is the verification and evidence boundary.

The member should determine:

- identity details
- portrait upload
- supporting evidence
- verification status
- correction requests

## 5. Expected user journeys

### 5.1 Customer journey

1. Sign up or sign in.
2. Purchase a package.
3. System provisions a project and entitlements.
4. Customer sees only allowed tools.
5. Customer completes guided intake.
6. Customer uploads guided evidence.
7. Customer tracks review status.
8. Customer receives delivery, certificate access, or further requests.

### 5.2 Admin journey

1. Review intake.
2. Approve, reject, or send back for correction.
3. Provision the correct workspace.
4. Review uploads and verification evidence.
5. Mark verified, pending, rejected, or needs correction.
6. Manage family structure and fixes.
7. Review logs, link access, and project state.

## 6. Near-term implementation priorities

### P0

- Enforce entitlement-backed access everywhere.
- Keep customer/admin routing separated.
- Complete metadata-scoped upload handling.
- Add dedicated verification review queue.
- Add audit trails for verification and corrections.

### P1

- Add correction request workflow.
- Add collaborator invitation model.
- Move uploads from local storage to private cloud storage.
- Add stronger review tooling and reviewer notes.
- Add legal policy pages and operational SOPs.

### P2

- Add automated scoring and duplicate detection improvements.
- Add malware scanning and richer fraud signals.
- Add controlled on-chain proof issuance.
- Add long-term retention and archive lifecycle controls.

## 7. Current implementation direction

The current codebase is already moving toward this model in a few good ways:

- package-gated customer pages
- project entitlements
- admin intake flows
- family and member scoped uploads
- separate internal admin dashboard concepts

The major remaining gaps are:

- dedicated verification review operations
- correction-request lifecycle
- collaborator permissions
- cloud storage migration
- formal legal and retention controls
- deeper audit and fraud tooling

## 8. Build target

Tomb of Light should become a private, entitlement-scoped family archive and verification platform with:

- customer package journeys
- guided intake and uploads
- human-reviewed verification
- secure private storage
- internal admin operations
- auditable corrections
- limited on-chain proof anchoring

That is the production model this repository should now build toward.
