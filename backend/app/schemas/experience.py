from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class UserProfileUpdate(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=150)


class UserProfileResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    status: str
    created_at: str
    last_login_at: str | None = None
    policy_version: str | None = None
    legal_acceptance: dict[str, Any] = Field(default_factory=dict)


class AccessContextResponse(BaseModel):
    user_id: str
    email: str
    role: str
    status: str
    package_lane: str
    active_project_id: str | None = None
    active_family_id: str | None = None
    active_entitlements: list[str] = Field(default_factory=list)
    project_permissions: list[str] = Field(default_factory=list)
    allowed_experience_modules: list[str] = Field(default_factory=list)
    experience_mode: str
    legal_acceptance: dict[str, Any] = Field(default_factory=dict)


class ExperienceTransitionOption(BaseModel):
    chamber: str
    label: str
    unlocked: bool = True
    reason: str | None = None


class JourneyCheckpoint(BaseModel):
    key: str
    label: str
    completed: bool
    detail: str


class ModuleUnlock(BaseModel):
    module_key: str
    unlocked: bool
    reason: str


class ExperienceSessionStartRequest(BaseModel):
    project_id: str = Field(..., min_length=1)
    preferred_chamber: str | None = Field(default=None, max_length=80)


class ExperienceTransitionRequest(BaseModel):
    project_id: str = Field(..., min_length=1)
    next_chamber: str = Field(..., min_length=1, max_length=80)


class ExperienceMapResponse(BaseModel):
    project_id: str
    package_lane: str
    recommended_entry_chamber: str
    chamber_sequence: list[str] = Field(default_factory=list)
    available_chambers: list[ExperienceTransitionOption] = Field(default_factory=list)


class RecommendedNextStepResponse(BaseModel):
    chamber: str
    summary: str
    reason: str


class ExperienceSessionResponse(BaseModel):
    project_id: str
    family_id: str | None = None
    package_lane: str
    current_chamber: str
    chamber_title: str
    allowed_transitions: list[ExperienceTransitionOption] = Field(default_factory=list)
    featured_focus: dict[str, Any] = Field(default_factory=dict)
    urgent_tasks: list[str] = Field(default_factory=list)
    verification_progress: dict[str, Any] = Field(default_factory=dict)
    archive_progress: dict[str, Any] = Field(default_factory=dict)
    suggested_storyline_moment: str | None = None
    live_event_count: int = 0
    recommended_next_transition: str | None = None
    unlocked_modules: list[ModuleUnlock] = Field(default_factory=list)
    checkpoints: list[JourneyCheckpoint] = Field(default_factory=list)


class ExperienceLaneResponse(BaseModel):
    project_id: str
    project_lane: str
    package_code: str
    package_name: str
    experience_mode: str
    allowed_chambers: list[str] = Field(default_factory=list)
    unlocked_modules: list[str] = Field(default_factory=list)


class LineageChamberSummaryResponse(BaseModel):
    family_id: str
    family_name: str
    verified_nodes: int
    incomplete_nodes: int
    orphaned_branches: int
    narrative_ready_segments: int
    certificate_ready_segments: int
    pending_uploads: int
    unresolved_identity_links: int
    trust_state: dict[str, Any] = Field(default_factory=dict)
    branch_summary: list[dict[str, Any]] = Field(default_factory=list)


class ExperienceStoryResponse(BaseModel):
    family_id: str
    opening_summary: str
    key_lineage_branches: list[dict[str, Any]] = Field(default_factory=list)
    major_verified_milestones: list[str] = Field(default_factory=list)
    unresolved_mysteries: list[str] = Field(default_factory=list)
    important_descendants: list[dict[str, Any]] = Field(default_factory=list)
    recommended_next_path: str
    archive_highlights: list[str] = Field(default_factory=list)
    certificate_progress: dict[str, Any] = Field(default_factory=dict)


class PresenceStatusResponse(BaseModel):
    status: str
    active_connections: int
    channels: dict[str, int] = Field(default_factory=dict)
    websocket_paths: list[str] = Field(default_factory=list)


class ExperienceChamberResponse(BaseModel):
    user_identity_summary: dict[str, Any] = Field(default_factory=dict)
    project_lane: str
    current_chamber: str
    featured_family: dict[str, Any] = Field(default_factory=dict)
    lineage_summary: dict[str, Any] = Field(default_factory=dict)
    archive_summary: dict[str, Any] = Field(default_factory=dict)
    trust_summary: dict[str, Any] = Field(default_factory=dict)
    certificate_readiness: dict[str, Any] = Field(default_factory=dict)
    narrative_summary: dict[str, Any] = Field(default_factory=dict)
    live_presence: dict[str, Any] = Field(default_factory=dict)
    recommended_next_transition: dict[str, Any] = Field(default_factory=dict)
    unlocked_modules: list[str] = Field(default_factory=list)
