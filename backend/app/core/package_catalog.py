from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.core.package_type_catalog import normalize_package_type


PACKAGE_CODE_ALIASES: dict[str, str] = {
    "legacy-snapshot": "legacy_snapshot",
    "legacy_snapshot": "legacy_snapshot",
    "legacy snapshot": "legacy_snapshot",
    "legacy-portrait-intro": "legacy_portrait_intro",
    "legacy_portrait_intro": "legacy_portrait_intro",
    "legacy portrait intro": "legacy_portrait_intro",
    "digital-legacy-portrait": "digital_legacy_portrait",
    "digital_legacy_portrait": "digital_legacy_portrait",
    "digital legacy portrait": "digital_legacy_portrait",
    "starter-family-tree": "household_foundation",
    "starter_family_tree": "household_foundation",
    "starter family tree": "household_foundation",
    "household-foundation": "household_foundation",
    "household_foundation": "household_foundation",
    "household foundation": "household_foundation",
    "heirloom-legacy-tree": "heirloom_legacy_tree",
    "heirloom_legacy_tree": "heirloom_legacy_tree",
    "heirloom legacy tree": "heirloom_legacy_tree",
    "legacy-plus": "legacy_plus",
    "legacy_plus": "legacy_plus",
    "legacy plus": "legacy_plus",
    "family-estate-concierge": "family_estate_concierge",
    "family_estate_concierge": "family_estate_concierge",
    "family estate concierge": "family_estate_concierge",
    "command-structure-network": "command_structure_network",
    "command_structure_network": "command_structure_network",
    "command structure network": "command_structure_network",
}

ADDON_CODE_ALIASES: dict[str, str] = {
    "extra-upload-pack": "extra_upload_pack",
    "extra_upload_pack": "extra_upload_pack",
    "extra-storage": "extra_storage",
    "extra_storage": "extra_storage",
    "portrait-polish": "portrait_polish",
    "portrait_polish": "portrait_polish",
    "tribute-narration": "tribute_narration",
    "tribute_narration": "tribute_narration",
    "rush-delivery": "rush_delivery",
    "rush_delivery": "rush_delivery",
    "extra-mapped-person": "extra_mapped_person",
    "extra_mapped_person": "extra_mapped_person",
    "extra-zoom-layer": "extra_zoom_layer",
    "extra_zoom_layer": "extra_zoom_layer",
    "additional-narration-minute": "additional_narration_minute",
    "additional_narration_minute": "additional_narration_minute",
    "on-site-photo-scanning": "on_site_photo_scanning",
    "on_site_photo_scanning": "on_site_photo_scanning",
    "extra-linked-household": "extra_linked_household",
    "extra_linked_household": "extra_linked_household",
    "extra-branch": "extra_branch",
    "extra_branch": "extra_branch",
    "white-glove-archive-support": "white_glove_archive_support",
    "white_glove_archive_support": "white_glove_archive_support",
    "extra-org-node": "extra_org_node",
    "extra_org_node": "extra_org_node",
    "extra-org-level": "extra_org_level",
    "extra_org_level": "extra_org_level",
    "extra-admin-seat": "extra_admin_seat",
    "extra_admin_seat": "extra_admin_seat",
    "command-report-addon": "command_report_addon",
    "command_report_addon": "command_report_addon",
}

PROJECT_LANES = frozenset({"portrait", "household", "network", "organization"})
COMMAND_STRUCTURE_ORG_NODE_LIMIT = 15

ALLOWED_VISIBILITY_SCOPES = [
    "private_to_owner",
    "private_to_owner_and_co_owner",
    "household_private",
    "branch_shared",
    "linked_family_shared",
    "public_memorial",
    "minor_protected",
]

BASE_ALLOWED_ASSET_TYPES = [
    "portrait_photo",
    "group_photo",
    "document",
    "certificate",
    "verification_evidence",
]

EXTENDED_ALLOWED_ASSET_TYPES = BASE_ALLOWED_ASSET_TYPES + [
    "private_voice_message",
    "private_video_message",
    "narration_audio",
    "memorial_media",
]

