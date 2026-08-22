# Continuity Kernel 10.1 — Account Closure and Permanent Deletion

Runtime: `10.1.0`

## Decision

Tomb of Light uses three visibly separate account lifecycle controls:

1. **Billing Hold** sets the account to `suspended`, disables login, records the billing-hold reason, revokes active sessions, and remains recoverable with **Restore Access**.
2. **Archive** disables login and archives account/workspace access while retaining a recoverable record. It is appropriate when access may be reopened.
3. **Permanent Delete** is an irreversible CEO-only Continuity Kernel operation. It destroys the authentication identity and personal account profile, revokes roles, permissions, memberships, entitlements, invitations, and vault grants, permanently closes owned workspace access, and cannot be restored.

If an owned workspace still has an active Stripe maintenance subscription, permanent deletion cancels it immediately before MongoDB identity destruction. If Stripe cancellation fails, the Kernel fails closed and does not issue a deletion-success receipt.

Permanent deletion is not presented as a way to erase required business evidence. Paid orders, billing history, corporate ownership records, issued certificates, delivery records, security evidence, and audit history remain under their applicable retention requirements. A separate data-retention or privacy-erasure process may dispose of retained content when no legal, security, ownership, or contractual reason remains.

## Required confirmation sequence

Permanent deletion fails closed unless all of the following are present:

- canonical CEO Master Administrator authorization;
- an allowed reason category: verified customer request, policy violation, security incident, or CEO-authorized company decision;
- an operational reason;
- the exact target account email;
- the first confirmation checkbox, enforced again by the backend;
- a separate final-warning dialog stating that the account will be permanently closed;
- the exact phrase `PERMANENTLY DELETE`;
- the final irreversible-action checkbox, enforced again by the backend.

The canonical CEO Master Administrator identity is protected from routine lifecycle controls and permanent deletion.

## MongoDB execution evidence

The operation is registered as `account_permanent_delete` and runs only through the persisted Continuity Kernel state machine. Evidence is stored in:

- `continuity_operations` — request, approval, state transitions, before/after snapshots, execution result, and evidence status;
- `continuity_events` — immutable-style operational event sequence;
- `account_deletion_tombstones` — deletion ID, Continuity operation ID, target user ID, SHA-256 of the former email, reason category, actor, affected-record counts, preserved-record categories, and completion state;
- `audit_logs` — accountable administrative and Continuity audit entries.

The raw former email is not stored in the deletion tombstone. The surviving user row becomes a non-login referential tombstone with a non-routable placeholder email. This preserves database references without preserving usable credentials or a restorable account.

Password-reset issuance is blocked for inactive and permanently deleted identities. Active impersonation and experience sessions are closed; project share/link keys, pending link requests, vault grants, and active mint work are revoked or stopped.

The CEO overview excludes these tombstones from **Total Users** and reports them separately as **Permanent Deletions**. The Users queue can locate a tombstone by user ID or deletion ID, recent completed deletion receipts can be reopened from Governed Operations, and the complete evidence history remains in MongoDB.

## Failure posture

The deletion tombstone is written with `status=started` before linked access is closed. Authentication identity destruction happens last and uses an exact-email compare-and-set. The tombstone is then finalized with `status=completed` and record counts. If execution is interrupted, the incomplete tombstone and failed Continuity operation remain visible for governed remediation.

No permanent-deletion success receipt is shown unless the Kernel reports both `execution_outcome=success` and `evidence_recording_status=complete`.
