# Continuity Kernel Phase 11 — Backend Security Correction

Date: 2026-08-22

Runtime: `11.0.0`

Governed action registry: 37 actions

## Outcome

Phase 11 closes the blocker-class findings from the post-Phase-10 backend audit. It preserves real customer checkout and CEO execution while removing alternate authority paths that could manufacture a second master administrator, claim a passwordless pending account, fabricate a paid order, bypass covered Continuity Kernel execution, acknowledge an incomplete Stripe webhook, or strand permanent deletion between external and database writes.

MFA remains optional for every account. An account that opts in must complete MFA for future sessions and may disable it only after password plus authenticator or recovery-code verification.

## CEO singleton authority

- `l.robinson@tomboflight.com` is the sole canonical CEO Master Administrator identity.
- Only `ceo_master_admin` (and its canonical compatibility alias) can receive wildcard capabilities and permissions.
- A noncanonical `super_admin` label is deprecated data with no administrator or wildcard authority, even if a stale role assignment or permission override contains `*`.
- The canonical CEO email, active status, role, access tier, and department role cannot be changed through account controls.
- CEO password/security resets require the canonical CEO actor.
- The canonical CEO remains an administrator if stale role labels are temporarily missing; startup reconciliation and read-time access resolution converge on the same invariant.

## Secure account activation

Public signup, checkout-created accounts, and CEO-created customer accounts begin as passwordless `pending_activation` identities. Password installation requires a short-lived activation token delivered to the account email.

- Only a SHA-256 token digest bound to the production `SECRET_KEY` is stored.
- The link carries the token in a URL fragment, not a query string, so it is not sent to the web server, proxy logs, or Referer headers.
- The browser reads the fragment and immediately removes it with `history.replaceState`.
- Activation uses a compare-and-set on pending status, empty password, and the exact token digest, making the token single-use even under concurrent requests.
- Startup enforces a unique normalized email index and a unique partial index for live activation-token digests.
- A delivery failure leaves the account pending and is reported as a failure; it never creates a usable credential.
- Administrator-created package grants create an entitlement without creating a paid order or changing Stripe payment history.

## Covered mutation boundary

Covered legacy mutations now fail with `409 continuity_kernel_required` and point callers to `/admin/control-center/kernel/execute`. This includes Control Center writes, protected Stripe writes, administrator password/security resets, manual paid-order creation, paid-package repair, direct entitlement apply, and direct administrator account creation.

Read-only routes and exact preview routes remain available. Customer-owned profile, billing, upload, vault, household, and workspace actions remain available under their existing authorization rules; Phase 11 does not route normal customer activity through an administrator Kernel.

The `legacy_admin_remediation` action brings the remaining privileged-account suspension into the persisted Kernel state machine. The target identity must match the read-only review result before execution.

Manual paid-order creation is removed from the service implementation. A paid order must come from verified Stripe state. A CEO may still grant an authorized complimentary, promotional, or internal-validation package, but that operation explicitly records `payment_record_created=false` and `stripe_payment_mutated=false`.

## Stripe recovery

Stripe event claims are retryable leases, not completion markers.

- A relevant event is marked processed only after its authoritative order or maintenance handler persists the result.
- Failure clears the processing claim, records a minimized retryable failure, omits `processed_at`, and returns HTTP 503 so Stripe retries.
- A Checkout Session may be a package purchase or a maintenance subscription; success by the relevant handler is sufficient and an expected rejection by the other handler is not treated as failure.
- Subscription and invoice lifecycle events that do not update their maintenance record are retryable failures.
- Permanent deletion derives a stable provider idempotency key per subscription, so an account with multiple subscriptions cannot collide on one Stripe idempotency key.

## Resumable permanent deletion

Permanent deletion remains irreversible, CEO-only, and separately confirmed twice. Execution now creates or reuses a stable MongoDB tombstone before external cancellation, revokes login before the first side effect, and records each phase.

Retrying the same failed Kernel operation resumes the same deletion ID. Stripe cancellation failure leaves `status=failed_retryable` and the identity locked. If identity erasure succeeds but audit persistence fails, the tombstone remains `status=audit_pending`; retry closes the missing audit evidence without restoring credentials or repeating identity destruction. Paid orders, billing history, corporate ownership records, issued certificates, delivery records, security evidence, and Continuity/audit evidence remain preserved.

## Operational readiness and disclosure boundary

Public `/health`, `/health/live`, `/health/ready`, the production root, and database-error responses expose platform availability without revealing which security integrations are absent.

Authenticated canonical CEO access to `/health/operational` reports:

- database connectivity;
- production signing-key validity without exposing the key;
- Stripe publishable, secret, and webhook configuration;
- Postmark transactional-email configuration;
- an active upload scanner hook and fail-closed/quarantine posture;
- readable and writable persistent private-upload storage;
- Continuity execution kill-switch state;
- deployed version and commit identifier;
- optional NFT runtime state without making NFT execution a core-readiness requirement.

The endpoint returns HTTP 503 when a required production control is incomplete. The public platform readiness endpoint remains compatible with Render health checks and continues to represent database-serving readiness.

## Deployment gates

Before treating Phase 11 as operationally ready:

1. Set a unique production `SECRET_KEY` of at least 32 bytes and do not reuse the value in another environment.
2. Configure `STRIPE_PUBLISHABLE_KEY`, `STRIPE_SECRET_KEY`, and `STRIPE_WEBHOOK_SECRET`.
3. Configure a verified Postmark server token and sender.
4. Deploy ClamAV on a private network, set `UPLOAD_SCAN_HOOK=app.services.clamav_upload_scanner:scan`, and configure `UPLOAD_CLAMAV_HOST` plus `UPLOAD_CLAMAV_PORT`. The adapter uses ClamAV's framed `INSTREAM` protocol and refuses public-network scanner peers by default. The legacy scanner command setting is intentionally not executed.
5. Mount a readable and writable persistent disk through `RENDER_DISK_MOUNT_PATH` for private uploads.
6. Keep `CONTINUITY_EXECUTION_KILL_SWITCH` unset for normal execution and set it only for emergency shutdown.
7. Confirm a deployment commit identifier is present. Render normally supplies `RENDER_GIT_COMMIT`.
8. Confirm the unique user-email index builds successfully. Duplicate historical email identities must be reviewed and corrected rather than silently accepted.
9. Run an authenticated production walkthrough after deployment. Engineering verification in this pull request performs no production customer mutation and does not permanently delete Marquis or any other account.

Provider encryption, backup, restore, edge-header, and independent penetration-test evidence remain separate launch evidence. Phase 11 does not claim SOC 2, ISO 27001, HIPAA, PCI DSS certification, end-to-end encryption, or an external penetration test.
