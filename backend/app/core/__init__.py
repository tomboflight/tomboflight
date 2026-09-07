"""Core Tomb of Light policy package.

The commercial catalog overlay is applied once when the core package loads so
all callers of package_catalog share the same published product truth.
"""

from importlib import import_module
import sys

try:
    import_module("app")
except ModuleNotFoundError as exc:
    if getattr(exc, "name", None) != "app":
        raise
    sys.modules.setdefault("app", import_module("backend.app"))

_package_catalog = import_module(".package_catalog", __name__)
_overlay = import_module(".commercial_catalog_overlay", __name__)
_overlay.apply_commercial_catalog_overlay(_package_catalog)

__all__: list[str] = []