# Private Household Vault package rules:
# - Legacy Snapshot and Legacy Portrait Intro stay personal-only.
# - Digital Legacy Portrait and Household Foundation unlock the household vault.
# - Heirloom Legacy Tree, Legacy Plus, and Family Estate Concierge add future
#   messages plus scheduled reveal support.
# - Command Structure Network stays on organization records vault access only.
VAULT_ENTITLEMENT_BY_PACKAGE: dict[str, dict[str, Any]] = {
    "legacy_snapshot": {
        "can_use_personal_vault": True,
        "can_use_household_vault": False,
        "can_use_future_message_vault": False,
        "can_use_linked_household_vault": False,
        "can_use_organization_records_vault": False,
        "can_use_scheduled_reveal": False,
        "allowed_asset_types": BASE_ALLOWED_ASSET_TYPES,
    },
    "legacy_portrait_intro": {
        "can_use_personal_vault": True,
        "can_use_household_vault": False,
        "can_use_future_message_vault": False,
        "can_use_linked_household_vault": False,
        "can_use_organization_records_vault": False,
        "can_use_scheduled_reveal": False,
        "allowed_asset_types": BASE_ALLOWED_ASSET_TYPES,
    },
    "digital_legacy_portrait": {
        "can_use_personal_vault": True,
        "can_use_household_vault": True,
        "can_use_future_message_vault": False,
        "can_use_linked_household_vault": False,
        "can_use_organization_records_vault": False,
        "can_use_scheduled_reveal": False,
        "allowed_asset_types": EXTENDED_ALLOWED_ASSET_TYPES,
    },
    "household_foundation": {
        "can_use_personal_vault": False,
        "can_use_household_vault": True,
        "can_use_future_message_vault": False,
        "can_use_linked_household_vault": False,
        "can_use_organization_records_vault": False,
        "can_use_scheduled_reveal": False,
        "allowed_asset_types": EXTENDED_ALLOWED_ASSET_TYPES,
    },
    "heirloom_legacy_tree": {
        "can_use_personal_vault": False,
        "can_use_household_vault": True,
        "can_use_future_message_vault": True,
        "can_use_linked_household_vault": False,
        "can_use_organization_records_vault": False,
        "can_use_scheduled_reveal": True,
        "allowed_asset_types": EXTENDED_ALLOWED_ASSET_TYPES,
    },
    "legacy_plus": {
        "can_use_personal_vault": False,
        "can_use_household_vault": True,
        "can_use_future_message_vault": True,
        "can_use_linked_household_vault": False,
        "can_use_organization_records_vault": False,
        "can_use_scheduled_reveal": True,
        "allowed_asset_types": EXTENDED_ALLOWED_ASSET_TYPES,
    },
    "family_estate_concierge": {
        "can_use_personal_vault": False,
        "can_use_household_vault": True,
        "can_use_future_message_vault": True,
        "can_use_linked_household_vault": True,
        "can_use_organization_records_vault": False,
        "can_use_scheduled_reveal": True,
        "allowed_asset_types": EXTENDED_ALLOWED_ASSET_TYPES,
    },
    "command_structure_network": {
        "can_use_personal_vault": False,
        "can_use_household_vault": False,
        "can_use_future_message_vault": False,
        "can_use_linked_household_vault": False,
        "can_use_organization_records_vault": True,
        "can_use_scheduled_reveal": False,
        "allowed_asset_types": ["document", "certificate", "verification_evidence", "private_voice_message"],
    },
}

