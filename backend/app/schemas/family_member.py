from datetime import datetime, UTC
from pydantic import BaseModel, Field


class FamilyMemberCreate(BaseModel):
    family_id: str = Field(..., min_length=1)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    birth_year: int | None = None
    generation: int = Field(..., ge=0)
    father_id: str | None = None
    mother_id: str | None = None
    spouse_id: str | None = None
    bio: str | None = None


class FamilyMemberResponse(BaseModel):
    id: str
    family_id: str
    first_name: str
    last_name: str
    birth_year: int | None = None
    generation: int
    father_id: str | None = None
    mother_id: str | None = None
    spouse_id: str | None = None
    bio: str | None = None
    created_at: str


def build_family_member_response(data: dict) -> FamilyMemberResponse:
    return FamilyMemberResponse(
        id=str(data.get("_id", "")),
        family_id=data["family_id"],
        first_name=data["first_name"],
        last_name=data["last_name"],
        birth_year=data.get("birth_year"),
        generation=data["generation"],
        father_id=data.get("father_id"),
        mother_id=data.get("mother_id"),
        spouse_id=data.get("spouse_id"),
        bio=data.get("bio"),
        created_at=data.get("created_at", datetime.now(UTC).isoformat()),
    )
