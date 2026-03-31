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
    email: str
    role: str
    created_at: str
    status: str | None = None
    full_name: str | None = None
    last_login_at: str | None = None
    password_reset_requested_at: str | None = None
    password_reset_expires_at: str | None = None


def _normalize_text(value: object) -> str:
    return str(value or "").strip()


def _split_display_name(data: dict) -> tuple[str, str]:
    first_name = _normalize_text(data.get("first_name"))
    last_name = _normalize_text(data.get("last_name"))
    if first_name or last_name:
        return first_name or "Unknown", last_name

    fallback_name = (
        _normalize_text(data.get("full_name"))
        or _normalize_text(data.get("name"))
        or _normalize_text(data.get("display_name"))
    )

    if not fallback_name:
        email_value = _normalize_text(data.get("email")).split("@")[0]
        fallback_name = email_value.replace(".", " ").replace("_", " ").strip()

    parts = [part for part in fallback_name.split() if part]
    if not parts:
        return "Unknown", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _serialize_created_at(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    normalized = _normalize_text(value)
    return normalized or datetime.now(UTC).isoformat()


def build_user_response(data: dict) -> UserResponse:
    first_name, last_name = _split_display_name(data)
    return UserResponse(
        id=str(data.get("_id", "")),
        first_name=first_name,
        last_name=last_name,
        email=_normalize_text(data.get("email")) or "—",
        role=_normalize_text(data.get("role")) or "client",
        created_at=_serialize_created_at(data.get("created_at")),
        status=_normalize_text(data.get("status")) or None,
        full_name=_normalize_text(data.get("full_name")) or None,
        last_login_at=_normalize_text(data.get("last_login_at")) or None,
        password_reset_requested_at=(
            _normalize_text(data.get("password_reset_requested_at")) or None
        ),
        password_reset_expires_at=(
            _normalize_text(data.get("password_reset_expires_at")) or None
        ),
    )
