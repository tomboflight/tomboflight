# Continuity Kernel Phase 9 — Control Surface and Security Completion

Date: 2026-08-21

Runtime: `9.0.0`

Control Center action registry: 35 governed actions

## Outcome

Phase 9 extends the Phase 8 operational runtime from 27 to 35 actions and makes the live CEO Control Center use the Continuity Kernel for every business-data write exposed by its interface. Read-only fetches, previews, report downloads, navigation, and external Stripe dashboard links remain direct because they do not mutate Tomb of Light business data.

This is an execution runtime, not a dry-run adapter. A confirmed canonical CEO one-step request performs request, structured founder override, validation, execution, evidence recording, and audit state transitions. The emergency kill switch still fails closed.

## Newly governed control-surface actions

| Action | System boundary | Execution protection |
|---|---|---|
| `manual_fulfillment` | Order/manual fulfillment | Kernel and downstream idempotency |
| `stripe_operation` | Stripe customer, invoice, payment link, subscription, portal operations | Kernel and Stripe idempotency |
| `customer_account_create` | Customer identity record | Super-admin category and evidence packet |
| `user_profile_update` | Customer identity/profile | Super-admin category and evidence packet |
| `user_password_reset` | Identity store and verified email delivery | No raw reset token; delivery failure becomes partial failure |
| `project_ownership_transfer` | Project/customer ownership | Explicit reason, confirmation, before/after evidence |
| `impersonation_start` | Read-only customer context | Audited, expiring session; no identity replacement |
| `impersonation_stop` | Read-only customer context | Audited session closure |

The pre-existing Phase 8 action registry continues to cover case mutations, safe bulk repairs, package changes, package/service lifecycle, officer permissions, account lifecycle, and specialized case repair.

## Control Center boundary

- Mutation buttons call `/admin/control-center/kernel/execute` for canonical CEO one-step execution or create a governed operation for officer review.
- Each mutation requires an operation reason and an explicit browser confirmation.
- The Kernel owns the downstream idempotency key; a caller cannot substitute another provider key through free-form parameters.
- Stripe read-only customer history and the external Stripe dashboard link remain non-mutating reads.
- Package and service previews remain non-mutating previews.
- Customer preview is explicitly read-only. The previous “Enable Admin Editing” control was removed because its session flag was not an authorization boundary for actual write endpoints.
- Legacy direct mutation API routes remain available for compatibility with non-Control-Center callers. Retiring or universally mediating those routes is a separate migration; Phase 9 guarantees the live Control Center boundary.

## Security changes

- Login and signup fail closed when the identity database is unavailable; no preview account or fallback bearer token is issued.
- Authenticator MFA is available as an account-level opt-in for customers, officers, and administrators. Accounts without MFA can authenticate with their password; accounts that enable MFA must complete it at sign-in and may later disable it after password and authenticator/recovery-code verification.
- Production HMAC signing secrets must be unique and at least 32 bytes; allowed JWT algorithms are restricted to `HS256`, `HS384`, and `HS512`.
- Browser bearer and user context are stored in `sessionStorage`, with legacy persistent copies removed.
- Overview payloads are reduced server-side to finance, operations, or marketing domains for restricted officer roles.
- Administrator-assisted password reset never exposes the reset token. The verified account email receives the link, and an unconfirmed email delivery is recorded as a partial failure rather than success.
- Upload scanning defaults to fail closed. Infected files, scanner errors, and unavailable scanning enter quarantine.
- Customer, administrative, and general public application pages include a restrictive Content Security Policy; inline scripts are authorized by exact hashes. The private Sip & Paint page has completed its sanitized migration: promotion values are no longer present in public source, recipient access uses a one-time server-verified link, and the protected runtime delivers an eligible package value only to the invited mailbox. `pricing.html` and the remaining legacy invite page continue as separately managed commercial surfaces pending their own migration.
- Pinned dependencies were upgraded and the legacy JWT dependency was removed. `pip-audit` reports no known vulnerabilities for `backend/requirements.txt` at this revision.
- Pull requests now run the dependency audit plus Phase 9 runtime and security suites.

## Deployment gates

These are operational requirements, not optional claims:

1. Set `SECRET_KEY` to a unique random value of at least 32 bytes before the backend restarts.
2. Keep `UPLOAD_SCAN_FAIL_CLOSED=true` and configure `UPLOAD_SCAN_HOOK`. Production remains fail closed even if the flag is mistakenly set false; without a working scanner, new uploads intentionally remain quarantined.
3. Verify the Postmark server token, sender, and message stream. Password-reset delivery failures now surface in Kernel evidence instead of reporting false success.
4. Configure static-host response headers at Cloudflare (or the active edge): HSTS and a header-level CSP containing `frame-ancestors`. A CSP meta element cannot enforce `frame-ancestors`.
5. Obtain and retain provider evidence for database/object-storage encryption at rest, access logging, encrypted backups, and restore testing before making those claims publicly.
6. Complete an authenticated production browser walkthrough after deployment. Mutation dialogs may be opened and canceled for wiring verification; a real customer write requires a separately identified record, intended effect, and confirmation.
7. Schedule an independent penetration test before claiming external security validation. Tomb of Light does not currently claim SOC 2, ISO 27001, HIPAA, PCI DSS certification, or end-to-end encryption.

## Verification evidence

- Repository suite: 1,739 tests passed, 66 subtests passed, 2 intentionally skipped.
- Phase 9 CI security, runtime, and Control Center focus: 105 tests passed.
- JavaScript syntax, Python compilation, and whitespace/diff checks passed.
- Dependency audit: no known vulnerabilities found.

No production customer mutation was performed as part of this engineering verification.
