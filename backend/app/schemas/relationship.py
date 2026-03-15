from datetime import UTC, datetime
from pydantic import BaseModel, Field


class RelationshipCreate(BaseModel):
    source_member_id: str = Field(..., min_length=1)
    target_member_id: str = Field(..., min_length=1)
    relationship_type: str = Field(..., min_length=1, max_length=100)
    relationship_mode: str = Field(..., min_length=1, max_length=50)
    status_marker: str = Field(..., min_length=1, max_length=50)
    notes: str | None = None


class RelationshipResponse(BaseModel):
    id: str
    source_member_id: str
    target_member_id: str
    relationship_type: str
    relationship_mode: str
    status_marker: str
    notes: str | None = None
    created_at: str


def build_relationship_response(data: dict) -> RelationshipResponse:
    return RelationshipResponse(
        id=str(data.get("_id", "")),
        source_member_id=data["source_member_id"],
        target_member_id=data["target_member_id"],
        relationship_type=data["relationship_type"],
        relationship_mode=data["relationship_mode"],
        status_marker=data["status_marker"],
        notes=data.get("notes"),
        created_at=data.get("created_at", datetime.now(UTC).isoformat()),
    )
