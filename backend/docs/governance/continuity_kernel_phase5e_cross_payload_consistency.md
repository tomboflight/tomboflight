# Continuity Kernel Phase 5E - Cross-Payload Consistency

This document defines isolated, fail-closed cross-payload consistency rules for the Continuity Kernel validator.

## Scope

- Phase 5E only strengthens isolated validation and tests.
- Phase 5E does not wire the validator into runtime routes.
- Phase 5E does not create apply mode.
- Phase 5E does not create repair scripts.
- Phase 5E does not touch live data.

## 1) Evidence packet ↔ authorization decision

Fail closed if any of the following are not satisfied:

- `evidence.repair_category` must match `authorization.repair_category`.
- `evidence.target_type` must match `authorization.target_type`.
- `evidence.target_id` must match `authorization.target_id`.
- `evidence.approval_role` must be compatible with `authorization.actor_role`.
- `evidence.approved_by` must match `authorization.actor_user_id`, or the mismatch must be explicitly justified in `audit_context`.

## 2) Evidence packet ↔ apply transition

Fail closed if any of the following are not satisfied:

- `evidence.evidence_packet_id` must match `transition.evidence_packet_id`.
- `transition.audit_context` must exist.
- transition state must be allowed.
- transition actor must be traceable to an approved actor, executor, or system-reviewed actor.

## 3) Evidence packet ↔ rollback verification

Fail closed if any of the following are not satisfied:

- `evidence.evidence_packet_id` must match `rollback.evidence_packet_id`.
- `evidence.target_type` must match `rollback.target_type`.
- `evidence.target_id` must match `rollback.target_id`.
- `rollback_plan` must reference `before_snapshot` or `before_snapshot_ref`.
- rollback `audit_context` must exist.

## 4) Idempotency

Fail closed when:

- idempotency key is blank.
- idempotency key is consumed.
- idempotency key is reused.

## 5) Risk and separation of duties

Fail closed when:

- high-risk requests use the same requester and executor.
- same requester/executor is present without `SUPERADMIN` emergency override in `audit_context`.
- `marketing_admin` / `CMO` is used for approval.

## 6) Prohibited cross-payload actions

Fail closed if any payload contains language suggesting:

- queue mint work directly
- mutate immutable issued certificate
- delete customer record
- bypass auth
- bypass entitlement
- bypass verification
- bypass mint readiness
- bypass audit logging
- bypass officer permissions
- hard-code customer-specific production values

## 7) Non-operational guardrail

- Phase 5E does not wire the validator into runtime routes.
- Phase 5E does not create apply mode.
- Phase 5E does not create repair scripts.
- Phase 5E does not touch live data.
- Phase 5E only strengthens isolated validation and tests.
