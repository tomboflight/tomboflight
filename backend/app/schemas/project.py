from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    project_lane: str = Field(..., min_length=1, max_length=50)
    owner_user_id: str = Field(..., min_length=1)
    owner_email: str = Field(..., min_length=1)
    package_code: str = Field(..., min_length=1, max_length=150)
    package_name: str = Field(..., min_length=1, max_length=150)
    status: str = Field(default="purchased", min_length=1, max_length=50)
    phase: str = Field(default="checkout_completed", min_length=1, max_length=100)
    source: str = Field(default="manual", min_length=1, max_length=100)
    family_id: str | None = None
    household_id: str | None = None
    organization_id: str | None = None
    intake_submission_id: str | None = None
    stripe_session_id: str | None = None
    stripe_payment_link_id: str | None = None
    notes: str = ""


class ProjectResponse(BaseModel):
    id: str
    name: str
    project_lane: str
    owner_user_id: str
    owner_email: str
    package_code: str
    package_name: str
    status: str
    phase: str
    source: str
    family_id: str | None = None
    household_id: str | None = None
    organization_id: str | None = None
    intake_submission_id: str | None = None
    stripe_session_id: str | None = None
    stripe_payment_link_id: str | None = None
    notes: str = ""
    created_at: str
    updated_at: str | None = None


def _as_string(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _as_datetime_string(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, str) and value.strip():
        return value.strip()

    return datetime.now(UTC).isoformat()


def build_project_response(data: dict[str, Any]) -> ProjectResponse:
    name = _as_string(data.get("name") or data.get("project_name"), "Unnamed Project")

    package_code = _as_string(
        data.get("package_code") or data.get("package_slug") or data.get("package_type"),
        "unknown",
    )

    project_lane = _as_string(data.get("project_lane"), "unknown")

    if not project_lane:
      project_lane = "unknown"

    return ProjectResponse(
        id=_as_string(data.get("_id")),
        name=name,
        project_lane=project_lane,
        owner_user_id=_as_string(data.get("owner_user_id")),
        owner_email=_as_string(data.get("owner_email")).lower(),
        package_code=package_code,
        package_name=_as_string(data.get("package_name"), "Tomb of Light Project"),
        status=_as_string(data.get("status"), "draft"),
        phase=_as_string(data.get("phase"), "created"),
        source=_as_string(data.get("source"), "manual"),
        family_id=_as_string(data.get("family_id")) or None,
        household_id=_as_string(data.get("household_id")) or None,
        organization_id=_as_string(data.get("organization_id")) or None,
        intake_submission_id=_as_string(data.get("intake_submission_id")) or None,
        stripe_session_id=_as_string(data.get("stripe_session_id")) or None,
        stripe_payment_link_id=_as_string(data.get("stripe_payment_link_id")) or None,
        notes=_as_string(data.get("notes")),
        created_at=_as_datetime_string(data.get("created_at")),
        updated_at=_as_datetime_string(data.get("updated_at")) if data.get("updated_at") else None,
    )