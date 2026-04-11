from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.role_catalog import normalize_project_member_role


class ProjectMemberCreate(BaseModel):
    project_id: str = Field(..., min_length=1)
    user_id: str | None = None
    email: str | None = None
    member_role: str = Field(default="viewer", min_length=1, max_length=50)
    status: str = Field(default="active", min_length=1, max_length=50)


class ProjectMemberResponse(BaseModel):
    id: str
    project_id: str
    user_id: str | None = None
    email: str | None = None
    member_role: str
    status: str
    created_at: str
    updated_at: str | None = None


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
    return ProjectMemberResponse(
        id=_as_string(data.get("_id") or data.get("id")),
        project_id=_as_string(data.get("project_id")),
        user_id=_as_string(data.get("user_id")) or None,
        email=_as_string(data.get("email")).lower() or None,
        member_role=normalize_project_member_role(data.get("member_role"), default="viewer"),
        status=_as_string(data.get("status") or "active") or "active",
        created_at=_format_timestamp(created_at, default=datetime.now(UTC).isoformat()),
        updated_at=_format_timestamp(updated_at) or None,
    )
