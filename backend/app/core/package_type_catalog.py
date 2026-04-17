from __future__ import annotations

from app.core.package_catalog import (
    get_addon,
    get_addon_catalog,
    get_package,
    get_package_catalog,
)

PROJECT_LANES = frozenset({"portrait", "household", "network", "organization"})
DEFAULT_LANE = "portrait"


def is_valid_lane(lane: str) -> bool:
    return str(lane or "").strip().lower() in PROJECT_LANES


__all__ = [
    "DEFAULT_LANE",
    "PROJECT_LANES",
    "get_addon",
    "get_addon_catalog",
    "get_package",
    "get_package_catalog",
    "is_valid_lane",
]
