# Tomb of Light On-Chain Anchor Backend Spec

Status: Proposed production backend spec

Purpose: Define the exact backend architecture for public-safe NFT anchor issuance, metadata generation, poster generation, mint jobs, and dashboard display without exposing private family archive data.

Related documents:

- [PLATFORM_BLUEPRINT.md](/Users/ok/Documents/GitHub/tomboflight/PLATFORM_BLUEPRINT.md)
- [IMPLEMENTATION_CHECKLIST.md](/Users/ok/Documents/GitHub/tomboflight/IMPLEMENTATION_CHECKLIST.md)

## 1. Launch rule

Tomb of Light should use the smallest public-safe proof on-chain and keep the real archive off-chain.

Core rule:

1. No mint at checkout.
2. No mint at upload.
3. No mint at intake submission.
4. Mint only after final approved public-safe manifest.

This means the live operational flow is:

1. payment confirmed
2. workspace provisioned
3. intake completed
4. uploads and build completed
5. admin final approval
6. customer public-safe approval when required
7. metadata and poster generated
8. mint job executed
9. mint record stored
10. dashboard updated

## 2. Package mint policy

Launch v1 policy:

- `legacy_snapshot`: no automatic mint
- `legacy_portrait_intro`: no automatic mint
- `digital_legacy_portrait`: automatic `portrait_anchor`
- `household_foundation`: automatic `household_anchor`
- `heirloom_legacy_tree`: automatic `household_anchor`
- `legacy_plus`: automatic `household_anchor`
- `family_estate_concierge`: automatic `branch_anchor`, up to 3 included
- `command_structure_network`: opt-in only for launch, `organization_anchor`

Policy rules:

- Lowest two portrait packages stay off-chain by default.
- Organization minting is disabled by default until public-title and privacy handling is finalized.
- Customer opt-in is required before using an approved portrait as public poster art.
- Public title is opt-in only.

## 3. Public/private boundary

### 3.1 On-chain

Blockchain exposes or derives:

- `token_id`
- `contract_address`
- `chain`
- `tx_hash`
- `owner_wallet`
- `token_uri`

### 3.2 Public metadata JSON

Token metadata may include only public-safe fields:

- generic token name
- generic description
- poster image URI
- external URL
- public-safe attributes
- hashed references
- approval timestamp
- version number
- package code and lane

### 3.3 Private vault only

Never publish these to chain or public metadata:

- names of living people unless explicitly opted in
- names of minors
- dates of birth
- addresses, emails, phone numbers
- private photos, videos, audio
- IDs and civil records
- raw family-tree JSON
- admin notes
- correction notes
- signed download URLs

## 4. Environment variables

Add these environment variables:

- `NFT_CHAIN=base-mainnet`
- `NFT_CONTRACT_ADDRESS=...`
- `NFT_MINTER_PRIVATE_KEY=...`
- `HASH_SALT=...`
- `METADATA_BASE_URL=https://metadata.tomboflight.com/v1`
- `POSTER_BASE_URL=https://metadata.tomboflight.com/v1/posters`
- `NFT_MINT_ENABLED=false`
- `NFT_ORG_MINT_ENABLED=false`
- `NFT_RPC_URL=...`

Optional:

- `IPFS_MIRROR_ENABLED=false`
- `IPFS_GATEWAY_BASE_URL=...`
- `PINATA_JWT=...`

## 5. Storage zones

Use three storage zones:

1. Private archive bucket
   - source portraits
   - family documents
   - certificates
   - narration and media

2. Public metadata bucket
   - token JSON
   - optional metadata versions

3. Public poster bucket
   - abstract covers
   - symbolic covers
   - approved public-safe poster art

## 6. MongoDB collection design

### 6.1 `mint_records`

Purpose: permanent internal record of every minted or attempted anchor.

