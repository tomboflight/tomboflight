from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IntakeHouseholdPayload(BaseModel):
    household_name: str = Field(..., min_length=1)
    primary_contact_name: str = Field(..., min_length=1)
    primary_contact_email: str = Field(..., min_length=1)
    primary_contact_phone: str = Field(default="")
    co_owner_name: str = Field(default="")
    household_role: str = Field(default="")
    project_scope: str = Field(default="")
    special_notes: str = Field(default="")


class IntakeFamilyMapPayload(BaseModel):
    family_branch_name: str = Field(..., min_length=1)
    people_in_scope: str = Field(default="")
    parent_one: str = Field(default="")
    parent_two: str = Field(default="")
    spouse_partner: str = Field(default="")
    children_names: str = Field(default="")
    family_structure_summary: str = Field(default="")
    branch_notes: str = Field(default="")


class IntakeReviewPayload(BaseModel):
    final_intake_notes: str = Field(default="")
    confirm_accuracy: bool = Field(default=False)


class IntakeSubmissionCreate(BaseModel):
    package_slug: str = Field(..., min_length=1)
    package_name: str = Field(..., min_length=1)
    household: IntakeHouseholdPayload
    family_map: IntakeFamilyMapPayload
    review: IntakeReviewPayload


class IntakeSubmissionResponse(BaseModel):
    id: str
    user_id: str
    email: str
    package_slug: str
    package_name: str
    status: str
    household: dict[str, Any]
    family_map: dict[str, Any]
    review: dict[str, Any]
    created_at: datetime
    updated_at: datetime