from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

INTAKE_POLICY_VERSION_DEFAULT = "2026-03-26"


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


class IntakeUploadsPayload(BaseModel):
    approx_upload_count: str = Field(default="")
    primary_asset_type: str = Field(default="")
    key_portraits: str = Field(default="")
    supporting_records: str = Field(default="")
    quality_notes: str = Field(default="")
    uploads_rights_confirmed: bool = Field(default=False)
    uploads_minimization_confirmed: bool = Field(default=False)


class IntakeConsentPayload(BaseModel):
    consent_process: bool = Field(default=False)
    consent_store: bool = Field(default=False)
    consent_authority: bool = Field(default=False)
    consent_review_disclaimer: bool = Field(default=False)
    visibility_preference: str = Field(default="private")
    consent_notes: str = Field(default="")


class IntakeReviewPayload(BaseModel):
    final_intake_notes: str = Field(default="")
    confirm_accuracy: bool = Field(default=False)


class IntakeSubmissionCreate(BaseModel):
    package_slug: str = Field(..., min_length=1)
    package_name: str = Field(..., min_length=1)

    household: IntakeHouseholdPayload
    family_map: IntakeFamilyMapPayload
    uploads: IntakeUploadsPayload
    consent: IntakeConsentPayload
    review: IntakeReviewPayload

    source: str = Field(default="web")
    policy_version: str = Field(
        default=INTAKE_POLICY_VERSION_DEFAULT,
        min_length=1,
        max_length=32,
    )
    submitted_at: Optional[datetime] = None


class IntakeSubmissionStatusUpdate(BaseModel):
    status: str = Field(..., min_length=1)
    review_notes: str = Field(default="")
    approval_notes: str = Field(default="")
    rejection_reason: str = Field(default="")


class IntakeSubmissionResponse(BaseModel):
    id: str
    user_id: str
    email: str
    package_slug: str
    package_name: str
    status: str
    review_locked: bool

    household: dict[str, Any]
    family_map: dict[str, Any]
    uploads: dict[str, Any]
    consent: dict[str, Any]
    review: dict[str, Any]

    policy_version: Optional[str] = None
    submission_source: Optional[str] = None
    submitted_client_at: Optional[datetime] = None
    consent_recorded_at: Optional[datetime] = None

    submitted_at: Optional[datetime] = None
    review_started_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    review_notes: Optional[str] = None
    approval_notes: Optional[str] = None
    rejection_reason: Optional[str] = None

    family_root_id: Optional[str] = None
    household_id: Optional[str] = None
    project_id: Optional[str] = None
    provisioned_at: Optional[datetime] = None
    provisioned_by: Optional[str] = None
    production_notes: Optional[str] = None

    created_at: datetime
    updated_at: datetime


class IntakeSubmissionListItem(BaseModel):
    id: str
    user_id: str
    email: str
    package_slug: str
    package_name: str
    status: str
    review_locked: bool
    policy_version: Optional[str] = None
    submission_source: Optional[str] = None
    submitted_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    family_root_id: Optional[str] = None
    project_id: Optional[str] = None
    created_at: datetime