PACKAGE_CATALOG: dict[str, dict[str, Any]] = {
    "legacy_snapshot": {
        "package_code": "legacy_snapshot",
        "display_name": "Legacy Snapshot",
        "package_lane": "portrait",
        "base_price_usd": 99,
        "maintenance_monthly_usd": 19,
        "maintenance_annual_usd": 190,
        "maintenance_lifetime_usd": 0,
        "maintenance_starts_on_delivery": False,
        "max_households": 0,
        "max_members": 1,
        "max_org_nodes": 0,
        "max_uploads": 3,
        "max_zoom_layers": 0,
        "max_storage_gb": 0.25,
        "can_build_household": False,
        "can_build_family_tree": True,
        "can_build_org_chart": False,
        "can_link_households": False,
        "can_link_org_units": False,
        "can_upload_portraits": True,
        "can_upload_verification_docs": True,
        "can_use_viewer": False,
        "can_use_secure_share_viewer": True,
        "can_use_narration": False,
        "can_use_lineage_certificate": True,
        "can_open_family_intake": True,
        "can_open_org_intake": False,
        "can_use_link_keys": False,
        "can_manage_link_keys": False,
        "protected_workspace": True,
        "guided_intake": True,
        "allowed_addons": [
            "extra_upload_pack",
            "extra_storage",
            "portrait_polish",
            "rush_delivery",
            "tribute_narration",
        ],
        "upgrade_targets": [
            "legacy_portrait_intro",
            "digital_legacy_portrait",
            "household_foundation",
            "heirloom_legacy_tree",
            "legacy_plus",
            "family_estate_concierge",
        ],
        "status": "active",
    },
    "legacy_portrait_intro": {
        "package_code": "legacy_portrait_intro",
        "display_name": "Legacy Portrait Intro",
        "package_lane": "portrait",
        "base_price_usd": 199,
        "maintenance_monthly_usd": 29,
        "maintenance_annual_usd": 290,
        "maintenance_lifetime_usd": 0,
        "maintenance_starts_on_delivery": False,
        "max_households": 0,
        "max_members": 1,
        "max_org_nodes": 0,
        "max_uploads": 5,
        "max_zoom_layers": 0,
        "max_storage_gb": 0.5,
        "can_build_household": False,
        "can_build_family_tree": True,
        "can_build_org_chart": False,
        "can_link_households": False,
        "can_link_org_units": False,
        "can_upload_portraits": True,
        "can_upload_verification_docs": True,
        "can_use_viewer": False,
        "can_use_secure_share_viewer": True,
        "can_use_narration": False,
        "can_use_lineage_certificate": True,
        "can_open_family_intake": True,
        "can_open_org_intake": False,
        "can_use_link_keys": False,
        "can_manage_link_keys": False,
        "protected_workspace": True,
        "guided_intake": True,
        "allowed_addons": [
            "extra_upload_pack",
            "extra_storage",
            "portrait_polish",
            "rush_delivery",
            "tribute_narration",
        ],
        "upgrade_targets": [
            "digital_legacy_portrait",
            "household_foundation",
            "heirloom_legacy_tree",
            "legacy_plus",
            "family_estate_concierge",
        ],
        "status": "active",
    },
    "digital_legacy_portrait": {
        "package_code": "digital_legacy_portrait",
        "display_name": "Digital Legacy Portrait",
        "package_lane": "portrait",
        "base_price_usd": 399,
        "maintenance_monthly_usd": 39,
        "maintenance_annual_usd": 390,
        "maintenance_lifetime_usd": 0,
        "maintenance_starts_on_delivery": False,
        "max_households": 0,
        "max_members": 1,
        "max_org_nodes": 0,
        "max_uploads": 10,
        "max_zoom_layers": 0,
        "max_storage_gb": 1,
        "can_build_household": False,
        "can_build_family_tree": True,
        "can_build_org_chart": False,
        "can_link_households": False,
        "can_link_org_units": False,
        "can_upload_portraits": True,
        "can_upload_verification_docs": True,
        "can_use_viewer": True,
        "can_use_narration": False,
        "can_use_lineage_certificate": True,
        "can_open_family_intake": True,
        "can_open_org_intake": False,
        "can_use_link_keys": True,
        "can_manage_link_keys": True,
        "protected_workspace": True,
        "guided_intake": True,
        "allowed_addons": [
            "extra_upload_pack",
            "extra_storage",
            "portrait_polish",
            "rush_delivery",
            "tribute_narration",
        ],
        "upgrade_targets": [
            "household_foundation",
            "heirloom_legacy_tree",
            "legacy_plus",
            "family_estate_concierge",
        ],
        "status": "active",
    },
    "household_foundation": {
        "package_code": "household_foundation",
        "display_name": "Household Foundation",
        "package_lane": "household",
        "base_price_usd": 799,
        "maintenance_monthly_usd": 59,
        "maintenance_annual_usd": 590,
        "maintenance_lifetime_usd": 0,
        "maintenance_starts_on_delivery": False,
        "max_households": 1,
        "max_members": 6,
        "max_org_nodes": 0,
        "max_uploads": 20,
        "max_zoom_layers": 2,
        "max_storage_gb": 3,
        "can_build_household": True,
        "can_build_family_tree": True,
        "can_build_org_chart": False,
        "can_link_households": False,
        "can_link_org_units": False,
        "can_upload_portraits": True,
        "can_upload_verification_docs": True,
        "can_use_viewer": True,
        "can_use_narration": False,
        "can_use_lineage_certificate": True,
        "can_open_family_intake": True,
        "can_open_org_intake": False,
        "can_use_link_keys": False,
        "can_manage_link_keys": False,
        "protected_workspace": True,
        "guided_intake": True,
        "allowed_addons": [
            "rush_delivery",
            "on_site_photo_scanning",
        ],
        "upgrade_targets": [
            "heirloom_legacy_tree",
            "legacy_plus",
            "family_estate_concierge",
        ],
        "status": "active",
    },
    "heirloom_legacy_tree": {
        "package_code": "heirloom_legacy_tree",
        "display_name": "Heirloom Legacy Tree",
        "package_lane": "household",
        "base_price_usd": 1500,
        "maintenance_monthly_usd": 89,
        "maintenance_annual_usd": 890,
        "maintenance_lifetime_usd": 0,
        "maintenance_starts_on_delivery": False,
        "max_households": 1,
        "max_members": 15,
        "max_org_nodes": 0,
        "max_uploads": 50,
        "max_zoom_layers": 4,
        "max_storage_gb": 10,
        "can_build_household": True,
        "can_build_family_tree": True,
        "can_build_org_chart": False,
        "can_link_households": False,
        "can_link_org_units": False,
        "can_upload_portraits": True,
        "can_upload_verification_docs": True,
        "can_use_viewer": True,
        "can_use_narration": False,
        "narration_ready_structure": True,
        "can_use_lineage_certificate": True,
        "can_open_family_intake": True,
        "can_open_org_intake": False,
        "can_use_link_keys": False,
        "can_manage_link_keys": False,
        "protected_workspace": True,
        "guided_intake": True,
        "allowed_addons": [
            "rush_delivery",
            "on_site_photo_scanning",
        ],
        "upgrade_targets": [
            "legacy_plus",
            "family_estate_concierge",
        ],
        "status": "active",
    },
    "legacy_plus": {
        "package_code": "legacy_plus",
        "display_name": "Legacy Plus",
        "package_lane": "household",
        "base_price_usd": 3200,
        "maintenance_monthly_usd": 149,
        "maintenance_annual_usd": 1490,
        "maintenance_lifetime_usd": 0,
        "maintenance_starts_on_delivery": False,
        "max_households": 1,
        "max_members": 30,
        "max_org_nodes": 0,
        "max_uploads": 100,
        "max_zoom_layers": 5,
        "max_storage_gb": 25,
        "can_build_household": True,
        "can_build_family_tree": True,
        "can_build_org_chart": False,
        "can_link_households": False,
        "can_link_org_units": False,
        "can_upload_portraits": True,
        "can_upload_verification_docs": True,
        "can_use_viewer": True,
        "can_use_narration": True,
        "narration_ready_structure": True,
        "premium_archive_structure": True,
        "can_use_lineage_certificate": True,
        "can_open_family_intake": True,
        "can_open_org_intake": False,
        "can_use_link_keys": True,
        "can_manage_link_keys": True,
        "protected_workspace": True,
        "guided_intake": True,
        "allowed_addons": [
            "rush_delivery",
            "on_site_photo_scanning",
            "additional_narration_minute",
        ],
        "upgrade_targets": [
            "family_estate_concierge",
        ],
        "status": "active",
    },
    "family_estate_concierge": {
        "package_code": "family_estate_concierge",
        "display_name": "Family Estate Concierge",
        "package_lane": "network",
        "base_price_usd": 6500,
        "maintenance_monthly_usd": 299,
        "maintenance_annual_usd": 2990,
        "maintenance_lifetime_usd": 0,
        "maintenance_starts_on_delivery": False,
        "max_households": 3,
        "max_members": 999,
        "max_org_nodes": 0,
        "max_uploads": 250,
        "max_zoom_layers": 999,
        "max_storage_gb": 50,
        "can_build_household": True,
        "can_build_family_tree": True,
        "can_build_org_chart": False,
        "can_link_households": True,
        "can_link_org_units": False,
        "can_upload_portraits": True,
        "can_upload_verification_docs": True,
        "can_use_viewer": True,
        "can_use_narration": True,
        "can_use_lineage_certificate": True,
        "can_open_family_intake": True,
        "can_open_org_intake": False,
        "can_use_link_keys": True,
        "can_manage_link_keys": True,
        "protected_workspace": True,
        "guided_intake": True,
        "premium_consultation_path": True,
        "custom_structure_planning": True,
        "white_glove_project_handling": True,
        "linked_household_structure": True,
        "network_branch_scope": True,
        "max_family_branches": 3,
        "high_capacity_archival_support": True,
        "continuity_stewardship_options": True,
        "lineage_experience_support": True,
        "organization_command_scope": False,
        "maintenance_included": False,
        "allowed_addons": [
            "extra_mapped_person",
            "extra_zoom_layer",
            "extra_storage",
            "rush_delivery",
            "on_site_photo_scanning",
            "additional_narration_minute",
            "white_glove_archive_support",
        ],
        "upgrade_targets": [],
        "status": "active",
    },
    "command_structure_network": {
        "package_code": "command_structure_network",
        "display_name": "Command Structure Network",
        "package_lane": "organization",
        "base_price_usd": 2999,
        "maintenance_monthly_usd": 199,
        "maintenance_annual_usd": 1990,
        "maintenance_lifetime_usd": 0,
        "maintenance_starts_on_delivery": False,
        "max_households": 0,
        "max_members": 0,
        "max_org_nodes": COMMAND_STRUCTURE_ORG_NODE_LIMIT,
        "organization_node_limit": COMMAND_STRUCTURE_ORG_NODE_LIMIT,
        "organization_profile_enabled": True,
        "organization_nodes_enabled": True,
        "max_uploads": 25,
        "max_zoom_layers": 2,
        "max_storage_gb": 5,
        "can_build_household": False,
        "can_build_family_tree": False,
        "can_build_org_chart": True,
        "can_link_households": False,
        "can_link_org_units": True,
        "can_upload_portraits": True,
        "can_upload_verification_docs": True,
        "can_use_viewer": True,
        "can_use_narration": False,
        "can_use_lineage_certificate": False,
        "can_open_family_intake": False,
        "can_open_org_intake": True,
        "can_use_link_keys": False,
        "can_manage_link_keys": False,
        "protected_workspace": True,
        "guided_intake": True,
        "command_role_mapping_tools": True,
        "role_seats_enabled": True,
        "officer_assignment_history": True,
        "transition_events_enabled": True,
        "structured_organization_lineage": True,
        "verification_support_record_workflows": True,
        "leadership_structure_viewer": True,
        "historical_command_view": True,
        "succession_timeline": True,
        "linked_organization_support": True,
        "command_officer_continuity": True,
        "admin_seat_expansion_paths": True,
        "family_household_scope": False,
        "family_branch_network_scope": False,
        "family_tree_builder": False,
        "household_builder": False,
        "relationship_editor": False,
        "spouse_child_parent_relationships": False,
        "organization_command_scope": True,
        "maintenance_included": False,
        "allowed_addons": [
            "extra_org_level",
            "extra_admin_seat",
            "extra_storage",
            "rush_delivery",
            "command_report_addon",
        ],
        "upgrade_targets": [],
        "status": "active",
    },
}

