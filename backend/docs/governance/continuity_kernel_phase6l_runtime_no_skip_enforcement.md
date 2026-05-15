# Continuity Kernel Phase 6L Runtime No-Skip Enforcement

## 1. Purpose

- Enforce that focused Phase 6I runtime route verification cannot silently pass in dependency-backed CI when runtime-only tests are skipped.
- Keep this phase scoped to verification/CI hardening only.
- Preserve read-only guardrails and avoid runtime feature expansion.

## 2. Why skipped runtime tests must fail in dependency-backed CI

- In dependency-backed CI, runtime dependencies are installed from `backend/requirements.txt`.
- In that environment, skipped runtime tests must fail the job to prevent false-green verification outcomes.
- Runtime no-skip enforcement is controlled by `CONTINUITY_KERNEL_RUNTIME_TEST_ENFORCE_NO_SKIPS`.
- CI must set `CONTINUITY_KERNEL_RUNTIME_TEST_ENFORCE_NO_SKIPS=1` for the dependency-backed runtime job.

## 3. Required commands

- Focused Phase 6I runtime route verification command:
  - `python -m unittest backend.tests.contracts.test_continuity_kernel_phase6i_runtime_route_verification -v`
- Phase 6L runtime no-skip enforcement command:
  - `python -m unittest backend.tests.contracts.test_continuity_kernel_phase6l_runtime_no_skip_enforcement -v`

## 4. Local/sandbox behavior without runtime dependencies

- If FastAPI/httpx are unavailable and `CONTINUITY_KERNEL_RUNTIME_TEST_ENFORCE_NO_SKIPS` is not set, local/sandbox skip is allowed with a clear reason.
- If `CONTINUITY_KERNEL_RUNTIME_TEST_ENFORCE_NO_SKIPS=1`, skipped Phase 6I runtime tests are treated as a Phase 6L failure.

## 5. Safety boundaries

- No live DB is required.
- No live secrets are required.
- No Stripe/Web3 calls are required.
- No customer data is required.
- No apply mode.
- No repair scripts.
- No DB writes.
- No frontend changes.
- Route remains GET-only (`GET /admin/continuity-kernel/preview`) with no POST/PUT/PATCH/DELETE additions.
