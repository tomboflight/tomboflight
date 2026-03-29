from typing import Optional

from pydantic import BaseModel, EmailStr, Field

POLICY_VERSION_DEFAULT = "2026-03-26"


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=150)

    terms_accepted: bool = Field(...)
    privacy_accepted: bool = Field(...)
    eligibility_attested: bool = Field(...)
    policy_version: str = Field(
        default=POLICY_VERSION_DEFAULT,
        min_length=1,
        max_length=32,
    )


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: str
    status: str
    created_at: str

    policy_version: Optional[str] = None
    terms_accepted_at: Optional[str] = None
    privacy_accepted_at: Optional[str] = None
    eligibility_attested_at: Optional[str] = None
