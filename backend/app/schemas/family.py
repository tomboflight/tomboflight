from datetime import datetime, UTC
from pydantic import BaseModel, Field


class FamilyCreate(BaseModel):
    family_name: str = Field(..., min_length=1, max_length=150)
    created_by: str = Field(..., min_length=1)
    description: str | None = None


class FamilyResponse(BaseModel):
    id: str
    family_name: str
    created_by: str
    description: str | None = None
    created_at: str


def build_family_response(data: dict) -> FamilyResponse:
    return FamilyResponse(
        id=str(data.get("_id", "")),
        family_name=data["family_name"],
        created_by=data["created_by"],
        description=data.get("description"),
        created_at=data.get("created_at", datetime.now(UTC).isoformat()),
    )