PACKAGE_CONTROL_POLICY: dict[str, dict[str, Any]] = {
    "legacy_snapshot": {
        "anchor_type": None,
        "launch_policy": {
            "allows_automatic_anchor": False,
            "requires_runtime_flag_for_auto_mint": True,
        },
        "maintenance_default": "monthly",
        "mint_policy": {
            "product_includes_onchain_anchor": False,
            "auto_mint_enabled": False,
            "opt_in_only": False,
            "token_type": None,
            "included_anchor_count": 0,
            "requires_customer_public_safe_approval": False,
            "mint_fee_model": "service_plus_network",
            "minting_included": False,
            "minting_service_fee_usd": 199,
            "default_network_fee_policy": "quoted_variable",
            "additional_mint_service_fee_usd": 199,
            "remint_service_fee_usd": 149,
            "network_fee_quote_usd": 0,
        },
    },
    "legacy_portrait_intro": {
        "anchor_type": None,
        "launch_policy": {
            "allows_automatic_anchor": False,
            "requires_runtime_flag_for_auto_mint": True,
        },
        "maintenance_default": "monthly",
        "mint_policy": {
            "product_includes_onchain_anchor": False,
            "auto_mint_enabled": False,
            "opt_in_only": False,
            "token_type": None,
            "included_anchor_count": 0,
            "requires_customer_public_safe_approval": False,
            "mint_fee_model": "service_plus_network",
            "minting_included": False,
            "minting_service_fee_usd": 199,
            "default_network_fee_policy": "quoted_variable",
            "additional_mint_service_fee_usd": 199,
            "remint_service_fee_usd": 149,
            "network_fee_quote_usd": 0,
        },
    },
    "digital_legacy_portrait": {
        "anchor_type": "portrait_anchor",
        "launch_policy": {
            "allows_automatic_anchor": True,
            "requires_runtime_flag_for_auto_mint": True,
        },
        "maintenance_default": "monthly",
        "mint_policy": {
            "product_includes_onchain_anchor": True,
            "auto_mint_enabled": True,
            "opt_in_only": False,
            "token_type": "portrait_anchor",
            "included_anchor_count": 1,
            "requires_customer_public_safe_approval": True,
            "mint_fee_model": "flat_included",
            "minting_included": True,
            "minting_service_fee_usd": 199,
            "default_network_fee_policy": "quoted_variable",
            "additional_mint_service_fee_usd": 199,
            "remint_service_fee_usd": 149,
            "network_fee_quote_usd": 0,
        },
    },
    "household_foundation": {
        "anchor_type": "household_anchor",
        "launch_policy": {
            "allows_automatic_anchor": True,
            "requires_runtime_flag_for_auto_mint": True,
        },
        "maintenance_default": "monthly",
        "mint_policy": {
            "product_includes_onchain_anchor": True,
            "auto_mint_enabled": True,
            "opt_in_only": False,
            "token_type": "household_anchor",
            "included_anchor_count": 1,
            "requires_customer_public_safe_approval": True,
            "mint_fee_model": "flat_included",
            "minting_included": True,
            "minting_service_fee_usd": 199,
            "default_network_fee_policy": "quoted_variable",
            "additional_mint_service_fee_usd": 199,
            "remint_service_fee_usd": 149,
            "network_fee_quote_usd": 0,
        },
    },
    "heirloom_legacy_tree": {
        "anchor_type": "household_anchor",
        "launch_policy": {
            "allows_automatic_anchor": True,
            "requires_runtime_flag_for_auto_mint": True,
        },
        "maintenance_default": "monthly",
        "mint_policy": {
            "product_includes_onchain_anchor": True,
            "auto_mint_enabled": True,
            "opt_in_only": False,
            "token_type": "household_anchor",
            "included_anchor_count": 1,
            "requires_customer_public_safe_approval": True,
            "mint_fee_model": "flat_included",
            "minting_included": True,
            "minting_service_fee_usd": 199,
            "default_network_fee_policy": "quoted_variable",
            "additional_mint_service_fee_usd": 199,
            "remint_service_fee_usd": 149,
            "network_fee_quote_usd": 0,
        },
    },
    "legacy_plus": {
        "anchor_type": "household_anchor",
        "launch_policy": {
            "allows_automatic_anchor": True,
            "requires_runtime_flag_for_auto_mint": True,
        },
        "maintenance_default": "monthly",
        "mint_policy": {
            "product_includes_onchain_anchor": True,
            "auto_mint_enabled": True,
            "opt_in_only": False,
            "token_type": "household_anchor",
            "included_anchor_count": 1,
            "requires_customer_public_safe_approval": True,
            "mint_fee_model": "flat_included",
            "minting_included": True,
            "minting_service_fee_usd": 199,
            "default_network_fee_policy": "quoted_variable",
            "additional_mint_service_fee_usd": 199,
            "remint_service_fee_usd": 149,
            "network_fee_quote_usd": 0,
        },
    },
    "family_estate_concierge": {
        "anchor_type": "branch_anchor",
        "launch_policy": {
            "allows_automatic_anchor": True,
            "requires_runtime_flag_for_auto_mint": True,
        },
        "maintenance_default": "monthly",
        "mint_policy": {
            "product_includes_onchain_anchor": True,
            "auto_mint_enabled": True,
            "opt_in_only": False,
            "token_type": "branch_anchor",
            "included_anchor_count": 3,
            "requires_customer_public_safe_approval": True,
            "mint_fee_model": "flat_included",
            "minting_included": True,
            "minting_service_fee_usd": 199,
            "default_network_fee_policy": "quoted_variable",
            "additional_mint_service_fee_usd": 199,
            "remint_service_fee_usd": 149,
            "network_fee_quote_usd": 0,
        },
    },
    "command_structure_network": {
        "anchor_type": "organization_anchor",
        "launch_policy": {
            "allows_automatic_anchor": True,
            "requires_runtime_flag_for_auto_mint": True,
        },
        "maintenance_default": "monthly",
        "mint_policy": {
            "product_includes_onchain_anchor": True,
            "auto_mint_enabled": False,
            "opt_in_only": True,
            "token_type": "organization_anchor",
            "included_anchor_count": 1,
            "requires_customer_public_safe_approval": True,
            "mint_fee_model": "service_plus_network",
            "minting_included": False,
            "minting_service_fee_usd": 299,
            "default_network_fee_policy": "quoted_variable",
            "additional_mint_service_fee_usd": 199,
            "remint_service_fee_usd": 149,
            "network_fee_quote_usd": 0,
        },
    },
}

