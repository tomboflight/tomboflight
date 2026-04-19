from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel


class LinkKeyResponse(BaseModel):
    id: str
    key_type: str
    project_id: str
    package_code: str | None = None
    package_name: str | None = None
    package_lane: str | None = None
    key_value: str
    key_preview: str | None = None
    status: str
    created_at: str
    updated_at: str | None = None
    revoked_at: str | None = None
    expires_at: str | None = None
    expired_at: str | None = None
    issuer_user_id: str | None = None
    target_email: str | None = None
    allowed_role: str | None = None
    max_uses: int = 1
    use_count: int = 0


def build_link_key_response(data: dict[str, Any]) -> LinkKeyResponse:
    return LinkKeyResponse(
        id=str(data.get("_id", "")),
        key_type=str(data.get("key_type") or "branch_link_key"),
        project_id=str(data.get("project_id") or ""),
        package_code=(str(data.get("package_code")) if data.get("package_code") else None),
        package_name=(str(data.get("package_name")) if data.get("package_name") else None),
        package_lane=(str(data.get("package_lane")) if data.get("package_lane") else None),
        key_value=str(data.get("key_value") or ""),
        key_preview=(str(data.get("key_preview")) if data.get("key_preview") else None),
        status=str(data.get("status") or "active"),
        created_at=str(data.get("created_at") or datetime.now(UTC).isoformat()),
        updated_at=(str(data.get("updated_at")) if data.get("updated_at") else None),
        revoked_at=(str(data.get("revoked_at")) if data.get("revoked_at") else None),
        expires_at=(str(data.get("expires_at")) if data.get("expires_at") else None),
        expired_at=(str(data.get("expired_at")) if data.get("expired_at") else None),
        issuer_user_id=(str(data.get("issuer_user_id")) if data.get("issuer_user_id") else None),
        target_email=(str(data.get("target_email")) if data.get("target_email") else None),
        allowed_role=(str(data.get("allowed_role")) if data.get("allowed_role") else None),
        max_uses=int(data.get("max_uses") or 1),
        use_count=int(data.get("use_count") or 0),
    )
