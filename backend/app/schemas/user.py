from datetime import datetime, UTC
from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    role: str = "client"


class UserResponse(BaseModel):
    id: str
    first_name: str
    last_name: str
    email: EmailStr
    role: str
    created_at: str


def build_user_response(data: dict) -> UserResponse:
    return UserResponse(
        id=str(data.get("_id", "")),
        first_name=data["first_name"],
        last_name=data["last_name"],
        email=data["email"],
        role=data.get("role", "client"),
        created_at=data.get("created_at", datetime.now(UTC).isoformat()),
    )