```json
{
  "_id": "ObjectId",
  "project_id": "string",
  "household_id": "string|null",
  "family_id": "string|null",
  "user_id": "string",
  "package_code": "string",
  "package_lane": "string",
  "token_type": "portrait_anchor|household_anchor|branch_anchor|organization_anchor",
  "chain": "base-mainnet",
  "contract_address": "0x...",
  "token_id": "string|null",
  "tx_hash": "0x...|null",
  "metadata_uri": "string",
  "project_ref_hash": "sha256:...",
  "household_ref_hash": "sha256:...|null",
  "build_hash": "sha256:...",
  "certificate_hash": "sha256:...|null",
  "version_number": 1,
  "poster_image_uri_public": "string",
  "poster_style": "abstract_cover|symbolic_cover|approved_poster",
  "mint_status": "pending_approval|approved|queued|minting|minted|failed|superseded|cancelled",
  "approved_at": "datetime|null",
  "minted_at": "datetime|null",
  "failed_at": "datetime|null",
  "customer_wallet": "0x...|null",
  "minted_by": "system|admin_email|user_id",
  "public_title_opt_in": false,
  "public_title": "string|null",
  "public_title_kind": "none|household_title|project_title|organization_title",
  "error_code": "string|null",
  "error_message": "string|null",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

Indexes:

- `project_id_1_version_number_-1`
- `mint_status_1_created_at_-1`
- `tx_hash_1`
- `token_id_1_contract_address_1`

### 6.2 `mint_jobs`

Purpose: queue and execution state for metadata generation, poster generation, and minting.

```json
{
  "_id": "ObjectId",
  "project_id": "string",
  "mint_record_id": "string",
  "job_type": "prepare_manifest|generate_poster|mint_anchor|sync_receipt",
  "status": "queued|running|succeeded|failed|cancelled",
  "attempt_count": 0,
  "max_attempts": 5,
  "priority": 50,
  "run_after": "datetime",
  "locked_by": "worker-id|null",
  "locked_at": "datetime|null",
  "started_at": "datetime|null",
  "finished_at": "datetime|null",
  "payload": {
    "project_id": "string",
    "mint_record_id": "string",
    "version_number": 1
  },
  "result": {
    "metadata_uri": "string|null",
    "poster_image_uri_public": "string|null",
    "tx_hash": "string|null"
  },
  "error_code": "string|null",
  "error_message": "string|null",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

Indexes:

- `status_1_run_after_1_priority_-1`
- `project_id_1_created_at_-1`
- `mint_record_id_1`

### 6.3 `public_metadata_manifests`

Purpose: canonical public-safe metadata versions before and after mint.

```json
{
  "_id": "ObjectId",
  "project_id": "string",
  "mint_record_id": "string",
  "version_number": 1,
  "schema_version": "tol-nft-1.0",
  "public_token_id": "TOL-2026-000123",
  "metadata_uri": "string",
  "poster_image_uri_public": "string",
  "payload": {
    "name": "string",
    "description": "string",
    "image": "string",
    "external_url": "string",
    "attributes": [],
    "tol": {}
  },
  "build_hash": "sha256:...",
  "certificate_hash": "sha256:...|null",
  "approval_status": "draft|approved|superseded",
  "approved_by": "string|null",
  "approved_at": "datetime|null",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

Indexes:

- `project_id_1_version_number_-1`
- `public_token_id_1`
- `mint_record_id_1`

### 6.4 `mint_approvals`

Purpose: store admin/customer approval checkpoints before mint.

```json
{
  "_id": "ObjectId",
  "project_id": "string",
  "mint_record_id": "string",
  "approval_type": "admin_final|customer_public_safe",
  "status": "pending|approved|rejected|cancelled",
  "approved_by_user_id": "string|null",
  "approved_by_email": "string|null",
  "notes": "string|null",
  "consent_snapshot": {
    "public_title_opt_in": false,
    "approved_poster_opt_in": false,
    "wallet_address": "string|null"
  },
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

Indexes:

- `project_id_1_approval_type_1_status_1`
- `mint_record_id_1`

## 7. Hash rules

Use these exact rules:

- `project_ref_hash = "sha256:" + SHA256(HASH_SALT + ":" + project_id)`
- `household_ref_hash = "sha256:" + SHA256(HASH_SALT + ":" + household_id)` when household exists
- `build_hash = "sha256:" + SHA256(canonical_build_manifest_json)`
- `certificate_hash = "sha256:" + SHA256(canonical_certificate_payload_json)` when certificate exists

Rules:

- `HASH_SALT` must be secret and environment-backed.
- Never hash with a public salt.
- Canonical JSON must be stable-key-sorted before hashing.

## 8. Public-safe NFT metadata schema

The token URI should point to:

- `https://metadata.tomboflight.com/v1/tokens/{public_token_id}.json`

Required shape:

- `name`
- `description`
- `image`
- `external_url`
- `attributes`
- `tol`

Required `tol` fields:

- `schema_version`
- `token_type`
- `package_code`
- `package_lane`
- `project_ref_hash`
- `build_hash`
- `version_number`
- `approval_timestamp`
- `privacy_mode`
- `poster_style`
- `public_title_opt_in`

Optional `tol` fields:

- `household_ref_hash`
- `certificate_hash`
- `public_title`
- `public_title_kind`

Rules:

- Default token name is generic, not a personal name.
- `public_title` is null unless explicitly approved.
- Poster art defaults to abstract or symbolic art.
- Approved portrait poster use is opt-in only.

## 9. Backend service modules

Add these backend services under `backend/app/services/`:

### 9.1 `mint_policy_service.py`

Responsibilities:

- decide whether a package auto-mints
- decide token type from package
- enforce launch toggles
- enforce org opt-in behavior

Core functions:

- `get_package_mint_policy(package_code)`
- `project_is_mint_eligible(project_id)`
- `resolve_token_type(project)`

### 9.2 `public_manifest_service.py`

Responsibilities:

- read project/family/certificate state
- filter to allowlisted public-safe fields
- build canonical metadata JSON
- compute hashes
- write metadata payload to public storage

Core functions:

- `build_public_manifest(project_id, version_number)`
- `compute_build_hash(project_id)`
- `compute_certificate_hash(project_id)`
- `write_public_metadata(public_token_id, payload)`

### 9.3 `poster_asset_service.py`

Responsibilities:

- generate or select poster style
- enforce poster privacy policy
- write poster asset to public storage

Core functions:

- `resolve_poster_policy(project_id)`
- `generate_abstract_cover(project_id, version_number)`
- `generate_symbolic_cover(project_id, version_number)`
- `export_approved_public_poster(project_id, version_number)`

### 9.4 `mint_record_service.py`

Responsibilities:

- create and version internal mint records
- persist approvals
- track mint status changes
- prevent duplicate active versions

Core functions:

- `create_mint_record(project_id)`
- `get_latest_mint_record(project_id)`
- `mark_mint_approved(mint_record_id, ...)`
- `mark_mint_minted(mint_record_id, ...)`
- `mark_mint_failed(mint_record_id, ...)`

### 9.5 `blockchain_mint_service.py`

Responsibilities:

- submit mint transaction to Base
- poll or confirm receipt
- capture token id and tx hash

Core functions:

- `mint_anchor(metadata_uri, recipient_wallet, token_type)`
- `sync_mint_receipt(tx_hash)`

### 9.6 `mint_job_service.py`

Responsibilities:

- enqueue jobs
- claim jobs
- retry failures
- execute prepare/poster/mint stages

Core functions:

- `enqueue_prepare_manifest(project_id, mint_record_id)`
- `enqueue_generate_poster(project_id, mint_record_id)`
- `enqueue_mint_anchor(project_id, mint_record_id)`
- `run_next_job(worker_id)`

## 10. API endpoint list

Add these backend routes under `backend/app/routes/`:

### 10.1 Policy and eligibility

- `GET /mint-policy/packages`
  - public/admin-safe package mint policy list

- `GET /projects/{project_id}/mint-eligibility`
  - customer/admin
  - returns whether project can mint, token type, missing approvals, missing build state

### 10.2 Preparation and approval

- `POST /projects/{project_id}/mint-records/prepare`
  - admin only
  - creates or versions a draft `mint_record`
  - generates draft public manifest

- `POST /projects/{project_id}/mint-records/{mint_record_id}/approve-admin`
  - admin only
  - marks admin final approval

- `POST /projects/{project_id}/mint-records/{mint_record_id}/approve-customer`
  - customer owner or authorized collaborator
  - records public-safe consent, wallet, poster opt-in, title opt-in

### 10.3 Execution

- `POST /projects/{project_id}/mint-records/{mint_record_id}/queue`
  - admin only
  - queues prepare poster + mint jobs

- `POST /mint-jobs/run-next`
  - internal worker only
  - claims and runs the next queued job

- `POST /mint-records/{mint_record_id}/sync`
  - internal/admin
  - syncs mint receipt and final token state

### 10.4 Retrieval

- `GET /projects/{project_id}/mint-records`
  - customer/admin
  - returns all mint versions for that project

- `GET /projects/{project_id}/mint-status`
  - customer/admin
  - returns current status block for dashboard

- `GET /tokens/{public_token_id}`
  - public-safe landing page payload
  - does not expose private archive data

## 11. Route request/response contracts

### 11.1 `GET /projects/{project_id}/mint-eligibility`

Response:

```json
{
  "project_id": "string",
  "package_code": "digital_legacy_portrait",
  "package_lane": "portrait",
  "mint_policy": {
    "auto_mint_enabled": true,
    "token_type": "portrait_anchor",
    "requires_customer_public_safe_approval": true
  },
  "eligible": true,
  "reasons": [],
  "latest_mint_record_id": "string|null"
}
```

### 11.2 `POST /projects/{project_id}/mint-records/prepare`

Request:

```json
{
  "version_strategy": "new_version_if_needed",
  "poster_style": "abstract_cover",
  "public_title_opt_in": false,
  "public_title": null
}
```

Response:

```json
{
  "mint_record_id": "string",
  "version_number": 1,
  "status": "pending_approval",
  "metadata_uri": "https://metadata.tomboflight.com/v1/tokens/TOL-2026-000123.json",
  "poster_image_uri_public": "https://metadata.tomboflight.com/v1/posters/TOL-2026-000123.jpg"
}
```

### 11.3 `GET /projects/{project_id}/mint-status`

Response:

```json
{
  "project_id": "string",
  "mint_enabled": true,
  "latest": {
    "mint_record_id": "string",
    "mint_status": "minted",
    "token_type": "portrait_anchor",
    "version_number": 1,
    "chain": "base-mainnet",
    "contract_address": "0x...",
    "token_id": "123",
    "tx_hash": "0x...",
    "metadata_uri": "https://metadata.tomboflight.com/v1/tokens/TOL-2026-000123.json",
    "poster_image_uri_public": "https://metadata.tomboflight.com/v1/posters/TOL-2026-000123.jpg",
    "minted_at": "2026-03-29T18:25:05Z"
  },
  "history": []
}
```

## 12. Job state machine

Mint record states:

- `pending_approval`
- `approved`
- `queued`
- `minting`
- `minted`
- `failed`
- `superseded`
- `cancelled`

Job states:

- `queued`
- `running`
- `succeeded`
- `failed`
- `cancelled`

Execution sequence:

1. prepare manifest
2. generate poster
3. mint anchor
4. sync receipt
5. update dashboard-facing status

Retry rules:

- receipt sync retries allowed
- mint transaction submission retries only before tx hash is produced
- failed jobs keep error codes and messages

## 13. Dashboard display contract

Customer dashboard NFT panel should show:

- token type
- version number
- mint status
- chain
- contract address
- token id
- tx hash
- metadata link
- poster preview
- wallet address if connected

Suggested front-end API source:

- `GET /projects/{project_id}/mint-status`

UI states:

- `not_included`
- `eligible_waiting_for_build`
- `waiting_for_approval`
- `queued`
- `minting`
- `minted`
- `failed`

## 14. Versioning rules

Use these version rules:

- typo fix in private data only: no remint
- major approved public-safe update: new version only when explicitly chosen
- previous token remains historical record
- latest mint record becomes dashboard primary version

## 15. Security and approval rules

Required rules:

- admin final approval required before queueing mint
- customer public-safe approval required when public title, poster opt-in, or wallet assignment is involved
- customer cannot mint without an entitled project
- customer cannot mint another customer’s project
- private files never leave protected storage for public metadata generation
- public manifest service must use an explicit allowlist, never a blacklist

## 16. Proposed file layout

Add these files:

- `backend/app/services/mint_policy_service.py`
- `backend/app/services/public_manifest_service.py`
- `backend/app/services/poster_asset_service.py`
- `backend/app/services/mint_record_service.py`
- `backend/app/services/blockchain_mint_service.py`
- `backend/app/services/mint_job_service.py`
- `backend/app/routes/mint_policy.py`
- `backend/app/routes/mint_records.py`
- `backend/app/routes/mint_jobs.py`
- `backend/app/schemas/mint_record.py`
- `backend/app/schemas/public_manifest.py`
- `backend/app/schemas/mint_job.py`

## 17. Implementation order

Build order:

1. collection schemas and indexes
2. mint policy service
3. public manifest generator
4. poster asset generator
5. mint record service
6. approval endpoints
7. job queue and worker route
8. blockchain mint service
9. dashboard NFT panel
10. legal copy alignment

## 18. Done criteria

This spec is complete when:

- metadata generation is public-safe by allowlist
- approved packages mint only according to policy
- no private archive fields appear in public metadata
- minting is versioned and auditable
- dashboard shows mint state and history correctly
- Stripe checkout metadata can target an existing project for upgrades
