# Continuity Kernel Phase 6I Runtime Route Verification

- Route tested: `GET /admin/continuity-kernel/preview`
- Verified as GET-only; POST/PUT/PATCH/DELETE are not available for this route.
- Feature flag behavior tested via `CONTINUITY_KERNEL_READONLY_ADMIN_PREVIEW_ENABLED`.
- Disabled-by-default behavior tested for missing/off/invalid flag values.
- Disabled responses tested to ensure no prohibited actions are returned and no preview payload is built.
- Admin-only behavior tested using the existing admin permission guard (`require_permission("admin.control.view")`).
- Non-admin runtime access tested as denied.
- Enabled behavior tested using explicit true-like values and validated as read-only response envelope only.
- Enabled response tested to contain no apply/schedule/execute/rollback actions, no repair execution actions, and no mutation actions.
- Enabled response tested to contain no full `rollback_plan`, no full override `reason_detail`, no full justification `reason_detail`, and no full `audit_context`.
- Route input surface tested to ensure no acceptance path for `approval_fixture_payload`, `test_context`, or `validator_result` as approval input.
- No customer-facing Continuity Kernel preview route exists.
- No mutation behavior is added: no database writes, no mint queueing, no certificate/customer/workspace/entitlement mutation, and no executable repair script entrypoints.

## Runtime test limitations

- Runtime route assertions run only when `fastapi` and `fastapi.testclient` are importable in the test environment.
- In environments without FastAPI/TestClient, runtime-only checks are skipped with explicit skip reasons.
- Static contract guardrails remain strict and continue to run regardless of runtime dependency availability.
