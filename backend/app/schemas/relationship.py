from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.relationship_catalog import (
    ALLOWED_RELATIONSHIP_TYPES,
    normalize_relationship_type,
)

ALLOWED_RELATIONSHIP_TYPE_SET = frozenset(ALLOWED_RELATIONSHIP_TYPES)


class RelationshipCreate(BaseModel):
    family_id: str = Field(..., min_length=1)
    source_member_id: str = Field(..., min_length=1)
    target_member_id: str = Field(..., min_length=1)
    relationship_type: str = Field(..., min_length=1)
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


class RelationshipInDB(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: Optional[str] = Field(default=None, alias="_id")
    family_id: str
    source_member_id: str
    target_member_id: str
    relationship_type: str
    notes: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RelationshipResponse(BaseModel):
    id: str
    family_id: str
    source_member_id: str
    target_member_id: str
    relationship_type: str
    notes: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime
