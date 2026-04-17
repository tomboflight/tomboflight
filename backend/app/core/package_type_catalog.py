from __future__ import annotations

from copy import deepcopy
from typing import Any

PACKAGE_TYPE_CATALOG: dict[str, dict[str, Any]] = {
    "portrait": {
        "package_type": "portrait",
        "display_name": "Portrait Workspace",
        "service_feature_foundation": ["viewer_manifest", "portrait_uploads"],
    },
    "household": {
        "package_type": "household",
        "display_name": "Household Workspace",
        "service_feature_foundation": ["viewer_manifest", "family_graph", "household_intake"],
    },
    "network": {
        "package_type": "network",
        "display_name": "Network Workspace",
        "service_feature_foundation": ["viewer_manifest", "family_graph", "household_links"],
    },
    "organization": {
        "package_type": "organization",
        "display_name": "Organization Workspace",
        "service_feature_foundation": ["viewer_manifest", "command_graph", "org_intake"],
    },
}

PACKAGE_TYPE_ALIASES: dict[str, str] = {
    "portrait": "portrait",
    "legacy_portrait": "portrait",
    "household": "household",
    "family": "household",
    "network": "network",
    "organization": "organization",
    "org": "organization",
}



def normalize_package_type(value: Any, *, default: str = "") -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return default
    return PACKAGE_TYPE_ALIASES.get(normalized, normalized)



def get_package_type(package_type: Any) -> dict[str, Any] | None:
    normalized = normalize_package_type(package_type)
    value = PACKAGE_TYPE_CATALOG.get(normalized)
    return deepcopy(value) if value else None
