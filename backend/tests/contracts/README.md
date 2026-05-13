# Contracts Tests (Phase 3)

Static Phase 3 contract checks for Continuity Kernel boundaries.

Scope:
- Standard-library-only tests (`unittest`, `pathlib`, `re`).
- Filesystem and source-text verification only.
- No runtime imports from `backend/app` modules.

Run:
- `python -m unittest discover -s backend/tests/contracts -p "test_*.py" -v`
