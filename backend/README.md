# Backend Runbook

## 1) Environment

1. Copy `.env.example` to `.env`.
2. Set required values for your target environment:
   - **Mongo**: `MONGODB_URI`, `MONGODB_DB_NAME`
   - **Auth/JWT**: `SECRET_KEY`, `ALGORITHM`, token expiry values
   - **R2/storage** (if using object storage): `R2_*` variables
   - **Stripe** (billing/webhooks): `STRIPE_*` variables
   - **Mint runtime flags/config**: `NFT_MINT_ENABLED`, `NFT_ORG_MINT_ENABLED`, `NFT_MINT_WORKER_ENABLED`, `NFT_MINT_WORKER_POLL_SECONDS`, optional exact Stripe NFT Price IDs, and NFT chain/contract fields. `NFT_AUTO_MINT_ON_REVIEW_ENABLED` must remain `false`.
   - **Email/Postmark** (if enabled): `POSTMARK_*` variables

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
