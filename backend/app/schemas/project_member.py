from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ProjectMemberRole(str, Enum):
    owner = "owner"
    collaborator = "collaborator"
    viewer = "viewer"
    admin = "admin"


class ProjectMemberStatus(str, Enum):
    active = "active"
    invited = "invited"
    suspended = "suspended"


class ProjectMemberCreate(BaseModel):
    project_id: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)
    user_email: str = Field(..., min_length=1)
    role: ProjectMemberRole = ProjectMemberRole.viewer
    status: ProjectMemberStatus = ProjectMemberStatus.active
    invited_by: str | None = None
    joined_at: datetime | None = None


class ProjectMemberResponse(BaseModel):
    id: str
    project_id: str
    user_id: str
    user_email: str
    role: ProjectMemberRole
    status: ProjectMemberStatus
    invited_by: str | None = None
    joined_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None


class ProjectMemberInDB(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str | None = Field(default=None, alias="_id")
    project_id: str
    user_id: str
    user_email: str
    role: ProjectMemberRole = ProjectMemberRole.viewer
    status: ProjectMemberStatus = ProjectMemberStatus.active
    invited_by: str | None = None
    joined_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None
