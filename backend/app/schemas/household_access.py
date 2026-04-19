from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.role_catalog import normalize_project_member_role

HOUSEHOLD_PRIVACY_SCOPES: tuple[str, ...] = (
    "private_to_owner",
    "private_to_owner_and_co_owner",
    "household_private",
    "household_shared",
    "read_only",
    "link_only",
    "branch_shared",
    "linked_family_shared",
    "public_memorial",
    "minor_protected",
)


class HouseholdMemberRoleUpdate(BaseModel):
    member_role: str = Field(..., min_length=1, max_length=50)


class HouseholdInviteCreate(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    member_role: str = Field(default="viewer", min_length=1, max_length=50)
    relationship_scope: str = Field(default="household_member", max_length=100)
    privacy_scope: Literal[
        "private_to_owner",
        "private_to_owner_and_co_owner",
        "household_private",
        "household_shared",
        "read_only",
        "link_only",
        "branch_shared",
        "linked_family_shared",
        "public_memorial",
        "minor_protected",
    ] = "household_private"
    notes: str = Field(default="", max_length=500)
    expires_in_days: int = Field(default=7, ge=1, le=90)
    max_uses: int = Field(default=1, ge=1, le=10)


class HouseholdInviteAccept(BaseModel):
    invite_key: str = Field(..., min_length=6, max_length=200)


def _normalize_value(value: Any) -> str:
    return str(value or "").strip()


def _normalize_privacy_scope_value(value: Any) -> str:
    normalized = _normalize_value(value or "household_private").lower()
    if normalized == "branch_shared":
        return "household_shared"
    if normalized == "linked_family_shared":
        return "link_only"
    if normalized == "public_memorial":
        return "read_only"
    return normalized


def _serialize_dt(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    normalized = _normalize_value(value)
    return normalized or None


def _coerce_int(value: Any, *, default: int, minimum: int = 0) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        normalized = int(default)
    return max(minimum, normalized)


def build_membership_response(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _normalize_value(data.get("_id") or data.get("id")),
        "project_id": _normalize_value(data.get("project_id")),
        "user_id": _normalize_value(data.get("user_id")) or None,
        "email": _normalize_value(data.get("email")).lower() or None,
        "full_name": _normalize_value(data.get("full_name")) or None,
        "first_name": _normalize_value(data.get("first_name")) or None,
        "last_name": _normalize_value(data.get("last_name")) or None,
        "member_role": normalize_project_member_role(data.get("member_role"), default="viewer"),
        "relationship_scope": _normalize_value(data.get("relationship_scope") or "household_member"),
        "privacy_scope": _normalize_privacy_scope_value(data.get("privacy_scope") or "household_private"),
        "status": _normalize_value(data.get("status") or "active"),
        "invited_by_user_id": _normalize_value(data.get("invited_by_user_id")) or None,
        "joined_at": _serialize_dt(data.get("joined_at") or data.get("created_at")),
        "created_at": _serialize_dt(data.get("created_at")) or datetime.now(UTC).isoformat(),
        "updated_at": _serialize_dt(data.get("updated_at")),
    }


def build_invite_response(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _normalize_value(data.get("_id") or data.get("id")),
        "project_id": _normalize_value(data.get("project_id")),
        "email": _normalize_value(data.get("email")).lower(),
        "invite_key": _normalize_value(data.get("invite_key")) or None,
        "status": _normalize_value(data.get("status") or "pending"),
        "email_delivery_status": _normalize_value(data.get("email_delivery_status")) or None,
        "email_delivery_error": _normalize_value(data.get("email_delivery_error")) or None,
        "member_role": normalize_project_member_role(data.get("member_role"), default="viewer"),
        "relationship_scope": _normalize_value(data.get("relationship_scope") or "household_member"),
        "privacy_scope": _normalize_privacy_scope_value(data.get("privacy_scope") or "household_private"),
        "max_uses": _coerce_int(data.get("max_uses"), default=1, minimum=1),
        "use_count": _coerce_int(data.get("use_count"), default=0, minimum=0),
        "notes": _normalize_value(data.get("notes")),
        "expires_at": _serialize_dt(data.get("expires_at")),
        "expired_at": _serialize_dt(data.get("expired_at")),
        "accepted_at": _serialize_dt(data.get("accepted_at")),
        "revoked_at": _serialize_dt(data.get("revoked_at")),
        "created_at": _serialize_dt(data.get("created_at")) or datetime.now(UTC).isoformat(),
        "updated_at": _serialize_dt(data.get("updated_at")),
    }
