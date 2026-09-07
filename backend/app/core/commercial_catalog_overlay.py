from __future__ import annotations

from copy import deepcopy
from types import ModuleType
from typing import Any


# Commercial SKU truth mirrors the currently published Tomb of Light checkout
# catalog. Stripe links remain in config.js; this server-side map supplies the
# exact product name/amount used to verify a paid Checkout Session and the
# canonical entitlement effect (when one exists).
COMMERCIAL_ADDON_SKUS: dict[str, dict[str, Any]] = {
    "extra_upload_pack": {
        "addon_code": "extra_upload_pack",
        "display_name": "Extra Upload Pack",
        "price_usd": 49,
        "billing_type": "one_time",
        "allowed_lanes": ["portrait", "household", "network", "organization"],
        "entitlement_code": "extra_upload_pack",
        "entitlement_effects": {"max_uploads_delta": 10},
        "status": "active",
    },
    "extra_storage_10gb_monthly": {
        "addon_code": "extra_storage_10gb_monthly",
        "display_name": "Extra Storage +10GB Monthly",
        "price_usd": 15,
        "billing_type": "monthly",
        "allowed_lanes": ["portrait", "household", "network", "organization"],
        "entitlement_code": "extra_storage",
        "entitlement_effects": {"max_storage_gb_delta": 10},
        "status": "active",
    },
    "extra_storage_10gb_yearly": {
        "addon_code": "extra_storage_10gb_yearly",
        "display_name": "Extra Storage +10GB Annual",
        "price_usd": 150,
        "billing_type": "yearly",
        "allowed_lanes": ["portrait", "household", "network", "organization"],
        "entitlement_code": "extra_storage",
        "entitlement_effects": {"max_storage_gb_delta": 10},
        "status": "active",
    },
    "vault_expansion_25gb_monthly": {
        "addon_code": "vault_expansion_25gb_monthly",
        "display_name": "Vault Expansion +25GB Monthly",
        "price_usd": 29,
        "billing_type": "monthly",
        "allowed_lanes": ["portrait", "household", "network"],
        "entitlement_code": "extra_storage",
        "entitlement_effects": {"max_storage_gb_delta": 25},
        "status": "active",
    },
    "vault_expansion_25gb_yearly": {
        "addon_code": "vault_expansion_25gb_yearly",
        "display_name": "Vault Expansion +25GB Annual",
        "price_usd": 290,
        "billing_type": "yearly",
        "allowed_lanes": ["portrait", "household", "network"],
        "entitlement_code": "extra_storage",
        "entitlement_effects": {"max_storage_gb_delta": 25},
        "status": "active",
    },
    "vault_expansion_50gb_monthly": {
        "addon_code": "vault_expansion_50gb_monthly",
        "display_name": "Vault Expansion +50GB Monthly",
        "price_usd": 59,
        "billing_type": "monthly",
        "allowed_lanes": ["portrait", "household", "network"],
        "entitlement_code": "extra_storage",
        "entitlement_effects": {"max_storage_gb_delta": 50},
        "status": "active",
    },
    "vault_expansion_50gb_yearly": {
        "addon_code": "vault_expansion_50gb_yearly",
        "display_name": "Vault Expansion +50GB Annual",
        "price_usd": 590,
        "billing_type": "yearly",
        "allowed_lanes": ["portrait", "household", "network"],
        "entitlement_code": "extra_storage",
        "entitlement_effects": {"max_storage_gb_delta": 50},
        "status": "active",
    },
    "private_vault_export": {
        "addon_code": "private_vault_export",
        "display_name": "Private Vault Export",
        "price_usd": 199,
        "billing_type": "one_time",
        "allowed_lanes": ["portrait", "household", "network"],
        "requires_package_allowlist": False,
        "fulfillment_type": "manual_service",
        "status": "active",
    },
    "portrait_polish": {
        "addon_code": "portrait_polish",
        "display_name": "Portrait Polish",
        "price_usd": 99,
        "billing_type": "one_time",
        "allowed_lanes": ["portrait"],
        "entitlement_code": "portrait_polish",
        "status": "active",
    },
    "tribute_narration": {
        "addon_code": "tribute_narration",
        "display_name": "Tribute Narration",
        "price_usd": 149,
        "billing_type": "one_time",
        "allowed_lanes": ["portrait"],
        "entitlement_code": "tribute_narration",
        "status": "active",
    },
    "additional_narration_minute": {
        "addon_code": "additional_narration_minute",
        "display_name": "Additional Narration Minute",
        "price_usd": 200,
        "billing_type": "one_time",
        "allowed_lanes": ["household", "network"],
        "entitlement_code": "additional_narration_minute",
        "status": "active",
    },
    "extra_mapped_person": {
        "addon_code": "extra_mapped_person",
        "display_name": "Extra Mapped Person",
        "price_usd": 49,
        "billing_type": "one_time",
        "allowed_lanes": ["household", "network"],
        "entitlement_code": "extra_mapped_person",
        "entitlement_effects": {"max_members_delta": 1},
        "status": "active",
    },
    "extra_zoom_layer": {
        "addon_code": "extra_zoom_layer",
        "display_name": "Extra Zoom Layer",
        "price_usd": 199,
        "billing_type": "one_time",
        "allowed_lanes": ["household", "network"],
        "entitlement_code": "extra_zoom_layer",
        "entitlement_effects": {"max_zoom_layers_delta": 1},
        "status": "active",
    },
    "extra_linked_household": {
        "addon_code": "extra_linked_household",
        "display_name": "Extra Linked Household",
        "price_usd": 1250,
        "billing_type": "one_time",
        "allowed_lanes": ["network"],
        "allowed_packages": ["family_estate_concierge"],
        "entitlement_code": "extra_linked_household",
        "entitlement_effects": {
            "max_households_delta": 1,
            "can_link_households": True,
        },
        "status": "active",
    },
    "extra_branch": {
        "addon_code": "extra_branch",
        "display_name": "Extra Branch",
        "price_usd": 1500,
        "billing_type": "one_time",
        "allowed_lanes": ["network"],
        "allowed_packages": ["family_estate_concierge"],
        "entitlement_code": "extra_branch",
        "entitlement_effects": {
            "max_households_delta": 1,
            "max_family_branches_delta": 1,
            "can_link_households": True,
        },
        "status": "active",
    },
    "extra_org_node": {
        "addon_code": "extra_org_node",
        "display_name": "Extra Organization Node",
        "price_usd": 99,
        "billing_type": "one_time",
        "allowed_lanes": ["organization"],
        "allowed_packages": ["command_structure_network"],
        "entitlement_code": "extra_org_node",
        "entitlement_effects": {"max_org_nodes_delta": 1},
        "status": "active",
    },
    "extra_org_level": {
        "addon_code": "extra_org_level",
        "display_name": "Extra Organization Level",
        "price_usd": 299,
        "billing_type": "one_time",
        "allowed_lanes": ["organization"],
        "allowed_packages": ["command_structure_network"],
        "entitlement_code": "extra_org_level",
        "entitlement_effects": {"max_zoom_layers_delta": 1},
        "status": "active",
    },
    "extra_admin_seat_monthly": {
        "addon_code": "extra_admin_seat_monthly",
        "display_name": "Extra Admin Seat Monthly",
        "price_usd": 19,
        "billing_type": "monthly",
        "allowed_lanes": ["organization"],
        "allowed_packages": ["command_structure_network"],
        "entitlement_code": "extra_admin_seat",
        "entitlement_effects": {"extra_admin_seats_delta": 1},
        "status": "active",
    },
    "extra_admin_seat_yearly": {
        "addon_code": "extra_admin_seat_yearly",
        "display_name": "Extra Admin Seat Annual",
        "price_usd": 190,
        "billing_type": "yearly",
        "allowed_lanes": ["organization"],
        "allowed_packages": ["command_structure_network"],
        "entitlement_code": "extra_admin_seat",
        "entitlement_effects": {"extra_admin_seats_delta": 1},
        "status": "active",
    },
    "command_report_addon": {
        "addon_code": "command_report_addon",
        "display_name": "Command Report",
        "price_usd": 299,
        "billing_type": "one_time",
        "allowed_lanes": ["organization"],
        "allowed_packages": ["command_structure_network"],
        "entitlement_code": "command_report_addon",
        "fulfillment_type": "manual_service",
        "status": "active",
    },
    "emergency_retrieval_support": {
        "addon_code": "emergency_retrieval_support",
        "display_name": "Emergency Retrieval Support",
        "price_usd": 249,
        "billing_type": "one_time",
        "allowed_lanes": ["portrait", "household", "network", "organization"],
        "requires_package_allowlist": False,
        "fulfillment_type": "manual_service",
        "status": "active",
    },
    "family_correction_cycle": {
        "addon_code": "family_correction_cycle",
        "display_name": "Family Correction Cycle",
        "price_usd": 149,
        "billing_type": "one_time",
        "allowed_lanes": ["portrait", "household", "network"],
        "requires_package_allowlist": False,
        "fulfillment_type": "manual_service",
        "status": "active",
    },
    "organization_correction_cycle": {
        "addon_code": "organization_correction_cycle",
        "display_name": "Organization Correction Cycle",
        "price_usd": 249,
        "billing_type": "one_time",
        "allowed_lanes": ["organization"],
        "requires_package_allowlist": False,
        "fulfillment_type": "manual_service",
        "status": "active",
    },
    "document_record_review_pack": {
        "addon_code": "document_record_review_pack",
        "display_name": "Document/Record Review Pack",
        "price_usd": 299,
        "billing_type": "one_time",
        "allowed_lanes": ["portrait", "household", "network", "organization"],
        "requires_package_allowlist": False,
        "fulfillment_type": "manual_service",
        "status": "active",
    },
    "on_site_photo_scanning": {
        "addon_code": "on_site_photo_scanning",
        "display_name": "On-Site Photo Scanning",
        "price_usd": 599,
        "billing_type": "one_time",
        "allowed_lanes": ["household", "network"],
        "entitlement_code": "on_site_photo_scanning",
        "fulfillment_type": "manual_service",
        "status": "active",
    },
    "white_glove_archive_support": {
        "addon_code": "white_glove_archive_support",
        "display_name": "White-Glove Archive Support",
        "price_usd": 1999,
        "billing_type": "one_time",
        "allowed_lanes": ["network"],
        "allowed_packages": ["family_estate_concierge"],
        "entitlement_code": "white_glove_archive_support",
        "fulfillment_type": "manual_service",
        "status": "active",
    },
    "rush_delivery_snapshot_portrait_intro": {
        "addon_code": "rush_delivery_snapshot_portrait_intro",
        "display_name": "Rush Delivery Snapshot / Portrait Intro",
        "price_usd": 99,
        "billing_type": "one_time",
        "allowed_lanes": ["portrait"],
        "allowed_packages": ["legacy_snapshot", "legacy_portrait_intro"],
        "entitlement_code": "rush_delivery",
        "fulfillment_type": "manual_service",
        "status": "active",
    },
    "rush_delivery_digital_legacy_portrait": {
        "addon_code": "rush_delivery_digital_legacy_portrait",
        "display_name": "Rush Delivery Digital Legacy Portrait",
        "price_usd": 199,
        "billing_type": "one_time",
        "allowed_lanes": ["portrait"],
        "allowed_packages": ["digital_legacy_portrait"],
        "entitlement_code": "rush_delivery",
        "fulfillment_type": "manual_service",
        "status": "active",
    },
    "rush_delivery_household_foundation": {
        "addon_code": "rush_delivery_household_foundation",
        "display_name": "Rush Delivery Household Foundation",
        "price_usd": 399,
        "billing_type": "one_time",
        "allowed_lanes": ["household"],
        "allowed_packages": ["household_foundation"],
        "entitlement_code": "rush_delivery",
        "fulfillment_type": "manual_service",
        "status": "active",
    },
    "rush_delivery_heirloom_legacy_tree": {
        "addon_code": "rush_delivery_heirloom_legacy_tree",
        "display_name": "Rush Delivery Heirloom Legacy Tree",
        "price_usd": 750,
        "billing_type": "one_time",
        "allowed_lanes": ["household"],
        "allowed_packages": ["heirloom_legacy_tree"],
        "entitlement_code": "rush_delivery",
        "fulfillment_type": "manual_service",
        "status": "active",
    },
    "rush_delivery_legacy_plus": {
        "addon_code": "rush_delivery_legacy_plus",
        "display_name": "Rush Delivery Legacy Plus",
        "price_usd": 1500,
        "billing_type": "one_time",
        "allowed_lanes": ["household"],
        "allowed_packages": ["legacy_plus"],
        "entitlement_code": "rush_delivery",
        "fulfillment_type": "manual_service",
        "status": "active",
    },
    "rush_delivery_estate_command_minimum": {
        "addon_code": "rush_delivery_estate_command_minimum",
        "display_name": "Rush Delivery Estate / Command Minimum",
        "price_usd": 2000,
        "billing_type": "one_time",
        "allowed_lanes": ["network", "organization"],
        "allowed_packages": ["family_estate_concierge", "command_structure_network"],
        "entitlement_code": "rush_delivery",
        "fulfillment_type": "manual_service",
        "status": "active",
    },
}


