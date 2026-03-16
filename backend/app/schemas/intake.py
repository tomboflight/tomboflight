from datetime import datetime, UTC
from pydantic import BaseModel, EmailStr, Field


class IntakeCreate(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=150)
    email: EmailStr
    package_interest: str = Field(..., min_length=1, max_length=100)
    family_goal: str = Field(..., min_length=1, max_length=1000)


class IntakeResponse(BaseModel):
    id: str
    full_name: str
    email: EmailStr
    package_interest: str
    family_goal: str
    created_at: str


def build_intake_response(data: dict) -> IntakeResponse:
    return IntakeResponse(
        id=str(data.get("_id", "")),
        full_name=data["full_name"],
        email=data["email"],
        package_interest=data["package_interest"],
        family_goal=data["family_goal"],
        created_at=data.get("created_at", datetime.now(UTC).isoformat()),
    )
