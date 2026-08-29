# Backend Runbook

## 1) Environment

1. Copy `.env.example` to `.env`.
2. Set required values for your target environment:
   - **Mongo**: `MONGODB_URI`, `MONGODB_DB_NAME`
   - **Auth/JWT**: `SECRET_KEY`, `ALGORITHM`, token expiry values
   - **Private admin identities**: `ADMIN_IDENTITY_REGISTRY_JSON` in the hosting provider's secret store. It is required in staging/production and must never be committed with real names or email addresses.
   - **R2/storage** (if using object storage): `R2_*` variables
   - **Stripe** (billing/webhooks): `STRIPE_*` variables
   - **Mint runtime flags/config**: `NFT_MINT_ENABLED`, `NFT_ORG_MINT_ENABLED`, `NFT_MINT_WORKER_ENABLED`, `NFT_MINT_WORKER_POLL_SECONDS`, optional exact Stripe NFT Price IDs, and NFT chain/contract fields. `NFT_AUTO_MINT_ON_REVIEW_ENABLED` must remain `false`.
   - **Email/Postmark** (if enabled): `POSTMARK_*` variables

`ADMIN_IDENTITY_REGISTRY_JSON` uses this shape. Exactly one active identity must
hold `ceo_master_admin`; every other active role must be job-scoped. Replace the
angle-bracket placeholders only in the protected runtime secret:

```json
{
  "active_officers": [
    {
      "email": "<private CEO email>",
      "role_codes": ["ceo_master_admin", "executive_tech_admin"],
      "profile": {
        "full_name": "<private name>",
        "business_title": "CEO",
        "access_tier": "ceo_master_admin",
        "department_role": "executive_tech_admin"
      }
    }
  ],
  "retired_officers": []
}
```

The audit-only `enforce_account_separation.py` script also requires
`ACCOUNT_SEPARATION_AUDIT_TARGETS_JSON` when it is run. Keep its `genesis`,
`personal_accounts`, and `target_personal_account_experience` mappings in the
operator's protected environment; they are intentionally absent from source
and are not required for normal API startup.

## 2) Local setup

```bash
python -m pip install -r requirements.txt
```

## 3) Safe local startup

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Notes:
- If Mongo is unavailable, startup continues in degraded mode; liveness remains up while readiness fails, and DB-backed routes return structured `503 database_unavailable` responses until connectivity is restored.
- Keep `NFT_MINT_ENABLED=false` for local development unless all mint dependencies are configured.
- No base package includes an NFT. The delivered-profile, paid add-on, customer wallet consent, CEO approval, and controlled queue contract is documented in `docs/governance/continuity_kernel_phase15_nft_addon_mint_console.md`.

## 4) Test command

```bash
python -m pytest -q tests
```
