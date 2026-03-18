from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class HouseholdIntakePayload(BaseModel):
    household_name: str = Field(..., min_length=1)
    primary_contact_name: str = Field(..., min_length=1)
    primary_contact_email: str = Field(..., min_length=1)
    primary_contact_phone: Optional[str] = ""
    co_owner_name: Optional[str] = ""
    household_role: str = Field(..., min_length=1)
    project_scope: str = Field(..., min_length=1)
    special_notes: Optional[str] = ""


class FamilyMapIntakePayload(BaseModel):
    family_branch_name: str = Field(..., min_length=1)
    people_in_scope: str = Field(..., min_length=1)
    parent_one: str = Field(..., min_length=1)
    parent_two: Optional[str] = ""
    spouse_partner: Optional[str] = ""
    children_names: str = Field(..., min_length=1)
    family_structure_summary: str = Field(..., min_length=1)
    branch_notes: Optional[str] = ""


class ReviewIntakePayload(BaseModel):
    final_intake_notes: Optional[str] = ""
    confirm_accuracy: bool = False


class IntakeSubmissionCreate(BaseModel):
    package_slug: str = Field(..., min_length=1)
    package_name: str = Field(..., min_length=1)
    household: HouseholdIntakePayload
    family_map: FamilyMapIntakePayload
    review: ReviewIntakePayload


class IntakeSubmissionResponse(BaseModel):
    id: str
    user_id: str
    email: str
    package_slug: str
    package_name: str
    status: str
    created_at: datetime
    updated_at: datetime


class IntakeSubmissionDetailResponse(BaseModel):
    id: str
    user_id: str
    email: str
    package_slug: str
    package_name: str
    status: str
    household: HouseholdIntakePayload
    family_map: FamilyMapIntakePayload
    review: ReviewIntakePayload
    created_at: datetime
    updated_at: datetime