PACKAGE_ALLOWED_ADDON_ADDITIONS: dict[str, tuple[str, ...]] = {
    "family_estate_concierge": ("extra_linked_household", "extra_branch"),
    "command_structure_network": ("extra_org_node",),
}


def _alias_forms(code: str) -> set[str]:
    return {code, code.replace("_", "-"), code.replace("_", " ")}


def apply_commercial_catalog_overlay(package_catalog: ModuleType) -> None:
    """Apply published commercial SKU truth without changing checkout URLs.

    The overlay deliberately mutates the existing catalog dictionaries in
    place so every already-imported get_package/get_addon function observes the
    same corrected data. It is idempotent and does not touch customer records.
    """

    for sku, definition in COMMERCIAL_ADDON_SKUS.items():
        package_catalog.ADDON_CATALOG[sku] = deepcopy(definition)
        for alias in _alias_forms(sku):
            package_catalog.ADDON_CODE_ALIASES[alias] = sku

    for package_code, additions in PACKAGE_ALLOWED_ADDON_ADDITIONS.items():
        package = package_catalog.PACKAGE_CATALOG.get(package_code)
        if not isinstance(package, dict):
            continue
        package["allowed_addons"] = list(
            dict.fromkeys([*(package.get("allowed_addons") or []), *additions])
        )
