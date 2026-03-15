from datetime import UTC, datetime
from pydantic import BaseModel, Field


class HouseholdCreate(BaseModel):
    network_id: str | None = None
    household_name: str = Field(..., min_length=1, max_length=150)
    owner_user_id: str = Field(..., min_length=1)
    status: str = Field(default="active", min_length=1, max_length=50)


class HouseholdResponse(BaseModel):
    id: str
    network_id: str | None = None
    household_name: str
    owner_user_id: str
    household_key: str
    status: str
    created_at: str


def build_household_response(data: dict) -> HouseholdResponse:
    return HouseholdResponse(
        id=str(data.get("_id", "")),
        network_id=data.get("network_id"),
        household_name=data["household_name"],
        owner_user_id=data["owner_user_id"],
        household_key=data["household_key"],
        status=data.get("status", "active"),
        created_at=data.get("created_at", datetime.now(UTC).isoformat()),
    )