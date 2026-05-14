# Continuity Kernel Phase 5H: CI Enforcement and Test-Gate Protection

Phase 5H establishes CI-only enforcement for Continuity Kernel guardrails without adding runtime wiring, apply-mode behavior, or repair execution.

## CI purpose

- prevent duplicate source-of-truth drift
- protect architecture docs
- protect contract docs
- protect isolated validator behavior
- protect structured override behavior
- protect payload placement rules
- prevent unsafe repair/apply behavior from entering unnoticed

## CI commands

- python -m compileall backend/app backend/scripts
- python -m unittest discover -s backend/tests/architecture -p "test_*.py" -v
- python -m unittest discover -s backend/tests/contracts -p "test_*.py" -v

## CI must not require

- database connection
- live secrets
- FastAPI startup
- Render environment
- Stripe/Web3 connection
- customer data
- production data

## Blocking rules

CI must fail if:

- architecture docs are missing
- duplicate package/role/entitlement/manifest source-of-truth files appear
- repair scripts lack dry-run/apply controls
- contract docs are missing
- validator behavior fails closed incorrectly
- structured overrides are bypassed
- payload placement governance is broken

## Non-operational guardrail

- Phase 5H does not wire validator into runtime routes.
- Phase 5H does not create apply mode.
- Phase 5H does not create repair scripts.
- Phase 5H does not touch live data.
- Phase 5H only adds CI/test-gate protection.
