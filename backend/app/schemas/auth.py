from typing import Optional

from pydantic import BaseModel, EmailStr, Field

POLICY_VERSION_DEFAULT = "2026-03-26"


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=12, max_length=128)
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


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str = Field(..., min_length=16, max_length=512)
    new_password: str = Field(..., min_length=12, max_length=128)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=8, max_length=128)
    new_password: str = Field(..., min_length=12, max_length=128)
    confirm_new_password: str = Field(..., min_length=12, max_length=128)


class PasswordResetResponse(BaseModel):
    success: bool = True
    message: str
    expires_at: Optional[str] = None
    reset_token: Optional[str] = None
    reset_url: Optional[str] = None
    delivery_mode: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    csrf_token: Optional[str] = None
    mfa_required: bool = False
    mfa_enrollment_required: bool = False
    mfa_challenge_token: Optional[str] = None
    backup_codes: list[str] = Field(default_factory=list)


class MfaEnrollmentBeginRequest(BaseModel):
    mfa_challenge_token: str = Field(..., min_length=8, max_length=2048)


class MfaEnrollmentBeginResponse(BaseModel):
    setup_token: str
    secret: str
    otpauth_url: str


class MfaEnrollmentVerifyRequest(BaseModel):
    setup_token: str = Field(..., min_length=8, max_length=2048)
    code: str = Field(..., min_length=6, max_length=12)


class MfaLoginVerifyRequest(BaseModel):
    mfa_challenge_token: str = Field(..., min_length=8, max_length=2048)
    code: Optional[str] = Field(default=None, min_length=6, max_length=12)
    recovery_code: Optional[str] = Field(default=None, min_length=6, max_length=64)


class MfaDisableRequest(BaseModel):
    current_password: str = Field(..., min_length=8, max_length=128)
    code: Optional[str] = Field(default=None, min_length=6, max_length=12)
    recovery_code: Optional[str] = Field(default=None, min_length=6, max_length=64)


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: str
    account_type: Optional[str] = None
    business_title: Optional[str] = None
    prototype_key: Optional[str] = None
    creator_credit: Optional[str] = None
    access_tier: Optional[str] = None
    department_role: Optional[str] = None
    status: str
    mfa_enabled: bool = False
    mfa_enrolled_at: Optional[str] = None
    created_at: str
    active_project_id: Optional[str] = None
    active_family_id: Optional[str] = None

    policy_version: Optional[str] = None
    terms_accepted_at: Optional[str] = None
    privacy_accepted_at: Optional[str] = None
    eligibility_attested_at: Optional[str] = None
