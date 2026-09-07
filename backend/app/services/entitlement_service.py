from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any

from app.core.package_catalog import get_addon, get_package

_logger = logging.getLogger(__name__)


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def get_package_or_raise(package_code: str) -> dict[str, Any]:
    package = get_package(package_code)
    if not package:
        raise ValueError(f"Unknown package_code: {package_code}")
    return package


def get_addon_or_raise(addon_code: str) -> dict[str, Any]:
    addon = get_addon(addon_code)
    if not addon:
        raise ValueError(f"Unknown addon_code: {addon_code}")
    return addon


def _addon_effect_code(addon: dict[str, Any], fallback: str) -> str:
    return _normalize(addon.get("entitlement_code") or addon.get("addon_code") or fallback)


def _addon_is_compatible(package: dict[str, Any], addon: dict[str, Any], addon_code: str) -> bool:
    package_code = _normalize(package.get("package_code"))
    package_lane = _normalize(package.get("package_lane"))
    sku_code = _normalize(addon.get("addon_code") or addon_code)
    effect_code = _addon_effect_code(addon, sku_code)

    allowed_packages = {
        _normalize(value)
        for value in (addon.get("allowed_packages") or [])
        if _normalize(value)
    }
    if allowed_packages and package_code not in allowed_packages:
        return False

    allowed_lanes = {
        _normalize(value)
        for value in (addon.get("allowed_lanes") or [])
        if _normalize(value)
    }
    if allowed_lanes and package_lane not in allowed_lanes:
        return False

    if not bool(addon.get("requires_package_allowlist", True)):
        return True

    allowed_addons = {
        _normalize(value)
        for value in (package.get("allowed_addons") or [])
        if _normalize(value)
    }
    return bool(sku_code in allowed_addons or effect_code in allowed_addons)


def _apply_entitlement_effects(
    entitlements: dict[str, Any],
    effects: dict[str, Any],
) -> None:
    numeric_deltas: dict[str, str] = {
        "max_uploads_delta": "max_uploads",
        "max_storage_gb_delta": "max_storage_gb",
        "max_members_delta": "max_members",
        "max_zoom_layers_delta": "max_zoom_layers",
        "max_households_delta": "max_households",
        "max_family_branches_delta": "max_family_branches",
        "max_org_nodes_delta": "max_org_nodes",
        "extra_admin_seats_delta": "extra_admin_seats",
    }
    for effect_key, entitlement_key in numeric_deltas.items():
        delta = effects.get(effect_key)
        if delta is None:
            continue
        current = entitlements.get(entitlement_key, 0) or 0
        if entitlement_key == "max_storage_gb":
            entitlements[entitlement_key] = float(current) + float(delta)
        else:
            entitlements[entitlement_key] = int(current) + int(delta)

    for boolean_key in (
        "can_link_households",
        "can_link_org_units",
    ):
        if boolean_key in effects:
            entitlements[boolean_key] = bool(effects.get(boolean_key))


def resolve_project_entitlements(
    package_code: str,
    active_addon_codes: list[str] | None = None,
) -> dict[str, Any]:
    package = get_package_or_raise(package_code)
    entitlements = deepcopy(package)
    entitlements["active_addons"] = []
    processed_addons: set[str] = set()

    for raw_addon_code in active_addon_codes or []:
        addon = get_addon_or_raise(raw_addon_code)
        addon_code = _normalize(addon.get("addon_code") or raw_addon_code)
        if not addon_code or addon_code in processed_addons:
            continue
        processed_addons.add(addon_code)

        if not _addon_is_compatible(package, addon, addon_code):
            _logger.warning(
                "Skipping addon '%s' because it is not compatible with package '%s' in lane '%s'.",
                addon_code,
                package.get("package_code"),
                package.get("package_lane"),
            )
            continue

        entitlements["active_addons"].append(addon_code)
        effect_code = _addon_effect_code(addon, addon_code)
        effects = addon.get("entitlement_effects")
        if isinstance(effects, dict) and effects:
            _apply_entitlement_effects(entitlements, effects)
            continue

        # Backward-compatible effects for historical generic add-on codes.
        if effect_code == "extra_upload_pack":
            entitlements["max_uploads"] = int(entitlements.get("max_uploads", 0)) + 10
        elif effect_code == "extra_storage":
            entitlements["max_storage_gb"] = float(
                entitlements.get("max_storage_gb", 0)
            ) + 10
        elif effect_code == "extra_mapped_person":
            entitlements["max_members"] = int(entitlements.get("max_members", 0)) + 1
        elif effect_code == "extra_zoom_layer":
            entitlements["max_zoom_layers"] = int(
                entitlements.get("max_zoom_layers", 0)
            ) + 1
        elif effect_code == "extra_linked_household":
            entitlements["max_households"] = int(
                entitlements.get("max_households", 0)
            ) + 1
            entitlements["can_link_households"] = True
        elif effect_code == "extra_branch":
            entitlements["max_households"] = int(
                entitlements.get("max_households", 0)
            ) + 1
            entitlements["max_family_branches"] = int(
                entitlements.get("max_family_branches", 0)
            ) + 1
            entitlements["can_link_households"] = True
        elif effect_code == "extra_org_node":
            entitlements["max_org_nodes"] = int(
                entitlements.get("max_org_nodes", 0)
            ) + 1
        elif effect_code == "extra_org_level":
            entitlements["max_zoom_layers"] = int(
                entitlements.get("max_zoom_layers", 0)
            ) + 1
        elif effect_code == "extra_admin_seat":
            entitlements["extra_admin_seats"] = int(
                entitlements.get("extra_admin_seats", 0)
            ) + 1

    entitlements["resolved"] = True
    return entitlements


def can_purchase_addon(package_code: str, addon_code: str) -> bool:
    package = get_package_or_raise(package_code)
    addon = get_addon_or_raise(addon_code)
    return _addon_is_compatible(package, addon, addon_code)


def can_upgrade(from_package_code: str, to_package_code: str) -> bool:
    package = get_package_or_raise(from_package_code)
    target_package = get_package_or_raise(to_package_code)
    return target_package["package_code"] in package.get("upgrade_targets", [])


def compute_upgrade_quote(
    from_package_code: str,
    to_package_code: str,
) -> dict[str, Any]:
    from_package = get_package_or_raise(from_package_code)
    to_package = get_package_or_raise(to_package_code)

    if not can_upgrade(from_package_code, to_package_code):
        raise ValueError(
            f"Package '{from_package_code}' cannot upgrade to '{to_package_code}'"
        )

    credit_usd = float(from_package.get("base_price_usd", 0))
    target_price_usd = float(to_package.get("base_price_usd", 0))
    upgrade_price_usd = max(target_price_usd - credit_usd, 0)

    return {
        "from_package_code": from_package["package_code"],
        "to_package_code": to_package["package_code"],
        "credit_usd": credit_usd,
        "target_price_usd": target_price_usd,
        "upgrade_price_usd": upgrade_price_usd,
        "new_maintenance_monthly_usd": to_package.get("maintenance_monthly_usd"),
        "new_maintenance_annual_usd": to_package.get("maintenance_annual_usd"),
        "new_maintenance_lifetime_usd": to_package.get("maintenance_lifetime_usd"),
    }


def can_access_feature(package_code: str, feature_name: str) -> bool:
    package = get_package_or_raise(package_code)
    return bool(package.get(feature_name, False))
