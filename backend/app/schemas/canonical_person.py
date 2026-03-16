from datetime import UTC, datetime
from pydantic import BaseModel, Field


class CanonicalPersonCreate(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=150)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    birth_year: int | None = None
    status: str = Field(default="active", min_length=1, max_length=50)
    notes: str | None = None


class CanonicalPersonResponse(BaseModel):
    id: str
    display_name: str
    first_name: str
    last_name: str
    birth_year: int | None = None
    status: str
    notes: str | None = None
    created_at: str


def build_canonical_person_response(data: dict) -> CanonicalPersonResponse:
    return CanonicalPersonResponse(
        id=str(data.get("_id", "")),
        display_name=data["display_name"],
        first_name=data["first_name"],
        last_name=data["last_name"],
        birth_year=data.get("birth_year"),
        status=data.get("status", "active"),
        notes=data.get("notes"),
        created_at=data.get("created_at", datetime.now(UTC).isoformat()),
    )