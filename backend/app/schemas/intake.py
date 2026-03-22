from datetime import UTC, datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field


class IntakeCreate(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=150)
    email: EmailStr
    package_interest: str = Field(..., min_length=1, max_length=100)
    family_goal: str = Field(..., min_length=1, max_length=1000)


class IntakeResponse(BaseModel):
    id: str
    full_name: str | None = None
    email: EmailStr | None = None
    package_interest: str | None = None
    family_goal: str | None = None
    package_name: str | None = None
    package_slug: str | None = None
    status: str | None = None
    source: str | None = None
    created_at: str
    submitted_at: str | None = None


def build_intake_response(data: dict[str, Any]) -> IntakeResponse:
    legacy_request = data.get("legacy_request") or {}

    full_name = data.get("full_name") or legacy_request.get("full_name")
    email = data.get("email") or legacy_request.get("email")
    package_interest = data.get("package_interest") or legacy_request.get("package_interest")
    family_goal = data.get("family_goal") or legacy_request.get("family_goal")

    package_name = data.get("package_name")
    package_slug = data.get("package_slug")
    status = data.get("status")
    source = data.get("source")
    submitted_at = data.get("submitted_at")

    created_at = data.get("created_at")
    if isinstance(created_at, datetime):
      created_at = created_at.isoformat()
    if not created_at:
      created_at = datetime.now(UTC).isoformat()

    if isinstance(submitted_at, datetime):
      submitted_at = submitted_at.isoformat()

    return IntakeResponse(
      id=str(data.get("_id", data.get("id", ""))),
      full_name=full_name,
      email=email,
      package_interest=package_interest,
      family_goal=family_goal,
      package_name=package_name,
      package_slug=package_slug,
      status=status,
      source=source,
      created_at=created_at,
      submitted_at=submitted_at,
    )