ADDON_CATALOG: dict[str, dict[str, Any]] = {
    "extra_upload_pack": {
        "addon_code": "extra_upload_pack",
        "display_name": "Extra Upload Pack",
        "price_usd": 49,
        "billing_type": "one_time",
        "allowed_lanes": ["portrait", "household", "network", "organization"],
        "status": "active",
    },
    "extra_storage": {
        "addon_code": "extra_storage",
        "display_name": "Extra Storage",
        "price_usd": 50,
        "billing_type": "recurring_or_one_time",
        "allowed_lanes": ["portrait", "household", "network", "organization"],
        "status": "active",
    },
    "portrait_polish": {
        "addon_code": "portrait_polish",
        "display_name": "Portrait Polish",
        "price_usd": 79,
        "billing_type": "one_time",
        "allowed_lanes": ["portrait"],
        "status": "active",
    },
    "tribute_narration": {
        "addon_code": "tribute_narration",
        "display_name": "Tribute Narration",
        "price_usd": 99,
        "billing_type": "one_time",
        "allowed_lanes": ["portrait"],
        "status": "active",
    },
    "rush_delivery": {
        "addon_code": "rush_delivery",
        "display_name": "Rush Delivery",
        "price_usd": None,
        "billing_type": "one_time_percent",
        "allowed_lanes": ["portrait", "household", "network", "organization"],
        "status": "active",
    },
    "extra_mapped_person": {
        "addon_code": "extra_mapped_person",
        "display_name": "Extra Mapped Person",
        "price_usd": 35,
        "billing_type": "one_time",
        "allowed_lanes": ["household", "network"],
        "status": "active",
    },
    "extra_zoom_layer": {
        "addon_code": "extra_zoom_layer",
        "display_name": "Extra Zoom Layer",
        "price_usd": 175,
        "billing_type": "one_time",
        "allowed_lanes": ["household", "network"],
        "status": "active",
    },
    "additional_narration_minute": {
        "addon_code": "additional_narration_minute",
        "display_name": "Additional Narration Minute",
        "price_usd": 200,
        "billing_type": "one_time",
        "allowed_lanes": ["household", "network"],
        "status": "active",
    },
    "on_site_photo_scanning": {
        "addon_code": "on_site_photo_scanning",
        "display_name": "On-Site Photo Scanning",
        "price_usd": 499,
        "billing_type": "one_time",
        "allowed_lanes": ["household", "network"],
        "status": "active",
    },
    "extra_linked_household": {
        "addon_code": "extra_linked_household",
        "display_name": "Extra Linked Household",
        "price_usd": 1000,
        "billing_type": "one_time",
        "allowed_lanes": ["household", "network"],
        "status": "active",
    },
    "extra_branch": {
        "addon_code": "extra_branch",
        "display_name": "Extra Branch",
        "price_usd": 1000,
        "billing_type": "one_time",
        "allowed_lanes": ["network"],
        "status": "active",
    },
    "white_glove_archive_support": {
        "addon_code": "white_glove_archive_support",
        "display_name": "White-Glove Archive Support",
        "price_usd": 1499,
        "billing_type": "one_time",
        "allowed_lanes": ["network"],
        "status": "active",
    },
    "extra_org_node": {
        "addon_code": "extra_org_node",
        "display_name": "Extra Organization Node",
        "price_usd": 45,
        "billing_type": "one_time",
        "allowed_lanes": ["organization"],
        "status": "active",
    },
    "extra_org_level": {
        "addon_code": "extra_org_level",
        "display_name": "Extra Organization Level",
        "price_usd": 175,
        "billing_type": "one_time",
        "allowed_lanes": ["organization"],
        "status": "active",
    },
    "extra_admin_seat": {
        "addon_code": "extra_admin_seat",
        "display_name": "Extra Admin Seat",
        "price_usd": 99,
        "billing_type": "one_time_or_recurring",
        "allowed_lanes": ["organization"],
        "status": "active",
    },
    "command_report_addon": {
        "addon_code": "command_report_addon",
        "display_name": "Command Report Add-On",
        "price_usd": 149,
        "billing_type": "one_time",
        "allowed_lanes": ["organization"],
        "status": "active",
    },
}


