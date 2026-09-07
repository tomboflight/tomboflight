"""Core Tomb of Light policy package.

The commercial catalog overlay is applied once when the core package loads so
all callers of package_catalog share the same published product truth.
"""

from importlib import import_module

try:
    _package_catalog = import_module("app.core.package_catalog")
    _overlay = import_module("app.core.commercial_catalog_overlay")
except ModuleNotFoundError as exc:
    if exc.name != "app":
        raise
else:
    _overlay.apply_commercial_catalog_overlay(_package_catalog)

__all__: list[str] = []
