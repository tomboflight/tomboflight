from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.role_catalog import normalize_project_member_role


class ProjectMemberRole(str, Enum):
    billing_owner = "billing_owner"
    co_owner = "co_owner"
    family_manager = "family_manager"
    contributor = "contributor"
    viewer = "viewer"
    minor_viewer = "minor_viewer"
    linked_relative = "linked_relative"
    legacy_executor = "legacy_executor"


class ProjectMemberStatus(str, Enum):
    active = "active"
    invited = "invited"
    suspended = "suspended"
    revoked = "revoked"
    inactive = "inactive"


class ProjectMemberCreate(BaseModel):
    project_id: str = Field(..., min_length=1)
    user_id: str | None = None
    user_email: str | None = None
    email: str | None = None
    member_role: str = Field(default="viewer", min_length=1, max_length=50)
    status: str = Field(default="active", min_length=1, max_length=50)
    invited_by_user_id: str | None = None
    joined_at: datetime | None = None


class ProjectMemberResponse(BaseModel):
    id: str
    project_id: str
    user_id: str | None = None
    email: str | None = None
    user_email: str | None = None
    member_role: str = "viewer"
    status: str = "active"
    invited_by_user_id: str | None = None
    joined_at: str | None = None
    created_at: str
    updated_at: str | None = None


class ProjectMemberInDB(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str | None = Field(default=None, alias="_id")
    project_id: str
    user_id: str | None = None
    email: str | None = None
    user_email: str | None = None
    member_role: str = Field(default="viewer")
    status: str = Field(default="active")
    invited_by_user_id: str | None = None
    joined_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None


def _as_string(value: Any) -> str:
    return str(value or "").strip()


def _format_timestamp(value: Any, *, default: str = "") -> str:
    if isinstance(value, datetime):
        return value.isoformat()

    normalized = _as_string(value)
    if normalized:
        return normalized

    return default


def build_project_member_response(data: dict[str, Any]) -> ProjectMemberResponse:
    created_at = data.get("created_at")
    updated_at = data.get("updated_at")
    joined_at = data.get("joined_at")
    normalized_email = _as_string(data.get("email") or data.get("user_email")).lower() or None
    return ProjectMemberResponse(
        id=_as_string(data.get("_id") or data.get("id")),
        project_id=_as_string(data.get("project_id")),
        user_id=_as_string(data.get("user_id")) or None,
        email=normalized_email,
        user_email=normalized_email,
        member_role=normalize_project_member_role(data.get("member_role"), default="viewer"),
        status=_as_string(data.get("status") or "active") or "active",
        invited_by_user_id=_as_string(data.get("invited_by_user_id")) or None,
        joined_at=_format_timestamp(joined_at) or None,
        created_at=_format_timestamp(created_at, default=datetime.now(UTC).isoformat()),
        updated_at=_format_timestamp(updated_at) or None,
    )
