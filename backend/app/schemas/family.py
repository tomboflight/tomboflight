from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class FamilyCreate(BaseModel):
    family_name: str = Field(..., min_length=1, max_length=150)
    created_by: str = Field(..., min_length=1)
    description: str | None = None
    project_id: str | None = None


class FamilyResponse(BaseModel):
    id: str
    family_name: str
    created_by: str
    description: str | None = None
    created_at: datetime
    project_id: str | None = None
    owner_user_id: str | None = None
    owner_email: str | None = None
    visibility: str | None = None
    package_code: str | None = None
    package_name: str | None = None


def _to_string(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _to_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return datetime.now(UTC)

    return datetime.now(UTC)


def build_family_response(data: dict[str, Any]) -> FamilyResponse:
    family_name = _to_string(
        data.get("family_name") or data.get("name"),
        "Unnamed Family",
    )

    created_by = _to_string(
        data.get("created_by")
        or data.get("owner_email")
        or data.get("owner_user_id"),
        "Unknown",
    )

    return FamilyResponse(
        id=_to_string(data.get("_id")),
        family_name=family_name,
        created_by=created_by,
        description=data.get("description"),
        created_at=_to_datetime(data.get("created_at")),
        project_id=_to_string(data.get("project_id")) or None,
        owner_user_id=_to_string(data.get("owner_user_id")) or None,
        owner_email=_to_string(data.get("owner_email")).lower() or None,
        visibility=_to_string(data.get("visibility")) or None,
        package_code=_to_string(data.get("package_code")) or None,
        package_name=_to_string(data.get("package_name")) or None,
    )
