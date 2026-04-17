from datetime import datetime, timezone
from typing import Optional, Literal

from pydantic import BaseModel, Field, ConfigDict

from app.core.relationship_catalog import (
    ALLOWED_RELATIONSHIP_TYPES as CATALOG_ALLOWED_RELATIONSHIP_TYPES,
    RELATIONSHIP_TYPE_LITERAL_VALUES,
)

# Backward-compatible re-export for existing imports.
ALLOWED_RELATIONSHIP_TYPES = CATALOG_ALLOWED_RELATIONSHIP_TYPES


class RelationshipCreate(BaseModel):
    family_id: str = Field(..., min_length=1)
    source_member_id: str = Field(..., min_length=1)
    target_member_id: str = Field(..., min_length=1)
    relationship_type: Literal[*RELATIONSHIP_TYPE_LITERAL_VALUES]
    notes: Optional[str] = None
    created_by: Optional[str] = None


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
