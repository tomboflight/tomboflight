# Continuity Kernel Phase 15 — NFT Add-On Mint Console

## Binding business rule

- No Tomb of Light base package includes an NFT.
- A customer profile must be complete and delivered before NFT checkout unlocks.
- The first mint requires **NFT Lineage Record** (`nft_lineage_record`, $499).
- Every later mint requires **Additional NFT Copy / Mint** (`additional_nft_copy_mint`, $399).
- **NFT Metadata Revision** (`nft_metadata_revision`, $149) is a revision credit and cannot authorize a mint.
- A paid Stripe checkout creates only a verified project-scoped credit. It never prepares, approves, queues, or executes a mint.
- Customer wallet/public-safe consent and CEO final approval are separate authenticated acts.
- Private vault files and private family information stay off-chain.

## Customer sequence

1. Tomb of Light completes and delivers the profile.
2. The dashboard unlocks only the add-on valid for the current NFT state.
3. The authenticated backend validates the customer, delivered project, mint sequence, and runtime before it creates a hosted Stripe Checkout Session. Raw NFT payment links are not published in the frontend.
4. Stripe confirms the exact catalog product and price against the signed-in customer and project context.
5. Tomb of Light records a verified project-and-sequence-scoped credit. No mint job is created. A sparse unique credit key closes concurrent duplicate-checkout races.
6. After Tomb of Light prepares the approval record, the billing owner or co-owner signs in and supplies the public Base recipient wallet.
7. The customer explicitly approves the public-safe metadata. Private keys and recovery phrases are rejected.

## CEO sequence

Use the selected customer case in Admin Control Center:

1. **Open Mint Review** — confirms profile completion, verified payment, project linkage, entitlement, and uploads; sets preparation state only.
2. **Prepare NFT Approval** — atomically claims exactly one valid paid mint credit and creates the approval record.
3. Wait for the customer wallet/public-safe consent shown in the customer dashboard.
4. **CEO Final Approve** — records the CEO approval independently of customer consent.
5. **Queue Approved NFT** — creates the four controlled jobs only when both approvals and all readiness gates pass.
6. The controlled worker prepares metadata, creates the poster, submits `safeMint`, and syncs the receipt.

All three mutating Admin Control Center actions run through the Continuity Kernel. Checkout is never an execution path.

## Production activation

Keep execution disabled until the contract owner wallet, Base ETH balance, R2 public artifact paths, and runtime configuration have been verified. Then set these Render secrets/settings:

```text
NFT_AUTO_MINT_ON_REVIEW_ENABLED=false
NFT_MINT_ENABLED=true
NFT_MINT_WORKER_ENABLED=true
NFT_MINT_WORKER_POLL_SECONDS=15
NFT_MINT_FUNCTION_NAME=safeMint
NFT_LEGACY_PAYMENT_LINKS_DISABLED=true
```

The existing validated settings are also required: `NFT_CHAIN`, `NFT_RPC_URL`, `NFT_CONTRACT_ADDRESS`, `NFT_CONTRACT_ABI_JSON`, `NFT_MINTER_PRIVATE_KEY`, `HASH_SALT`, `METADATA_BASE_URL`, `POSTER_BASE_URL`, `PUBLIC_TOKEN_EXTERNAL_BASE_URL`, and the R2 credentials/buckets.

The authenticated checkout resolver can locate the exact active Stripe price from the existing product name and amount. For an unambiguous fail-closed deployment, set the optional Price IDs `STRIPE_NFT_LINEAGE_RECORD_PRICE_ID`, `STRIPE_ADDITIONAL_NFT_MINT_PRICE_ID`, and `STRIPE_NFT_METADATA_REVISION_PRICE_ID`. A configured Price ID is revalidated against the server catalog before every Checkout Session is created.

Before setting `NFT_LEGACY_PAYMENT_LINKS_DISABLED=true`, deactivate the three former public NFT Payment Links in Stripe. Production readiness and new NFT checkout stay blocked until that operator confirmation is present. Do not set the flag merely to clear readiness; it records a completed Stripe-side control.

`NFT_MINTER_PRIVATE_KEY` must be stored only as a secret in Render. It must belong to the wallet that owns the configured contract and must never be pasted into source code, a pull request, logs, screenshots, or customer forms. The wallet needs enough Base ETH for network fees.

Startup fails closed when the worker is enabled without minting, when legacy auto-mint-on-review is enabled, or when the ABI does not expose a supported recipient-and-metadata mint function.

## Recovery and rollback

- Set `NFT_MINT_WORKER_ENABLED=false` to stop new queued job execution while preserving approvals and queued evidence.
- Set `NFT_MINT_ENABLED=false` to disable blockchain execution entirely.
- A failed or ambiguous blockchain submission must be reviewed from its existing mint record and transaction hash. Do not sell or consume a second credit merely to retry a technical failure.
- A paid checkout without valid delivered-project context is preserved as an escalated paid order with a blocked credit so staff can reconcile or refund it without minting.

## Verification contract

Phase 15 tests assert that every base package has zero included anchors, public raw NFT payment links are absent, authenticated Checkout Sessions enforce the delivered-profile gate, exact Stripe prices are verified, duplicate mint-sequence credits fail closed, metadata revisions cannot authorize mints, manual fee overrides cannot unlock execution, customer and CEO approvals stay separate, and the worker processes only previously queued jobs.
