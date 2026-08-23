# Continuity Kernel Phase 12 — Production Security Closure

Date: 2026-08-23

Runtime: `12.0.0`

Governed action registry: 38 actions

## Outcome

Phase 12 closes the concrete security defects found in the post-Phase-11 backend audit without changing production customer records as part of engineering verification. It makes privileged execution fail closed, removes broad write authorization, repairs authentication races, requires publication-safe uploaded portraits, makes critical startup controls visible, adds shared production authentication throttling, and introduces a truthful CEO-only workflow for reconciling identities that were manually removed outside governance.

The new orphan-identity action does not claim that an earlier manual MongoDB deletion was governed. It records `governed_deletion_observed=false`, preserves required business and evidence records, and issues a reconciliation receipt rather than a deletion receipt.

## Privileged mutation boundary

- The 17 route modules that used broad `admin.access` authorization now require job-scoped read, write, billing, intake, audit, upload-review, or mint permissions.
- Covered legacy privileged writes fail with `409 continuity_kernel_required` in production until a registered Kernel adapter exists.
- The Kernel execution endpoint and read-only preview endpoints remain available.
- Direct production mutations for mint execution, global lineage/identity creation, match decisions, maintenance, and administrator intake-status changes cannot bypass approval, idempotency, the kill switch, or evidence recording.

## Authentication and token correctness

- MFA enrollment and login-challenge tokens are bound to the current `session_token_version`; revoking sessions invalidates an outstanding MFA challenge.
- Recovery codes are consumed with an atomic conditional `$pull`, so two concurrent requests cannot successfully use the same recovery code.
- Password-reset consumption uses a compare-and-set on identity, token digest, expiry, and account status.
- Password-reset links carry the token in a URL fragment. The account-security page reads the fragment and immediately removes it from browser-visible history.
- Production authentication request counters and lockouts use shared MongoDB state with hashed principals and TTL cleanup. Development and unit-test environments retain the in-process implementation.

## Upload publication gate

An uploaded portrait is eligible for poster publication only when all of the following are true:

- malware scan status is clean;
- the upload is not quarantined;
- cinematic use is explicitly approved;
- verification status is approved;
- consent status is approved.

Failing any requirement leaves the upload unavailable to public poster selection.

## Startup and readiness

- Unique Stripe event, order, finance-event, public-token, Continuity operation, and Continuity idempotency indexes fail startup when they cannot be created.
- Canonical administrator bootstrap failure stops production startup instead of allowing an apparently healthy API to serve.
- The canonical CEO diagnostics response includes the exact protected operational-readiness result, degraded reasons, component state, and deployed release identifier.
- Public health endpoints continue to disclose availability without exposing protected configuration details.

## Resumable evidence

Kernel request, approval, rejection, scheduling, failure, execution, and audit-closure stages have durable evidence checkpoints. Event identifiers and audit identifiers are deterministic per operation, stage, and retry attempt. If an event or audit write succeeds but the parent operation checkpoint fails, retrying the same idempotent operation repairs the missing checkpoint without duplicating the canonical evidence row.

Business execution does not begin until request, approval, and scheduling evidence is complete. Post-execution evidence marked incomplete is replayed before audit closure.

## Post-hoc manual-removal reconciliation

The CEO-only `orphan_identity_reconciliation` action is for a user document that is already absent. Preview is read-only and execution requires:

1. the removed identity email;
2. an allowed reason category and operational reason;
3. the exact phrase `RECONCILE MANUAL REMOVAL`;
4. an explicit acknowledgement;
5. a final browser confirmation;
6. Continuity Kernel request, approval, validation, execution, and evidence.

Execution blocks if a live identity exists, the target is the canonical CEO, a governed deletion tombstone already exists, or a completed reconciliation already exists. It revokes surviving role assignments, permission overrides, memberships, invitations, vault access, uploads, impersonation sessions, mint work, approvals, and active maintenance subscriptions that resolve to the former identity. It preserves orders, billing history, corporate ownership, certificates, delivery records, security evidence, audit logs, and Continuity evidence.

Because the original MongoDB removal happened outside the application, Phase 12 cannot prove the exact time or actor of that deletion. The receipt explicitly labels the operation as post-hoc evidence and never backdates or fabricates a governed deletion.

## Hosting-header boundary

The API already emits HSTS on secure requests plus anti-framing, content-type, referrer, permissions, and no-store headers. The public static site is deployed through GitHub Pages and currently passes through Cloudflare. GitHub Pages does not provide a repository-level mechanism for arbitrary response headers, so HTTP-level headers for static pages require an edge configuration change or migration to a host that supports custom headers. HTML CSP and referrer meta policies remain defense in depth but are not represented as a completed HTTP-header control.

This external hosting control remains an explicit production-readiness item. Phase 12 does not misrepresent it as closed by adding an unused `_headers` file.

## Deployment and production verification

Before production reconciliation:

1. Merge Phase 12 only after backend, contract, browser, dependency, static-analysis, syntax, and secret-pattern checks pass.
2. Confirm the backend and static deployment contain the Phase 12 commit.
3. Sign in as the canonical CEO and review protected operational diagnostics.
4. Run the orphan-identity preview for the exact former Marquis identity.
5. Confirm the live user document is absent and review every surviving dependency count.
6. Execute only after the CEO provides action-time confirmation for the destructive reconciliation.
7. Save the Continuity operation ID and reconciliation ID and close the operation audit only when evidence status is complete.

Engineering work in the pull request performs no production customer mutation, does not cancel a live subscription, and does not create a Marquis reconciliation receipt before the deployed CEO-confirmed execution.
