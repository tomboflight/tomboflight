from datetime import UTC, datetime
from pydantic import BaseModel, Field


class FamilyNetworkCreate(BaseModel):
    network_name: str = Field(..., min_length=1, max_length=150)
    created_by: str = Field(..., min_length=1)
    description: str | None = None


class FamilyNetworkResponse(BaseModel):
    id: str
    network_name: str
    created_by: str
    network_key: str
    description: str | None = None
    created_at: str


def build_family_network_response(data: dict) -> FamilyNetworkResponse:
    return FamilyNetworkResponse(
        id=str(data.get("_id", "")),
        network_name=data["network_name"],
        created_by=data["created_by"],
        network_key=data["network_key"],
        description=data.get("description"),
        created_at=data.get("created_at", datetime.now(UTC).isoformat()),
    )