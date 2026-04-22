from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class OrganizationProfileUpsert(BaseModel):
    organization_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    organization_name: str = Field(min_length=1)
    organization_type: str = Field(min_length=1)
    organization_subtype: str | None = None
    legal_name: str | None = None
    short_name: str | None = None
    jurisdiction: str | None = None
    nation_state_region: str | None = None
    charter_number_or_unit_number: str | None = None
    parent_organization: str | None = None
    founding_date_or_charter_date: date | None = None
    status: str = "active"
    description: str | None = None
    mission: str | None = None
    logo_upload_id: str | None = None
    visibility: str = "private"


class OrganizationNodeCreate(BaseModel):
    node_key: str = Field(min_length=1)
    node_name: str = Field(min_length=1)
    node_type: str = Field(min_length=1)
    description: str | None = None
    visibility: str = "private"


class RoleSeatCreate(BaseModel):
    node_id: str = Field(min_length=1)
    role_key: str = Field(min_length=1)
    role_name: str = Field(min_length=1)
    seat_status: str = "active"
    description: str | None = None


class OrganizationPersonCreate(BaseModel):
    person_id: str = Field(min_length=1)
    full_name: str = Field(min_length=1)
    display_name: str | None = None
    rank_title_honorific: str | None = None
    organization_specific_title: str | None = None
    status: str = "active"
    biography: str | None = None
    portrait_upload_id: str | None = None
    visibility: str = "private"


class AssignmentCreate(BaseModel):
    assignment_id: str = Field(min_length=1)
    node_id: str = Field(min_length=1)
    role_seat_id: str = Field(min_length=1)
    person_id: str = Field(min_length=1)
    title_at_time: str | None = None
    rank_at_time: str | None = None
    start_date: date
    end_date: date | None = None
    status: str = "active"
    appointment_source: str | None = None
    evidence_record_ids: list[str] = Field(default_factory=list)
    notes: str | None = None
    verified_status: str = "unverified"
    acting_or_interim: bool = False


class EndAssignmentPayload(BaseModel):
    end_date: date
    status: str = "ended"
    notes: str | None = None


class ReplaceRoleSeatPayload(BaseModel):
    assignment_id: str = Field(min_length=1)
    person_id: str = Field(min_length=1)
    title_at_time: str | None = None
    rank_at_time: str | None = None
    start_date: date
    appointment_source: str | None = None
    notes: str | None = None
    evidence_record_ids: list[str] = Field(default_factory=list)
    verified_status: str = "unverified"
    acting_or_interim: bool = False


class TransitionEventCreate(BaseModel):
    transition_id: str = Field(min_length=1)
    assignment_id: str | None = None
    role_seat_id: str | None = None
    person_id: str | None = None
    event_type: str = Field(min_length=1)
    event_date: date
    notes: str | None = None
    evidence_record_ids: list[str] = Field(default_factory=list)


class SupportRecordCreate(BaseModel):
    support_record_id: str = Field(min_length=1)
    target_type: Literal["organization", "node", "role_seat", "person", "assignment", "transition"]
    target_id: str = Field(min_length=1)
    upload_id: str = Field(min_length=1)
    title: str | None = None
    notes: str | None = None
    privacy_level: Literal["private", "restricted", "confidential"] = "private"
    sensitive: bool = False


class LinkedOrganizationCreate(BaseModel):
    linked_organization_id: str = Field(min_length=1)
    link_type: str = Field(min_length=1)
    notes: str | None = None


class SupportRecordVerifyPayload(BaseModel):
    status: Literal["verified", "rejected", "needs_more_info"]
    note: str | None = None


class AdminSeatInvitePayload(BaseModel):
    project_id: str = Field(min_length=1)
    email: str = Field(min_length=3)
    role: Literal["organization_admin", "viewer", "contributor"]


class OrganizationNotePayload(BaseModel):
    project_id: str = Field(min_length=1)
    note: str = Field(min_length=1)
    visibility: Literal["internal", "workspace"] = "workspace"


class WhiteGloveRequestPayload(BaseModel):
    project_id: str = Field(min_length=1)
    note: str | None = None
