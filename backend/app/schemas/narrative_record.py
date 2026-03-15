from datetime import UTC, datetime
from pydantic import BaseModel, Field


class NarrativeRecordCreate(BaseModel):
    relationship_id: str | None = None
    canonical_person_id: str | None = None
    story_title: str = Field(..., min_length=1, max_length=150)
    story_text: str = Field(..., min_length=1, max_length=5000)
    submitted_by: str = Field(..., min_length=1, max_length=150)
    visibility: str = Field(default="family_only", min_length=1, max_length=50)


class NarrativeRecordResponse(BaseModel):
    id: str
    relationship_id: str | None = None
    canonical_person_id: str | None = None
    story_title: str
    story_text: str
    submitted_by: str
    visibility: str
    created_at: str


def build_narrative_record_response(data: dict) -> NarrativeRecordResponse:
    return NarrativeRecordResponse(
        id=str(data.get("_id", "")),
        relationship_id=data.get("relationship_id"),
        canonical_person_id=data.get("canonical_person_id"),
        story_title=data["story_title"],
        story_text=data["story_text"],
        submitted_by=data["submitted_by"],
        visibility=data.get("visibility", "family_only"),
        created_at=data.get("created_at", datetime.now(UTC).isoformat()),
    )