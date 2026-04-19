from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.role_catalog import normalize_project_member_role


class ProjectMemberCreate(BaseModel):
    project_id: str = Field(..., min_length=1)
    user_id: str | None = None
    user_email: str | None = None
    email: str | None = None
    role: str = Field(default="viewer", min_length=1, max_length=50)
    member_role: str = Field(default="viewer", min_length=1, max_length=50)
    status: str = Field(default="active", min_length=1, max_length=50)
    invited_by: str | None = None
    joined_at: datetime | None = None


class ProjectMemberResponse(BaseModel):
    id: str
    project_id: str
    user_id: str | None = None
    user_email: str | None = None
    email: str | None = None
    role: str
    member_role: str
    status: str
    invited_by: str | None = None
    joined_at: str | None = None
    created_at: str
    updated_at: str | None = None


class ProjectMemberInDB(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str | None = Field(default=None, alias="_id")
    project_id: str
    user_id: str | None = None
    user_email: str | None = None
    email: str | None = None
    role: str = Field(default="viewer")
    member_role: str = Field(default="viewer")
    status: str = Field(default="active")
    invited_by: str | None = None
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
    normalized_role = normalize_project_member_role(
        data.get("member_role") or data.get("role"),
        default="viewer",
    )
    normalized_email = _as_string(data.get("email") or data.get("user_email")).lower() or None
    normalized_user_id = _as_string(data.get("user_id")) or None

    return ProjectMemberResponse(
        id=_as_string(data.get("_id") or data.get("id")),
        project_id=_as_string(data.get("project_id")),
        user_id=normalized_user_id,
        user_email=normalized_email,
        email=normalized_email,
        role=normalized_role,
        member_role=normalized_role,
        status=_as_string(data.get("status") or "active") or "active",
        invited_by=_as_string(data.get("invited_by")) or None,
        joined_at=_format_timestamp(data.get("joined_at")) or None,
        created_at=_format_timestamp(created_at, default=datetime.now(UTC).isoformat()),
        updated_at=_format_timestamp(updated_at) or None,
    )
