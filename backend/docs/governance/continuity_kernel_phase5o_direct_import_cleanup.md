## Continuity Kernel Phase 5O: Direct Import Cleanup

### 1. Purpose

Phase 5O updates Continuity Kernel isolation governance to allow direct imports between isolated Continuity Kernel core modules and remove importlib indirection where it was only used to satisfy older tests.

- allow direct imports between isolated Continuity Kernel core modules
- remove importlib indirection where it was only used to satisfy older tests
- keep all runtime wiring prohibited
- keep all DB/service/route/script imports prohibited

### 2. Approved isolated core module imports

Approved isolated core modules:

- `backend.app.core.continuity_kernel_taxonomy`
- `backend.app.core.continuity_kernel_validator`
- `backend.app.core.continuity_kernel_dry_run_adapter`
- `backend.app.core.continuity_kernel_admin_preview`

Import policy:

- `continuity_kernel_taxonomy` may be imported by validator, adapter, and preview.
- `continuity_kernel_validator` may be imported by adapter/preview tests if needed, but runtime wiring remains prohibited.
- `continuity_kernel_dry_run_adapter` remains isolated and must not be imported into routes/services/scripts.
- `continuity_kernel_admin_preview` remains isolated and must not be imported into routes/services/scripts.

### 3. Forbidden imports remain

The following imports remain forbidden in isolated Continuity Kernel modules:

- FastAPI
- pymongo
- motor
- bson
- pydantic
- stripe
- web3
- `backend.app.routes`
- `backend.app.services`
- `backend.scripts`
- database/session modules

### 4. Isolation rule update

- A Continuity Kernel core module may directly import another approved Continuity Kernel core module.
- A Continuity Kernel core module must not import runtime route/service/script/database modules.
- Routes/services/scripts/main must not import Continuity Kernel modules yet.

### 5. Non-operational guardrail

- Phase 5O does not wire modules into runtime routes.
- Phase 5O does not create apply mode.
- Phase 5O does not create repair scripts.
- Phase 5O does not touch live data.
- Phase 5O only cleans up isolated imports and tests.
