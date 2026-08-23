from datetime import datetime, UTC
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FamilyMemberCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    family_id: str = Field(..., min_length=1)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    middle_name: str | None = Field(default=None, max_length=100)
    birth_year: int | None = Field(default=None, ge=1000, le=2200)
    birth_date: str | None = Field(default=None, max_length=50)
    generation: int | None = Field(default=None, ge=0)
    generation_locked: bool = False
    father_id: str | None = None
    mother_id: str | None = None
    spouse_id: str | None = None
    father_relationship_type: str = "biological_parent"
    mother_relationship_type: str = "biological_parent"
    partner_relationship_type: str = "spouse"
    relationship_mode: str = "narrative"
    privacy_scope: str = "household_private"
    identity_matching_consent: bool = False
    account_required: bool = False
    invite_email: str | None = Field(default=None, max_length=320)
    account_member_role: Literal["viewer", "contributor"] = "viewer"
    is_deceased: bool = False
    bio: str | None = Field(default=None, max_length=5000)

    @field_validator("invite_email")
    @classmethod
    def _normalize_invite_email(cls, value: str | None) -> str | None:
        normalized = str(value or "").strip().lower()
        if not normalized:
            return None
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("invite_email must be a valid email address")
        return normalized


class FamilyMemberUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    middle_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    birth_year: int | None = Field(default=None, ge=1000, le=2200)
    birth_date: str | None = Field(default=None, max_length=50)
    generation: int | None = Field(default=None, ge=0)
    generation_locked: bool | None = None
    identity_matching_consent: bool | None = None
    account_required: bool | None = None
    invite_email: str | None = Field(default=None, max_length=320)
    account_member_role: Literal["viewer", "contributor"] | None = None
    is_deceased: bool | None = None
    bio: str | None = Field(default=None, max_length=5000)

    @field_validator("invite_email")
    @classmethod
    def _normalize_invite_email(cls, value: str | None) -> str | None:
        normalized = str(value or "").strip().lower()
        if not normalized:
            return None
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("invite_email must be a valid email address")
        return normalized


class FamilyMemberResponse(BaseModel):
    id: str
    family_id: str
    first_name: str
    last_name: str
    birth_year: int | None = None
    generation: int = 0
    father_id: str | None = None
    mother_id: str | None = None
    spouse_id: str | None = None
    bio: str | None = None
    created_at: str


def build_family_member_response(data: dict) -> FamilyMemberResponse:
    return FamilyMemberResponse(
        id=str(data.get("_id", "")),
        family_id=data["family_id"],
        first_name=data["first_name"],
        last_name=data["last_name"],
        birth_year=data.get("birth_year"),
        generation=data["generation"],
        father_id=data.get("father_id"),
        mother_id=data.get("mother_id"),
        spouse_id=data.get("spouse_id"),
        bio=data.get("bio"),
        created_at=data.get("created_at", datetime.now(UTC).isoformat()),
    )
