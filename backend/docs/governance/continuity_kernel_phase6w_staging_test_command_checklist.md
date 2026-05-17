# Continuity Kernel Phase 6W Staging Test Command Checklist

## 1. Purpose

- This is an operator-facing staging manual test command checklist.
- This is used only after Phase 6S go decision and Phase 6V preflight evidence.
- This is staging only.
- There is no production enablement.
- There is no apply mode.
- There is no repair execution.
- There is no data mutation.
- This checklist is staging-only and must not create production enablement, apply mode behavior, repair execution, or data mutation.

## 2. Preconditions

- Phase 6N readiness complete:
- Phase 6O runbook reviewed:
- Phase 6P approval/evidence complete:
- Phase 6Q execution record ready:
- Phase 6R packet index complete:
- Phase 6S go decision complete:
- Phase 6T readiness lock complete:
- Phase 6U manual test packet ready:
- Phase 6V preflight evidence refreshed:
- production flag confirmed off:
- owner/CEO approval recorded:
- technical reviewer approval recorded:
- rollback owner assigned:
- QA owner assigned:
- monitoring owner assigned:

## 3. Environment restrictions

- staging only
- production flag must remain off
- no production setting change
- no customer-facing exposure
- no frontend/admin button exposure
- no POST/PUT/PATCH/DELETE route testing except to confirm unavailable
- no apply/schedule/execute/rollback action

## 4. Required command/evidence checklist

- record staging base URL
- record authenticated admin test account
- record non-admin test account
- record marketing_admin/CMO test account or equivalent role simulation
- capture flag-off GET /admin/continuity-kernel/preview response
- enable flag in staging only by approved manual process
- capture flag-on GET /admin/continuity-kernel/preview response
- verify response enabled true
- verify read-only envelope only
- verify no prohibited actions
- verify no full rollback_plan
- verify no override reason_detail
- verify no justification reason_detail
- verify no audit_context
- verify non-admin denied
- verify marketing_admin/CMO receives no repair execution actions
- verify POST unavailable
- verify PUT unavailable
- verify PATCH unavailable
- verify DELETE unavailable
- verify no customer-facing route exists
- verify backend logs show no DB writes
- verify no jobs queued
- verify no mint queueing
- verify no certificate/customer mutation
- disable flag after test
- capture flag-off response after rollback
- rerun architecture tests
- rerun contract tests
- rerun focused Phase 6I runtime route test
- rerun Phase 6L no-skip enforcement

## 5. Prohibited actions that must never appear

- approve_apply
- schedule_apply
- execute_apply
- rollback_apply
- mutate_entitlement
- mutate_workspace_member
- mutate_certificate
- queue_mint
- delete_customer_record
- bypass_validator
- bypass_audit

## 6. Stop conditions

- production flag changes
- customer-facing route is exposed
- POST/PUT/PATCH/DELETE works
- prohibited action appears
- sensitive payload appears
- DB write observed
- job queued
- mint queueing observed
- certificate/customer mutation observed
- non-admin gains access
- rollback/flag-off response fails

## 7. Evidence fields

- command_run
- expected_result
- actual_result
- screenshot_or_log_reference
- pass_fail
- notes
- reviewer_initials

## 8. Non-operational guardrail

- Phase 6W does not enable the flag.
- Phase 6W does not change Render settings.
- Phase 6W does not change production settings.
- Phase 6W does not create apply mode.
- Phase 6W does not create repair scripts.
- Phase 6W does not create apply mode or repair scripts.
- Phase 6W does not touch live data.
