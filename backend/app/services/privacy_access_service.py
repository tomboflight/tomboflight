from __future__ import annotations

from typing import Any

from app.core.role_catalog import normalize_project_member_role

PRIVACY_SCOPE_ALIASES = {
    "private": "private_to_owner",
    "family_shared": "household_private",
    "linked_family_shared": "linked_family_shared",
    "internal_only": "private_to_owner",
    "public": "public_memorial",
    "owner_only": "private_to_owner",
    "household_only": "household_private",
    "shared": "branch_shared",
    "admin_only": "private_to_owner",
}

MINOR_SAFE_SCOPES = {"minor_protected", "public_memorial"}
LINK_SHARED_SCOPES = {"linked_family_shared", "branch_shared", "public_memorial"}
HOUSEHOLD_ROLES = {"billing_owner", "co_owner", "family_manager", "contributor", "viewer", "minor_viewer"}


def normalize_privacy_scope(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return "private_to_owner"
    return PRIVACY_SCOPE_ALIASES.get(normalized, normalized)


def can_access_privacy_scope(
    *,
    privacy_scope: str,
    member_role: str,
    relationship_scope: str = "",
    link_status: str = "",
    is_owner: bool = False,
) -> bool:
    normalized_scope = normalize_privacy_scope(privacy_scope)
    normalized_role = normalize_project_member_role(member_role, default="viewer")
    normalized_relationship = str(relationship_scope or "").strip().lower()
    normalized_link_status = str(link_status or "").strip().lower()

    if normalized_scope == "public_memorial":
        return True
    if normalized_scope == "private_to_owner":
        return bool(is_owner or normalized_role == "billing_owner")
    if normalized_scope == "private_to_owner_and_co_owner":
        return bool(is_owner or normalized_role in {"billing_owner", "co_owner"})
    if normalized_scope == "minor_protected":
        return normalized_role in {"billing_owner", "co_owner", "family_manager", "minor_viewer"}
    if normalized_scope == "household_private":
        return normalized_role in HOUSEHOLD_ROLES
    if normalized_scope == "branch_shared":
        if normalized_role in {"billing_owner", "co_owner", "family_manager", "contributor"}:
            return True
        return normalized_relationship in {"branch_member", "branch_relative"}
    if normalized_scope == "linked_family_shared":
        if normalized_role in {"billing_owner", "co_owner", "family_manager"}:
            return True
        if normalized_role == "linked_relative":
            return normalized_link_status in {"approved", "active", "verified"}
        return normalized_link_status in {"approved", "active", "verified"} and normalized_relationship in {
            "linked_relative",
            "branch_relative",
        }
    return False


def can_access_cinematic_asset(
    *,
    asset: dict[str, Any],
    member_role: str,
    relationship_scope: str = "",
    link_status: str = "",
    is_owner: bool = False,
) -> bool:
    if not bool(asset.get("approved_for_cinematic")):
        return False
    if str(asset.get("verification_status") or "").strip().lower() in {"rejected", "blocked"}:
        return False
    if str(asset.get("consent_status") or "").strip().lower() in {"revoked", "denied"}:
        return False
    return can_access_privacy_scope(
        privacy_scope=asset.get("privacy_scope") or asset.get("visibility_scope") or "private_to_owner",
        member_role=member_role,
        relationship_scope=relationship_scope,
        link_status=link_status,
        is_owner=is_owner,
    )
