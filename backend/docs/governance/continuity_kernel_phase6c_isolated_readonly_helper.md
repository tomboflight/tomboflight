# Continuity Kernel Phase 6C: Isolated Read-Only Preview Helper

## 1. Purpose

- isolated read-only helper for future admin preview
- combines flag check, staging dry-run payload assembly, validator, and admin preview shaping
- no route/service/admin UI wiring

## 2. Feature flag behavior

- disabled by default
- off/missing/invalid returns disabled response
- enabled only by explicit true-like value

## 3. Read-only behavior

- no apply mode
- no repair execution
- no DB writes
- no mint queueing
- no certificate/customer mutation
- no customer-facing exposure
- no prohibited actions returned

## 4. Non-operational guardrail

- phase 6c does not expose runtime route
- phase 6c does not wire helper into services
- phase 6c does not wire helper into admin actions
- phase 6c does not create repair scripts
- phase 6c does not touch live data
