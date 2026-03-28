from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.dependencies.auth import get_current_user, require_admin
from app.schemas.link_request import (
    LinkRequestCreate,
    LinkRequestResponse,
    build_link_request_response,
)
from app.services.link_request_service import (
    approve_link_request,
    create_link_request,
    list_link_requests,
    reject_link_request,
)

router = APIRouter(prefix="/link-requests", tags=["Link Requests"])

INTERNAL_ADMIN_KEYS = {
    "admin",
    "super_admin",
    "root_admin",
    "platform_admin",
    "operations_admin",
    "finance_admin",
    "marketing_admin",
    "executive_technology",
    "operations",
    "finance",
    "marketing",
}


class LinkRequestDecision(BaseModel):
    notes: str | None = Field(default=None, max_length=1000)


def _current_user_id(user: dict[str, Any]) -> str:
    raw_id = user.get("id") or user.get("_id") or user.get("user_id")
    if raw_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user id is missing.",
        )
    return str(raw_id)


def _current_user_display(user: dict[str, Any]) -> str:
    return (
        str(user.get("full_name") or user.get("name") or user.get("email") or "")
        .strip()
        or "Unknown User"
    )


def _is_admin(user: dict[str, Any]) -> bool:
    role = str(user.get("role") or "").strip().lower()
    access_tier = str(user.get("access_tier") or "").strip().lower()
    department_role = str(user.get("department_role") or "").strip().lower()

    return any(
      value in INTERNAL_ADMIN_KEYS
      for value in (role, access_tier, department_role)
    )


@router.get("/", response_model=list[LinkRequestResponse])
def get_link_requests(
    current_user: dict[str, Any] = Depends(require_admin),
):
    requests = list_link_requests()
    return [build_link_request_response(item) for item in requests]


@router.post("/", response_model=LinkRequestResponse, status_code=status.HTTP_201_CREATED)
def create_link_request_route(
    payload: LinkRequestCreate,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    request = create_link_request(
        payload,
        requested_by=_current_user_display(current_user),
        requested_by_user_id=_current_user_id(current_user),
    )
    return build_link_request_response(request)


@router.post("/{request_id}/approve", response_model=LinkRequestResponse)
def approve_link_request_route(
    request_id: str,
    payload: LinkRequestDecision | None = None,
    current_user: dict[str, Any] = Depends(require_admin),
):
    updated_request = approve_link_request(
        request_id,
        approved_by=_current_user_display(current_user),
        approval_notes=(payload.notes if payload else None),
    )

    if updated_request is None:
        raise HTTPException(status_code=404, detail="Link request not found.")

    return build_link_request_response(updated_request)


@router.post("/{request_id}/reject", response_model=LinkRequestResponse)
def reject_link_request_route(
    request_id: str,
    payload: LinkRequestDecision | None = None,
    current_user: dict[str, Any] = Depends(require_admin),
):
    updated_request = reject_link_request(
        request_id,
        rejected_by=_current_user_display(current_user),
        rejection_notes=(payload.notes if payload else None),
    )

    if updated_request is None:
        raise HTTPException(status_code=404, detail="Link request not found.")

    return build_link_request_response(updated_request)