def _copy_package(value: dict[str, Any]) -> dict[str, Any]:
    package = deepcopy(value)
    package["package_lane"] = normalize_package_type(package.get("package_lane"))
    package_code = str(package.get("package_code") or "").strip()
    return _with_vault_entitlements(package_code, package)


def get_package_catalog() -> dict[str, dict[str, Any]]:
    return {
        package_code: _copy_package(package)
        for package_code, package in PACKAGE_CATALOG.items()
    }


def get_addon_catalog() -> dict[str, dict[str, Any]]:
    return deepcopy(ADDON_CATALOG)


def normalize_package_code(package_code: Any) -> str:
    raw = str(package_code or "").strip().lower()
    return PACKAGE_CODE_ALIASES.get(
        raw,
        raw,
    )


def canonicalize_package_identifier(value: Any) -> dict[str, Any]:
    raw = str(value or "").strip()
    normalized = normalize_package_code(raw)
    package = PACKAGE_CATALOG.get(normalized)
    if not raw:
        status = "missing"
    elif package and raw.lower() == normalized:
        status = "canonical"
    elif package:
        status = "alias_mapped"
    else:
        status = "unknown"

    return {
        "raw_value": raw,
        "package_code": normalized or "",
        "package_slug": normalized or "",
        "package_name": (package or {}).get("display_name") or raw or "",
        "package_lane": normalize_package_type((package or {}).get("package_lane")),
        "normalization_status": status,
        "is_known": package is not None,
    }


