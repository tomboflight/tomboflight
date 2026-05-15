# Continuity Kernel Phase 6O Staging Flag Runbook

## 1. Purpose

- This is a staging-only feature flag enablement runbook.
- The runbook validates read-only admin preview behavior.
- Phase 6O includes no production enablement.
- Phase 6O includes no apply mode.
- Phase 6O includes no repair execution.
- Phase 6O includes no data mutation.

## 2. Feature flag

- CONTINUITY_KERNEL_READONLY_ADMIN_PREVIEW_ENABLED

## 3. Approval required before staging enablement

- owner/CEO approval
- technical reviewer approval
- confirmation Phase 6N criteria are met
- confirmation dependency-backed CI has zero runtime skips
- confirmation feature flag remains off in production

## 4. Staging enablement rules

- staging only
- time-boxed test window
- flag must be turned off after testing
- no production enablement
- no customer-facing exposure
- no frontend/admin UI button exposure unless separately approved
- no apply/schedule/execute/rollback actions
- no database writes
- no mint queueing
- no certificate/customer mutation

## 5. Manual staging QA checklist

- verify route disabled before enabling flag
- enable flag in staging only
- verify GET /admin/continuity-kernel/preview returns read-only envelope
- verify admin-only access
- verify non-admin is denied
- verify marketing_admin/CMO receives no repair execution actions
- verify no prohibited actions are returned
- verify no full rollback_plan is exposed
- verify no override reason_detail is exposed
- verify no justification reason_detail is exposed
- verify no audit_context is exposed
- verify no POST/PUT/PATCH/DELETE routes work
- verify logs show no DB writes
- verify no jobs are queued
- verify no mint queueing occurs
- verify no certificate/customer mutation occurs
- disable flag after test
- verify route returns disabled after flag is off

## 6. Monitoring checklist

- check backend logs
- check error rates
- check auth failures
- check route access attempts
- check no write operations occurred
- check no job queue activity occurred
- check no customer-facing traffic hit the route

## 7. Rollback

- disable feature flag
- redeploy/restart only if needed
- verify disabled response
- verify no data changed
- verify no jobs queued
- rerun architecture tests
- rerun contract tests
- rerun focused Phase 6I runtime route tests
- document test result

## 8. Exit criteria

- successful QA checklist
- flag disabled after test
- no mutation observed
- no prohibited actions observed
- no sensitive payload exposure observed
- owner sign-off recorded
- staging result documented

## 9. Non-operational guardrail

- Phase 6O does not enable the flag.
- Phase 6O does not change Render settings.
- Phase 6O does not change production settings.
- Phase 6O does not create apply mode.
- Phase 6O does not create repair scripts.
- Phase 6O does not touch live data.
