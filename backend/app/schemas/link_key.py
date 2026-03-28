from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel


class LinkKeyResponse(BaseModel):
    id: str
    project_id: str
    package_code: str | None = None
    package_name: str | None = None
    package_lane: str | None = None
    key_value: str
    status: str
    created_at: str
    updated_at: str | None = None
    revoked_at: str | None = None


def build_link_key_response(data: dict[str, Any]) -> LinkKeyResponse:
    return LinkKeyResponse(
        id=str(data.get("_id", "")),
        project_id=str(data.get("project_id") or ""),
        package_code=(str(data.get("package_code")) if data.get("package_code") else None),
        package_name=(str(data.get("package_name")) if data.get("package_name") else None),
        package_lane=(str(data.get("package_lane")) if data.get("package_lane") else None),
        key_value=str(data.get("key_value") or ""),
        status=str(data.get("status") or "active"),
        created_at=str(data.get("created_at") or datetime.now(UTC).isoformat()),
        updated_at=(str(data.get("updated_at")) if data.get("updated_at") else None),
        revoked_at=(str(data.get("revoked_at")) if data.get("revoked_at") else None),
    )