def get_package_identifier_map() -> dict[str, Any]:
    return {
        "aliases": deepcopy(PACKAGE_CODE_ALIASES),
        "packages": {
            package_code: {
                "package_code": package["package_code"],
                "package_slug": package["package_code"],
                "package_name": package["display_name"],
                "package_lane": normalize_package_type(package["package_lane"]),
                "status": package.get("status", "active"),
            }
            for package_code, package in PACKAGE_CATALOG.items()
        },
    }


def normalize_addon_code(addon_code: Any) -> str:
    raw = str(addon_code or "").strip().lower()
    return ADDON_CODE_ALIASES.get(
        raw,
        raw,
    )


def get_package(package_code: Any) -> dict[str, Any] | None:
    normalized = normalize_package_code(package_code)
    if not normalized:
        return None
    value = PACKAGE_CATALOG.get(normalized)
    return _copy_package(value) if value else None


def get_package_control_profile(package_code: str) -> dict[str, Any] | None:
    package = get_package(package_code)
    if not package:
        return None

    normalized_code = str(package.get("package_code") or "").strip()
    policy = deepcopy(PACKAGE_CONTROL_POLICY.get(normalized_code) or {})
    launch_policy = dict(policy.get("launch_policy") or {})
    mint_policy = dict(policy.get("mint_policy") or {})

    return {
        "package_code": normalized_code,
        "package_slug": normalized_code,
        "display_name": package.get("display_name"),
        "package_lane": package.get("package_lane"),
        "anchor_type": policy.get("anchor_type"),
        "launch_policy": {
            "allows_automatic_anchor": bool(launch_policy.get("allows_automatic_anchor")),
            "requires_runtime_flag_for_auto_mint": bool(
                launch_policy.get("requires_runtime_flag_for_auto_mint", True)
            ),
        },
        "maintenance_default": str(policy.get("maintenance_default") or "monthly"),
        "mint_policy": {
            "product_includes_onchain_anchor": bool(
                mint_policy.get("product_includes_onchain_anchor")
            ),
            "auto_mint_enabled": bool(mint_policy.get("auto_mint_enabled")),
            "opt_in_only": bool(mint_policy.get("opt_in_only")),
            "token_type": mint_policy.get("token_type"),
            "included_anchor_count": int(mint_policy.get("included_anchor_count") or 0),
            "requires_customer_public_safe_approval": bool(
                mint_policy.get("requires_customer_public_safe_approval")
            ),
            "mint_fee_model": str(mint_policy.get("mint_fee_model") or "service_plus_network"),
            "minting_included": bool(mint_policy.get("minting_included", int(mint_policy.get("included_anchor_count") or 0) > 0)),
            "minting_service_fee_usd": float(mint_policy.get("minting_service_fee_usd") or 0),
            "default_network_fee_policy": str(mint_policy.get("default_network_fee_policy") or "quoted_variable"),
            "additional_mint_service_fee_usd": float(mint_policy.get("additional_mint_service_fee_usd") or 0),
            "remint_service_fee_usd": float(mint_policy.get("remint_service_fee_usd") or 0),
            "network_fee_quote_usd": float(mint_policy.get("network_fee_quote_usd") or 0),
        },
    }


