# Continuity Kernel Phase 6G: Read-Only Route Design Contract

## 1. Purpose

- design future read-only route contract
- prevent accidental mutation
- keep Phase 6G design-only
- prepare for Phase 6H route implementation only if separately approved

## 2. Proposed future route

- canonical future route path: GET /admin/continuity-kernel/preview

## 3. Route type

- GET only
- admin-only
- read-only
- feature-flagged
- disabled by default
- no customer-facing exposure

## 4. Required auth and permission guard

- authenticated admin required
- officer role required
- route must fail closed for non-admin users
- route must fail closed for marketing_admin/CMO if repair execution preview actions would be shown
- route must never bypass existing auth/role checks

## 5. Required feature flag behavior

- if CONTINUITY_KERNEL_READONLY_ADMIN_PREVIEW_ENABLED is missing/off/invalid, route returns disabled response
- production default off
- no preview payload built when flag is off
- no prohibited actions returned when flag is off

## 6. Allowed response

- read-only preview envelope only
- no apply/schedule/execute/rollback actions
- no repair execution
- no DB writes
- no mint queueing
- no certificate/customer mutation
- no full rollback_plan
- no full override reason_detail
- no full justification reason_detail
- no full audit_context

## 7. Forbidden route behavior

- POST/PUT/PATCH/DELETE
- apply mode
- repair execution
- database writes
- job queueing
- mint queueing
- certificate mutation
- customer record mutation
- accepting validator_result as user approval input
- accepting approval_fixture_payload from request/user input
- accepting test_context from request/user input
- exposing customer-facing route
- exposing prohibited actions

## 8. Request input restrictions

- no approval_fixture_payload from request
- no test_context from request
- no user-provided validator_result
- no user-provided structured_override unless later separately approved
- no user-provided structured_justification unless later separately approved
- any future target selector must be admin-scoped and validated

## 9. Required route tests for future Phase 6H

- flag off returns disabled
- flag missing returns disabled
- flag invalid returns disabled
- non-admin denied
- marketing_admin denied or receives no actions
- response contains no prohibited actions
- no DB writes called
- no apply/schedule/execute/rollback route exists
- no POST/PUT/PATCH/DELETE route exists
- no fixture/test_context request path exists
- no customer-facing route exists

## 10. Non-operational guardrail

- Phase 6G does not implement route.
- Phase 6G does not wire runtime routes.
- Phase 6G does not create apply mode.
- Phase 6G does not create repair scripts.
- Phase 6G does not touch live data.
