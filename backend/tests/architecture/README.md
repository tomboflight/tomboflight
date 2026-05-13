# Architecture Fitness Tests (Phase 2A)

These tests are static, documentation-and-filesystem architecture checks for the Tomb of Light Continuity Kernel.

Scope:
- Uses only Python standard library file/text inspection.
- Does not import backend runtime modules.
- Protects audited architecture boundaries without changing app behavior.

Run:
- `python -m unittest discover -s backend/tests/architecture -p "test_*.py" -v`
