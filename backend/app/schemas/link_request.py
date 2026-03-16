from datetime import UTC, datetime
from pydantic import BaseModel, Field


class LinkRequestCreate(BaseModel):
    source_household_id: str = Field(..., min_length=1)
    target_household_id: str = Field(..., min_length=1)
    source_key: str = Field(..., min_length=1, max_length=150)
    target_key: str = Field(..., min_length=1, max_length=150)
    status: str = Field(default="pending", min_length=1, max_length=50)
    requested_by: str = Field(..., min_length=1, max_length=150)
    notes: str | None = None


class LinkRequestResponse(BaseModel):
    id: str
    source_household_id: str
    target_household_id: str
    source_key: str
    target_key: str
    status: str
    requested_by: str
    notes: str | None = None
    approved_by: str | None = None
    approved_at: str | None = None
    rejected_by: str | None = None
    rejected_at: str | None = None
    created_at: str


def build_link_request_response(data: dict) -> LinkRequestResponse:
    return LinkRequestResponse(
        id=str(data.get("_id", "")),
        source_household_id=data["source_household_id"],
        target_household_id=data["target_household_id"],
        source_key=data["source_key"],
        target_key=data["target_key"],
        status=data.get("status", "pending"),
        requested_by=data["requested_by"],
        notes=data.get("notes"),
        approved_by=data.get("approved_by"),
        approved_at=data.get("approved_at"),
        rejected_by=data.get("rejected_by"),
        rejected_at=data.get("rejected_at"),
        created_at=data.get("created_at", datetime.now(UTC).isoformat()),
    )