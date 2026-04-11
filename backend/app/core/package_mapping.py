from __future__ import annotations

from copy import deepcopy
from typing import Any

PACKAGE_MAP: dict[str, dict[str, Any]] = {
    "legacy_snapshot": {
        "slug": "legacy_snapshot",
        "display_name": "Legacy Snapshot",
        "entitlement_code": "legacy_snapshot",
        "lane": "portrait",
        "anchor_type": None,
        "mint_policy": {
            "product_includes_onchain_anchor": False,
            "auto_mint_enabled": False,
            "opt_in_only": False,
            "token_type": None,
            "included_anchor_count": 0,
            "requires_customer_public_safe_approval": False,
        },
        "maintenance_default": "monthly",
    },
    "legacy_portrait_intro": {
        "slug": "legacy_portrait_intro",
        "display_name": "Legacy Portrait Intro",
        "entitlement_code": "legacy_portrait_intro",
        "lane": "portrait",
        "anchor_type": None,
        "mint_policy": {
            "product_includes_onchain_anchor": False,
            "auto_mint_enabled": False,
            "opt_in_only": False,
            "token_type": None,
            "included_anchor_count": 0,
            "requires_customer_public_safe_approval": False,
        },
        "maintenance_default": "monthly",
    },
    "digital-legacy-portrait": {
        "slug": "digital-legacy-portrait",
        "display_name": "Digital Legacy Portrait",
        "entitlement_code": "digital_legacy_portrait",
        "lane": "portrait",
        "anchor_type": "portrait_anchor",
        "mint_policy": {
            "product_includes_onchain_anchor": True,
            "auto_mint_enabled": True,
            "opt_in_only": False,
            "token_type": "portrait_anchor",
            "included_anchor_count": 1,
            "requires_customer_public_safe_approval": True,
        },
        "maintenance_default": "monthly",
    },
    "household_foundation": {
        "slug": "household_foundation",
        "display_name": "Household Foundation",
        "entitlement_code": "household_foundation",
        "lane": "household",
        "anchor_type": "household_anchor",
        "mint_policy": {
            "product_includes_onchain_anchor": True,
            "auto_mint_enabled": True,
            "opt_in_only": False,
            "token_type": "household_anchor",
            "included_anchor_count": 1,
            "requires_customer_public_safe_approval": True,
        },
        "maintenance_default": "monthly",
    },
    "heirloom_legacy_tree": {
        "slug": "heirloom_legacy_tree",
        "display_name": "Heirloom Legacy Tree",
        "entitlement_code": "heirloom_legacy_tree",
        "lane": "household",
        "anchor_type": "household_anchor",
        "mint_policy": {
            "product_includes_onchain_anchor": True,
            "auto_mint_enabled": True,
            "opt_in_only": False,
            "token_type": "household_anchor",
            "included_anchor_count": 1,
            "requires_customer_public_safe_approval": True,
        },
        "maintenance_default": "monthly",
    },
    "legacy-plus": {
        "slug": "legacy-plus",
        "display_name": "Legacy Plus",
        "entitlement_code": "legacy_plus",
        "lane": "household",
        "anchor_type": "household_anchor",
        "mint_policy": {
            "product_includes_onchain_anchor": True,
            "auto_mint_enabled": True,
            "opt_in_only": False,
            "token_type": "household_anchor",
            "included_anchor_count": 1,
            "requires_customer_public_safe_approval": True,
        },
        "maintenance_default": "monthly",
    },
    "family_estate_concierge": {
        "slug": "family_estate_concierge",
        "display_name": "Family Estate Concierge",
        "entitlement_code": "family_estate_concierge",
        "lane": "network",
        "anchor_type": "branch_anchor",
        "mint_policy": {
            "product_includes_onchain_anchor": True,
            "auto_mint_enabled": True,
            "opt_in_only": False,
            "token_type": "branch_anchor",
            "included_anchor_count": 3,
            "requires_customer_public_safe_approval": True,
        },
        "maintenance_default": "monthly",
    },
    "command_structure_network": {
        "slug": "command_structure_network",
        "display_name": "Command Structure Network",
        "entitlement_code": "command_structure_network",
        "lane": "organization",
        "anchor_type": "organization_anchor",
        "mint_policy": {
            "product_includes_onchain_anchor": True,
            "auto_mint_enabled": False,
            "opt_in_only": True,
            "token_type": "organization_anchor",
            "included_anchor_count": 1,
            "requires_customer_public_safe_approval": True,
        },
        "maintenance_default": "monthly",
    },
}

