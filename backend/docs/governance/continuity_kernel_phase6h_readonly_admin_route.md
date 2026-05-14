# Continuity Kernel Phase 6H Read-Only Admin Route

- Route path: `GET /admin/continuity-kernel/preview`
- GET-only endpoint; no POST/PUT/PATCH/DELETE variant exists.
- Admin-only access via existing admin permission dependency.
- Feature flag behavior is fail-closed through `CONTINUITY_KERNEL_READONLY_ADMIN_PREVIEW_ENABLED`.
- Missing flag, off flag, and invalid flag values return a disabled response.
- Disabled-by-default behavior is enforced in production and non-production environments.
- Disabled responses do not build preview payloads and return no prohibited actions.
- Enabled responses return a read-only preview envelope only.
- No apply mode.
- No repair execution.
- No DB writes.
- No mint queueing.
- No certificate/customer mutation.
- No customer-facing exposure.
- No prohibited actions in the response.
- No full `rollback_plan` is exposed.
- No full override `reason_detail` is exposed.
- No full justification `reason_detail` is exposed.
- No full `audit_context` is exposed.
- Route does not accept `approval_fixture_payload` from request/user input.
- Route does not accept `test_context` from request/user input.
- Route does not accept `validator_result` as request/user approval input.

## Rollback Instructions

1. Disable feature flag `CONTINUITY_KERNEL_READONLY_ADMIN_PREVIEW_ENABLED`.
2. Remove route PR if needed.
3. Verify no data was mutated.
4. Run architecture and contract tests.
