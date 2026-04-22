from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.core.package_catalog import get_package_catalog
from app.services.experience_catalog_service import derive_allowed_modules

WORKSPACE_DEFAULT_MEMBER_ROLES: list[str] = [
    "billing_owner",
    "co_owner",
    "family_manager",
    "contributor",
    "viewer",
    "minor_viewer",
    "linked_relative",
    "legacy_executor",
]

WORKSPACE_VISIBILITY_RULES: dict[str, str] = {
    "membership_first": "project_members record grants access before owner fallback checks",
    "owner_fallback": "owner_user_id/owner_email retains billing-owner access",
    "admin_override": "internal admin roles can traverse workspace context",
    "family_fallback": "family visibility fallback applies only when family owner markers are absent",
}

LIFECYCLE_NOTES: dict[str, str] = {
    "upgrade": "only upgrade_targets listed by package are accepted in purchase flow",
    "downgrade": "downgrades are blocked in current purchase flow (no allowed reverse path)",
    "maintenance": "maintenance status is tracked but does not revoke package capability flags",
    "inactive_entitlement": "workspace access depends on membership/owner checks even when entitlement state is inactive",
}


def _feature_access_from_package(package: dict[str, Any]) -> dict[str, Any]:
    entitlements = deepcopy(package)
    package_lane = str(package.get("package_lane") or "").strip().lower()

    return {
        "can_build_household": bool(entitlements.get("can_build_household")),
        "can_build_family_tree": bool(entitlements.get("can_build_family_tree")),
        "can_build_org_chart": bool(entitlements.get("can_build_org_chart")),
        "can_link_households": bool(entitlements.get("can_link_households")),
        "can_link_org_units": bool(entitlements.get("can_link_org_units")),
        "can_upload_portraits": bool(entitlements.get("can_upload_portraits")),
        "can_upload_verification_docs": bool(entitlements.get("can_upload_verification_docs")),
        "can_use_viewer": bool(entitlements.get("can_use_viewer")),
        "can_use_narration": bool(entitlements.get("can_use_narration")),
        "narration_ready_structure": bool(entitlements.get("narration_ready_structure")),
        "premium_archive_structure": bool(entitlements.get("premium_archive_structure")),
        "can_use_lineage_certificate": bool(entitlements.get("can_use_lineage_certificate")),
        "can_open_family_intake": bool(entitlements.get("can_open_family_intake")),
        "can_open_org_intake": bool(entitlements.get("can_open_org_intake")),
        "can_use_link_keys": bool(entitlements.get("can_use_link_keys")),
        "can_manage_link_keys": bool(entitlements.get("can_manage_link_keys")),
        "workspace_modules_enabled": derive_allowed_modules(package_lane, entitlements),
    }


def _hard_limits_from_package(package: dict[str, Any]) -> dict[str, Any]:
    return {
        "max_uploads": int(package.get("max_uploads") or 0),
        "max_storage_gb": float(package.get("max_storage_gb") or 0),
        "max_members": int(package.get("max_members") or 0),
        "max_households": int(package.get("max_households") or 0),
        "max_org_nodes": int(package.get("max_org_nodes") or 0),
        "max_zoom_layers": int(package.get("max_zoom_layers") or 0),
    }


def _lifecycle_behavior_from_package(package: dict[str, Any]) -> dict[str, Any]:
    return {
        "upgrade_targets": list(package.get("upgrade_targets") or []),
        "downgrade_policy": LIFECYCLE_NOTES["downgrade"],
        "maintenance_behavior": LIFECYCLE_NOTES["maintenance"],
        "inactive_entitlement_behavior": LIFECYCLE_NOTES["inactive_entitlement"],
    }


def build_entitlement_conformance_matrix() -> dict[str, Any]:
    package_catalog = get_package_catalog()

    lanes: dict[str, dict[str, Any]] = {
        "portrait": {"packages": {}},
        "household": {"packages": {}},
        "network": {"packages": {}},
        "organization": {"packages": {}},
    }

    for package_code, package in package_catalog.items():
        package_lane = str(package.get("package_lane") or "").strip().lower()
        if package_lane not in lanes:
            continue

        lanes[package_lane]["packages"][package_code] = {
            "package_code": package_code,
            "display_name": package.get("display_name"),
            "hard_limits": _hard_limits_from_package(package),
            "feature_access": _feature_access_from_package(package),
            "workspace_behavior": {
                "default_member_roles": list(WORKSPACE_DEFAULT_MEMBER_ROLES),
                "visibility_rules": deepcopy(WORKSPACE_VISIBILITY_RULES),
                "access_boundary": "project-scoped access only; cross-project access requires explicit membership/owner/admin path",
            },
            "lifecycle_behavior": _lifecycle_behavior_from_package(package),
        }

    return {
        "version": "phase1-v1",
        "single_source_of_truth": "backend.app.core.entitlement_conformance_matrix",
        "lifecycle_global_notes": deepcopy(LIFECYCLE_NOTES),
        "lanes": lanes,
    }


def validate_entitlement_conformance_matrix(matrix: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    package_catalog = get_package_catalog()

    covered_packages: set[str] = set()
    lanes = matrix.get("lanes") if isinstance(matrix, dict) else {}
    if not isinstance(lanes, dict):
        return ["Matrix lanes payload is invalid."]

    for lane_key in ("portrait", "household", "network", "organization"):
        lane_value = lanes.get(lane_key)
        if not isinstance(lane_value, dict):
            errors.append(f"Lane '{lane_key}' is missing or invalid.")
            continue

        lane_packages = lane_value.get("packages")
        if not isinstance(lane_packages, dict):
            errors.append(f"Lane '{lane_key}' packages payload is invalid.")
            continue

        for package_code, definition in lane_packages.items():
            covered_packages.add(package_code)
            source = package_catalog.get(package_code)
            if source is None:
                errors.append(f"Matrix includes unknown package '{package_code}'.")
                continue

            source_lane = str(source.get("package_lane") or "").strip().lower()
            if source_lane != lane_key:
                errors.append(
                    f"Package '{package_code}' lane mismatch: matrix={lane_key} source={source_lane}."
                )

            hard_limits = (definition or {}).get("hard_limits") if isinstance(definition, dict) else {}
            if not isinstance(hard_limits, dict):
                errors.append(f"Package '{package_code}' has invalid hard_limits.")
                continue

            for limit_key in (
                "max_uploads",
                "max_storage_gb",
                "max_members",
                "max_households",
                "max_org_nodes",
                "max_zoom_layers",
            ):
                if limit_key not in hard_limits:
                    errors.append(f"Package '{package_code}' missing hard limit '{limit_key}'.")

    source_packages = set(package_catalog.keys())
    missing = sorted(source_packages - covered_packages)
    extra = sorted(covered_packages - source_packages)

    for package_code in missing:
        errors.append(f"Matrix missing package '{package_code}'.")
    for package_code in extra:
        errors.append(f"Matrix has non-catalog package '{package_code}'.")

    return errors


def get_entitlement_conformance_matrix() -> dict[str, Any]:
    matrix = build_entitlement_conformance_matrix()
    errors = validate_entitlement_conformance_matrix(matrix)
    if errors:
        raise ValueError("Entitlement conformance matrix is invalid: " + "; ".join(errors))
    return matrix
