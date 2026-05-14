## Continuity Kernel Phase 6B: Isolated Feature Flag Module

### 1. Purpose

- isolated feature-flag helper for future read-only admin preview
- fail-closed default
- not wired into runtime yet

### 2. Flag

- CONTINUITY_KERNEL_READONLY_ADMIN_PREVIEW_ENABLED

### 3. Behavior

- missing = false/off
- invalid = false/off
- production default = false/off
- only explicit true-like values enable

### 4. Non-operational guardrail

- phase 6b does not wire the flag into routes
- phase 6b does not wire the flag into services
- phase 6b does not create apply mode
- phase 6b does not create repair scripts
- phase 6b does not touch live data