def list_package_control_profiles() -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    for package_code in PACKAGE_CATALOG:
        profile = get_package_control_profile(package_code)
        if profile is not None:
            profiles.append(profile)
    return profiles


def get_addon(addon_code: str) -> dict[str, Any] | None:
    normalized = normalize_addon_code(addon_code)
    if not normalized:
        return None
    value = ADDON_CATALOG.get(normalized)
    return deepcopy(value) if value else None


def _with_vault_entitlements(package_code: str, package: dict[str, Any]) -> dict[str, Any]:
    entitlements = deepcopy(VAULT_ENTITLEMENT_BY_PACKAGE.get(package_code) or {})
    package.update(entitlements)
    # Keep the legacy premium_archive_structure flag as a compatibility alias
    # for the same household-vault entitlement while route gating converges on
    # can_use_household_vault.
    package["premium_archive_structure"] = bool(package.get("can_use_household_vault"))
    package["allowed_visibility_scopes"] = deepcopy(ALLOWED_VISIBILITY_SCOPES)
    return package


def get_public_package_catalog() -> list[dict[str, Any]]:
    packages: list[dict[str, Any]] = []
    for package_code, raw in PACKAGE_CATALOG.items():
        package = _with_vault_entitlements(package_code, _copy_package(raw))
        control_profile = get_package_control_profile(package_code) or {}
        mint_policy = dict(control_profile.get("mint_policy") or {})
        package["maintenance_default"] = str(control_profile.get("maintenance_default") or "monthly")
        package["maintenance_meaning"] = {
            "covers": [
                "storage continuity",
                "protected access",
                "retrieval",
                "role-based workspace continuity",
                "package-compatible platform updates",
                "delivery continuity",
                "normal support for the delivered project",
            ],
            "does_not_cover": [
                "a new build",
                "new branch creation",
                "genealogy research",
                "major redesign",
                "add-ons not purchased",
            ],
        }
        package["verification_meaning"] = "Verification is a private evidence and review path used to support trusted lineage records."
        package["minting_available"] = bool(mint_policy.get("product_includes_onchain_anchor"))
        package["minting_included"] = bool(mint_policy.get("minting_included", False))
        package["included_anchor_count"] = int(mint_policy.get("included_anchor_count") or 0)
        package["mint_fee_model"] = str(mint_policy.get("mint_fee_model") or "service_plus_network")
        package["minting_service_fee_usd"] = float(mint_policy.get("minting_service_fee_usd") or 0)
        package["additional_mint_service_fee_usd"] = float(mint_policy.get("additional_mint_service_fee_usd") or 0)
        package["remint_service_fee_usd"] = float(mint_policy.get("remint_service_fee_usd") or 0)
        package["default_network_fee_policy"] = str(mint_policy.get("default_network_fee_policy") or "quoted_variable")
        package["minting_copy"] = (
            "Blockchain / NFT minting is a separate one-time production step unless explicitly included in your package. "
            "This fee covers collectible preparation, metadata creation, mint execution, and applicable blockchain network costs. "
            "Private vault materials are not minted by default. "
            "Only approved delivery-safe collectible assets are eligible for blockchain minting."
        )
        package["scheduled_reveal_status"] = "planned_private_beta"
        package["scheduled_reveal_copy"] = (
            "Scheduled reveal is currently planned/private beta and is not generally available for automatic timed release."
        )
        package["scheduled_reveal_auto_executor_live"] = False
        packages.append(package)
    return packages
