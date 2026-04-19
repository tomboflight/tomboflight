"""Pytest bootstrap for local test execution.

Ensures tests run from repository root without extra env vars and
adds compatibility for Python versions that do not expose datetime.UTC.
"""

from __future__ import annotations

import datetime as _datetime
import sys
from pathlib import Path

# Make `backend/app` importable as top-level `app` when running:
#   pytest backend/tests/... 
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Python <3.11 compatibility for code that imports `from datetime import UTC`.
if not hasattr(_datetime, "UTC"):
    _datetime.UTC = _datetime.timezone.utc