PACKAGE_VALUE_ALIASES: dict[str, str] = {
    "legacy-snapshot": "legacy_snapshot",
    "legacy_snapshot": "legacy_snapshot",
    "legacy-portrait-intro": "legacy_portrait_intro",
    "legacy_portrait_intro": "legacy_portrait_intro",
    "digital-legacy-portrait": "digital-legacy-portrait",
    "digital_legacy_portrait": "digital-legacy-portrait",
    "starter-family-tree": "household_foundation",
    "starter_family_tree": "household_foundation",
    "household-foundation": "household_foundation",
    "household_foundation": "household_foundation",
    "heirloom-legacy-tree": "heirloom_legacy_tree",
    "heirloom_legacy_tree": "heirloom_legacy_tree",
    "legacy-plus": "legacy-plus",
    "legacy_plus": "legacy-plus",
    "family-estate-concierge": "family_estate_concierge",
    "family_estate_concierge": "family_estate_concierge",
    "command-structure-network": "command_structure_network",
    "command_structure_network": "command_structure_network",
}

_PACKAGE_BY_CODE: dict[str, dict[str, Any]] = {
    str(item.get("entitlement_code") or ""): item for item in PACKAGE_MAP.values()
}


def _normalize(value: Any) -> str:
    return str(value or "").strip().lower()


def normalize_package_slug(value: Any) -> str:
    normalized = _normalize(value)
    return PACKAGE_VALUE_ALIASES.get(normalized, normalized)


def normalize_package_code(value: Any) -> str:
    package = get_package_map_entry(value)
    if package:
        return str(package.get("entitlement_code") or "").strip()
    return _normalize(value)


def package_code_to_slug(value: Any) -> str:
    code = _normalize(value)
    package = _PACKAGE_BY_CODE.get(code)
    return str((package or {}).get("slug") or "")


def package_slug_to_code(value: Any) -> str:
    package = get_package_map_entry(value)
    return str((package or {}).get("entitlement_code") or "")


def get_package_map_entry(value: Any) -> dict[str, Any] | None:
    slug = normalize_package_slug(value)
    item = PACKAGE_MAP.get(slug)
    if item:
        return deepcopy(item)
    by_code = _PACKAGE_BY_CODE.get(_normalize(value))
    return deepcopy(by_code) if by_code else None


def resolve_package_identity(value: Any, *, package_name: Any = "") -> dict[str, Any]:
    item = get_package_map_entry(value)
    if not item:
        normalized_value = _normalize(value)
        normalized_name = str(package_name or "").strip()
        return {
            "known": False,
            "package_slug": normalized_value,
            "package_code": normalized_value,
            "display_name": normalized_name or normalized_value or "Unknown Package",
            "lane": "unknown",
            "anchor_type": None,
            "mint_policy": {},
            "maintenance_default": "monthly",
        }

    return {
        "known": True,
        "package_slug": item["slug"],
        "package_code": item["entitlement_code"],
        "display_name": str(package_name or "").strip() or item["display_name"],
        "lane": item["lane"],
        "anchor_type": item["anchor_type"],
        "mint_policy": deepcopy(item["mint_policy"]),
        "maintenance_default": item["maintenance_default"],
    }


def list_package_map() -> dict[str, dict[str, Any]]:
    return deepcopy(PACKAGE_MAP)
