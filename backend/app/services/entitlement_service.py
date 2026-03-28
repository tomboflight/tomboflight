from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.core.package_catalog import get_addon, get_package


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


def resolve_project_entitlements(
    package_code: str,
    active_addon_codes: list[str] | None = None,
) -> dict[str, Any]:
    package = get_package_or_raise(package_code)
    entitlements = deepcopy(package)
    entitlements["active_addons"] = []

    for raw_addon_code in active_addon_codes or []:
        addon = get_addon_or_raise(raw_addon_code)
        addon_code = str(addon.get("addon_code") or raw_addon_code).strip()

        if package["package_lane"] not in addon.get("allowed_lanes", []):
            raise ValueError(
                f"Addon '{addon_code}' is not allowed for lane '{package['package_lane']}'"
            )

        entitlements["active_addons"].append(addon_code)

        if addon_code == "extra_upload_pack":
            entitlements["max_uploads"] = int(entitlements.get("max_uploads", 0)) + 10
        elif addon_code == "extra_storage":
            entitlements["max_storage_gb"] = float(
                entitlements.get("max_storage_gb", 0)
            ) + 10
        elif addon_code == "extra_mapped_person":
            entitlements["max_members"] = int(entitlements.get("max_members", 0)) + 1
        elif addon_code == "extra_zoom_layer":
            entitlements["max_zoom_layers"] = int(
                entitlements.get("max_zoom_layers", 0)
            ) + 1
        elif addon_code == "extra_linked_household":
            entitlements["max_households"] = int(
                entitlements.get("max_households", 0)
            ) + 1
            entitlements["can_link_households"] = True
        elif addon_code == "extra_branch":
            entitlements["max_households"] = int(
                entitlements.get("max_households", 0)
            ) + 1
            entitlements["can_link_households"] = True
        elif addon_code == "extra_org_node":
            entitlements["max_org_nodes"] = int(
                entitlements.get("max_org_nodes", 0)
            ) + 1
        elif addon_code == "extra_org_level":
            entitlements["max_zoom_layers"] = int(
                entitlements.get("max_zoom_layers", 0)
            ) + 1
        elif addon_code == "extra_admin_seat":
            entitlements["extra_admin_seats"] = int(
                entitlements.get("extra_admin_seats", 0)
            ) + 1

    entitlements["resolved"] = True
    return entitlements


def can_purchase_addon(package_code: str, addon_code: str) -> bool:
    package = get_package_or_raise(package_code)
    addon = get_addon_or_raise(addon_code)
    return package["package_lane"] in addon.get("allowed_lanes", [])


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