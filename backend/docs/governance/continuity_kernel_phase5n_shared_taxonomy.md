## Continuity Kernel Phase 5N: Shared Taxonomy Module

### 1. Purpose

Phase 5N centralizes Continuity Kernel role/category taxonomy so validator and preview use the same canonical constants and mappings.

- prevent validator/preview role-category drift
- keep taxonomy isolated
- keep fail-closed role/category governance centralized

### 2. Shared taxonomy ownership

- `backend/app/core/continuity_kernel_taxonomy.py` is the isolated source of truth for Continuity Kernel role/category taxonomy.
- Validator and preview modules must import role/category constants from taxonomy.
- Routes/services/scripts/admin UI must not import it yet in Phase 5N.

### 3. Non-operational guardrail

- Phase 5N does not wire taxonomy into runtime routes.
- Phase 5N does not create apply mode.
- Phase 5N does not create repair scripts.
- Phase 5N does not touch live data.
- Phase 5N only centralizes isolated taxonomy and tests.
