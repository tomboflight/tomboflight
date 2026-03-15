from datetime import UTC, datetime
from pydantic import BaseModel, Field


class HouseholdLinkCreate(BaseModel):
    source_household_id: str = Field(..., min_length=1)
    target_household_id: str = Field(..., min_length=1)
    relationship_type: str = Field(..., min_length=1, max_length=100)
    link_status: str = Field(default="pending", min_length=1, max_length=50)
    linked_by_key: str = Field(..., min_length=1, max_length=150)


class HouseholdLinkResponse(BaseModel):
    id: str
    source_household_id: str
    target_household_id: str
    relationship_type: str
    link_status: str
    linked_by_key: str
    created_at: str


def build_household_link_response(data: dict) -> HouseholdLinkResponse:
    return HouseholdLinkResponse(
        id=str(data.get("_id", "")),
        source_household_id=data["source_household_id"],
        target_household_id=data["target_household_id"],
        relationship_type=data["relationship_type"],
        link_status=data.get("link_status", "pending"),
        linked_by_key=data["linked_by_key"],
        created_at=data.get("created_at", datetime.now(UTC).isoformat()),
    )
