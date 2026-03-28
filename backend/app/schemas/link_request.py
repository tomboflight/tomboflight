from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class LinkRequestCreate(BaseModel):
    source_household_id: str = Field(..., min_length=1)
    target_household_id: str = Field(..., min_length=1)
    source_key: str = Field(..., min_length=1, max_length=150)
    target_key: str = Field(..., min_length=1, max_length=150)
    notes: str | None = Field(default=None, max_length=1000)


class LinkRequestResponse(BaseModel):
    id: str
    source_household_id: str
    target_household_id: str
    source_key: str
    target_key: str
    status: str
    requested_by: str
    requested_by_user_id: str | None = None
    notes: str | None = None
    approved_by: str | None = None
    approved_at: str | None = None
    approval_notes: str | None = None
    rejected_by: str | None = None
    rejected_at: str | None = None
    rejection_notes: str | None = None
    created_at: str


def build_link_request_response(data: dict[str, Any]) -> LinkRequestResponse:
    return LinkRequestResponse(
        id=str(data.get("_id", "")),
        source_household_id=str(data.get("source_household_id") or ""),
        target_household_id=str(data.get("target_household_id") or ""),
        source_key=str(data.get("source_key") or ""),
        target_key=str(data.get("target_key") or ""),
        status=str(data.get("status") or "pending"),
        requested_by=str(data.get("requested_by") or ""),
        requested_by_user_id=(
            str(data.get("requested_by_user_id"))
            if data.get("requested_by_user_id") is not None
            else None
        ),
        notes=data.get("notes"),
        approved_by=data.get("approved_by"),
        approved_at=data.get("approved_at"),
        approval_notes=data.get("approval_notes"),
        rejected_by=data.get("rejected_by"),
        rejected_at=data.get("rejected_at"),
        rejection_notes=data.get("rejection_notes"),
        created_at=str(data.get("created_at") or datetime.now(UTC).isoformat()),
    )