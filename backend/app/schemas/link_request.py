from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class LinkRequestCreate(BaseModel):
    source_project_id: str = Field(..., min_length=1)
    target_key: str = Field(..., min_length=1, max_length=150)
    notes: str | None = Field(default=None, max_length=1000)


class LinkRequestResponse(BaseModel):
    id: str
    source_project_id: str
    target_project_id: str
    source_household_id: str | None = None
    target_household_id: str | None = None
    source_key: str
    target_key: str
    status: str
    requested_by: str
    requested_by_user_id: str | None = None
    source_package_code: str | None = None
    source_package_name: str | None = None
    source_project_name: str | None = None
    source_owner_email: str | None = None
    target_package_code: str | None = None
    target_package_name: str | None = None
    target_project_name: str | None = None
    target_owner_email: str | None = None
    notes: str | None = None
    handshake_state: str | None = None
    source_handshake_at: str | None = None
    source_handshake_by: str | None = None
    source_handshake_user_id: str | None = None
    target_handshake_at: str | None = None
    target_handshake_by: str | None = None
    target_handshake_user_id: str | None = None
    handshake_completed_at: str | None = None
    approved_by: str | None = None
    approved_at: str | None = None
    approval_notes: str | None = None
    rejected_by: str | None = None
    rejected_at: str | None = None
    rejection_notes: str | None = None
    revoked_by: str | None = None
    revoked_at: str | None = None
    revoke_notes: str | None = None
    created_at: str
    updated_at: str | None = None


def build_link_request_response(data: dict[str, Any]) -> LinkRequestResponse:
    return LinkRequestResponse(
        id=str(data.get("_id", "")),
        source_project_id=str(data.get("source_project_id") or ""),
        target_project_id=str(data.get("target_project_id") or ""),
        source_household_id=(
            str(data.get("source_household_id"))
            if data.get("source_household_id") is not None
            and str(data.get("source_household_id")).strip()
            else None
        ),
        target_household_id=(
            str(data.get("target_household_id"))
            if data.get("target_household_id") is not None
            and str(data.get("target_household_id")).strip()
            else None
        ),
        source_key=str(data.get("source_key") or ""),
        target_key=str(data.get("target_key") or ""),
        status=str(data.get("status") or "pending"),
        requested_by=str(data.get("requested_by") or ""),
        requested_by_user_id=(
            str(data.get("requested_by_user_id"))
            if data.get("requested_by_user_id") is not None
            else None
        ),
        source_package_code=(
            str(data.get("source_package_code"))
            if data.get("source_package_code")
            else None
        ),
        source_package_name=(
            str(data.get("source_package_name"))
            if data.get("source_package_name")
            else None
        ),
        source_project_name=(
            str(data.get("source_project_name"))
            if data.get("source_project_name")
            else None
        ),
        source_owner_email=(
            str(data.get("source_owner_email"))
            if data.get("source_owner_email")
            else None
        ),
        target_package_code=(
            str(data.get("target_package_code"))
            if data.get("target_package_code")
            else None
        ),
        target_package_name=(
            str(data.get("target_package_name"))
            if data.get("target_package_name")
            else None
        ),
        target_project_name=(
            str(data.get("target_project_name"))
            if data.get("target_project_name")
            else None
        ),
        target_owner_email=(
            str(data.get("target_owner_email"))
            if data.get("target_owner_email")
            else None
        ),
        notes=data.get("notes"),
        handshake_state=(
            str(data.get("handshake_state"))
            if data.get("handshake_state")
            else None
        ),
        source_handshake_at=data.get("source_handshake_at"),
        source_handshake_by=data.get("source_handshake_by"),
        source_handshake_user_id=(
            str(data.get("source_handshake_user_id"))
            if data.get("source_handshake_user_id") is not None
            else None
        ),
        target_handshake_at=data.get("target_handshake_at"),
        target_handshake_by=data.get("target_handshake_by"),
        target_handshake_user_id=(
            str(data.get("target_handshake_user_id"))
            if data.get("target_handshake_user_id") is not None
            else None
        ),
        handshake_completed_at=data.get("handshake_completed_at"),
        approved_by=data.get("approved_by"),
        approved_at=data.get("approved_at"),
        approval_notes=data.get("approval_notes"),
        rejected_by=data.get("rejected_by"),
        rejected_at=data.get("rejected_at"),
        rejection_notes=data.get("rejection_notes"),
        revoked_by=data.get("revoked_by"),
        revoked_at=data.get("revoked_at"),
        revoke_notes=data.get("revoke_notes"),
        created_at=str(data.get("created_at") or datetime.now(UTC).isoformat()),
        updated_at=(str(data.get("updated_at")) if data.get("updated_at") else None),
    )
