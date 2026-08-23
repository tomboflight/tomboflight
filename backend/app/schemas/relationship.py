from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.relationship_catalog import (
    ALLOWED_RELATIONSHIP_MODES,
    ALLOWED_RELATIONSHIP_PRIVACY_SCOPES,
    ALLOWED_RELATIONSHIP_STATUS_MARKERS,
    ALLOWED_RELATIONSHIP_TYPES,
    ALLOWED_RELATIONSHIP_TYPE_SET,
    normalize_relationship_type,
)


class RelationshipCreate(BaseModel):
    family_id: str = Field(..., min_length=1)
    source_member_id: str = Field(..., min_length=1)
    target_member_id: str = Field(..., min_length=1)
    relationship_type: str = Field(..., min_length=1)
    relationship_mode: Literal["verified", "narrative"] = "narrative"
    status_marker: Literal[
        "verified", "narrative", "pending", "disputed", "unknown"
    ] = "narrative"
    privacy_scope: Literal[
        "private_to_owner",
        "private_to_owner_and_co_owner",
        "household_private",
        "branch_shared",
        "linked_family_shared",
        "public_memorial",
        "minor_protected",
    ] = "household_private"
    relationship_label: Optional[str] = Field(default=None, max_length=100)
    evidence_record_ids: list[str] = Field(default_factory=list, max_length=25)
    valid_from: Optional[str] = Field(default=None, max_length=50)
    valid_to: Optional[str] = Field(default=None, max_length=50)
    notes: Optional[str] = None
    created_by: Optional[str] = None

    @field_validator("relationship_type")
    @classmethod
    def _normalize_relationship_type(cls, value: str) -> str:
        normalized = normalize_relationship_type(value)
        if normalized not in ALLOWED_RELATIONSHIP_TYPE_SET:
            raise ValueError(
                f"relationship_type must be one of {sorted(ALLOWED_RELATIONSHIP_TYPES)}"
            )
        return normalized

    @field_validator("relationship_mode")
    @classmethod
    def _validate_relationship_mode(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in ALLOWED_RELATIONSHIP_MODES:
            raise ValueError("relationship_mode must be verified or narrative")
        return normalized

    @field_validator("status_marker")
    @classmethod
    def _validate_status_marker(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in ALLOWED_RELATIONSHIP_STATUS_MARKERS:
            raise ValueError("Invalid relationship status marker")
        return normalized

    @field_validator("privacy_scope")
    @classmethod
    def _validate_privacy_scope(cls, value: str) -> str:
        normalized = str(value or "").strip().lower()
        if normalized not in ALLOWED_RELATIONSHIP_PRIVACY_SCOPES:
            raise ValueError("Invalid relationship privacy scope")
        return normalized


class RelationshipInDB(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = Field(default=None, alias="_id")
    family_id: str
    source_member_id: str
    target_member_id: str
    relationship_type: str
    relationship_mode: str = "narrative"
    status_marker: str = "narrative"
    privacy_scope: str = "household_private"
    relationship_label: Optional[str] = None
    evidence_record_ids: list[str] = Field(default_factory=list)
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    notes: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RelationshipResponse(BaseModel):
    id: str
    family_id: str
    source_member_id: str
    target_member_id: str
    relationship_type: str
    relationship_mode: str = "narrative"
    status_marker: str = "narrative"
    privacy_scope: str = "household_private"
    relationship_label: Optional[str] = None
    evidence_record_ids: list[str] = Field(default_factory=list)
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    notes: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime
