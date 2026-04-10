from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.dependencies.auth import get_current_user, require_permission
from app.schemas.link_request import (
    LinkRequestCreate,
    LinkRequestResponse,
    build_link_request_response,
)
from app.services.link_request_service import (
    approve_link_request,
    create_link_request,
    list_link_requests,
    list_link_requests_for_user,
    reject_link_request,
    revoke_link_request,
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
        str(user.get("full_name") or user.get("name") or user.get("email") or "").strip()
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
    current_user: dict[str, Any] = Depends(require_permission("admin.access")),
):
    requests = list_link_requests()
    return [build_link_request_response(item) for item in requests]


@router.get("/my-list")
def get_my_link_requests(
    project_id: str | None = Query(default=None),
    direction: str = Query(default="all"),
    status_value: str | None = Query(default=None, alias="status"),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    items = list_link_requests_for_user(
        user_id,
        project_id=project_id,
        direction=direction,
        status=status_value,
    )
    return {"items": [build_link_request_response(item) for item in items]}


@router.post("/", response_model=LinkRequestResponse, status_code=status.HTTP_201_CREATED)
def create_link_request_route(
    payload: LinkRequestCreate,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    try:
        request = create_link_request(
            payload,
            requested_by=_current_user_display(current_user),
            requested_by_user_id=_current_user_id(current_user),
        )
        return build_link_request_response(request)
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/{request_id}/approve", response_model=LinkRequestResponse)
def approve_link_request_route(
    request_id: str,
    payload: LinkRequestDecision | None = None,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    try:
        updated_request = approve_link_request(
            request_id,
            approved_by=_current_user_display(current_user),
            approver_user_id=_current_user_id(current_user),
            approval_notes=(payload.notes if payload else None),
            is_admin=_is_admin(current_user),
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if updated_request is None:
        raise HTTPException(status_code=404, detail="Link request not found.")

    return build_link_request_response(updated_request)


@router.post("/{request_id}/reject", response_model=LinkRequestResponse)
def reject_link_request_route(
    request_id: str,
    payload: LinkRequestDecision | None = None,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    try:
        updated_request = reject_link_request(
            request_id,
            rejected_by=_current_user_display(current_user),
            rejector_user_id=_current_user_id(current_user),
            rejection_notes=(payload.notes if payload else None),
            is_admin=_is_admin(current_user),
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if updated_request is None:
        raise HTTPException(status_code=404, detail="Link request not found.")

    return build_link_request_response(updated_request)


@router.post("/{request_id}/revoke", response_model=LinkRequestResponse)
def revoke_link_request_route(
    request_id: str,
    payload: LinkRequestDecision | None = None,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    try:
        updated_request = revoke_link_request(
            request_id,
            revoked_by=_current_user_display(current_user),
            revoker_user_id=_current_user_id(current_user),
            revoke_notes=(payload.notes if payload else None),
            is_admin=_is_admin(current_user),
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if updated_request is None:
        raise HTTPException(status_code=404, detail="Link request not found.")

    return build_link_request_response(updated_request)