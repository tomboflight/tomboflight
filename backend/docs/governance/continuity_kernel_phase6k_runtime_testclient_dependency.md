# Continuity Kernel Phase 6K Runtime TestClient Dependency Enforcement

## 1. Purpose

- Ensure Phase 6I runtime route verification executes in CI with FastAPI/Starlette TestClient.
- Prevent runtime-only checks from being skipped when runtime test dependencies are installed.
- Keep verification scoped to read-only guardrails with no runtime feature expansion.

## 2. Why `httpx` is required

- `httpx` is required for Starlette/FastAPI TestClient runtime verification.
- This dependency is used only for runtime TestClient execution of the focused route test:
  - `python -m unittest backend.tests.contracts.test_continuity_kernel_phase6i_runtime_route_verification -v`
- `httpx` in this phase is not for live DB access.
- `httpx` in this phase is not for Stripe/Web3 calls.
- `httpx` in this phase is not for customer data operations.

## 3. Runtime environment boundaries

- No live DB is required.
- No live secrets are required.
- Runtime route tests should execute in CI when dependencies are installed.
- Runtime verification remains GET-only for `GET /admin/continuity-kernel/preview`.

## 4. Safety constraints

- No apply mode.
- No repair scripts.
- No DB writes.
- No POST/PUT/PATCH/DELETE route additions.
- No frontend changes.
- No production write behavior.
