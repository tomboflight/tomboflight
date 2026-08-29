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
ACTIVE_LINK_STATUSES = {"approved", "active", "accepted", "verified", "linked"}
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
    is_project_owner: bool = False,
) -> bool:
    normalized_scope = normalize_privacy_scope(privacy_scope)
    normalized_role = normalize_project_member_role(member_role, default="viewer")
    normalized_relationship = str(relationship_scope or "").strip().lower()
    normalized_link_status = str(link_status or "").strip().lower()

    if normalized_scope == "public_memorial":
        return True
    if normalized_scope == "private_to_owner":
        # "Private to me" is uploader/record-owner only.  A billing owner may
        # administer the workspace, but that must not silently make another
        # customer's owner-only file readable.
        return bool(is_owner)
    if normalized_scope == "private_to_owner_and_co_owner":
        return bool(
            is_owner
            or is_project_owner
            or normalized_role in {"billing_owner", "co_owner"}
        )
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
            return normalized_link_status in ACTIVE_LINK_STATUSES
        return normalized_link_status in ACTIVE_LINK_STATUSES and normalized_relationship in {
            "linked_relative",
            "branch_relative",
        }
    return False


def can_manage_privacy_scope(
    *,
    privacy_scope: str,
    member_role: str,
    is_owner: bool = False,
    is_project_owner: bool = False,
) -> bool:
    """Return whether a customer may mutate/delete a record in this scope.

    Read access and management access deliberately remain separate.  In
    particular, family managers must not be able to reclassify an uploader's
    owner-only file and use that mutation to grant themselves read access.
    """

    normalized_scope = normalize_privacy_scope(privacy_scope)
    normalized_role = normalize_project_member_role(member_role, default="viewer")

    if is_owner:
        return True
    if normalized_scope == "private_to_owner":
        return False
    if normalized_scope == "private_to_owner_and_co_owner":
        return bool(
            is_project_owner
            or normalized_role in {"billing_owner", "co_owner"}
        )
    if normalized_scope in {
        "household_private",
        "minor_protected",
        "branch_shared",
        "linked_family_shared",
        "public_memorial",
    }:
        return bool(
            is_project_owner
            or normalized_role in {"billing_owner", "co_owner", "family_manager"}
        )
    return False


def account_access_is_enabled(record: dict[str, Any]) -> bool:
    """Fail closed for records explicitly disabled during account deletion.

    Legacy upload rows predate the flag, so a missing value remains readable;
    every newly-created row writes an explicit ``True`` value.  Either deletion
    marker always wins.
    """

    if bool(record.get("owner_account_deleted")):
        return False
    return record.get("account_access_enabled") is not False


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
        is_project_owner=False,
    )
