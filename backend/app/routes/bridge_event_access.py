from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, EmailStr, Field

from app.config import settings
from app.dependencies.auth import require_super_admin
from app.services.bridge_event_access_service import (
    create_bridge_paint_invitation,
    list_bridge_paint_invitations,
    request_bridge_paint_access,
    revoke_bridge_paint_invitation,
)
from app.services.rate_limit_service import enforce_rate_limit


router = APIRouter(prefix="/bridge-events/paint", tags=["Private Bridge Event"])


class BridgePaintAccessRequest(BaseModel):
    email: EmailStr
    access_token: str = Field(min_length=24, max_length=256)


class BridgePaintInvitationCreate(BaseModel):
    email: EmailStr
    package_code: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=3, max_length=500)
    confirmed: bool = False


class BridgePaintInvitationRevoke(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
    confirmed: bool = False


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"


def _client_host(request: Request) -> str:
    client_host = str((request.client.host if request.client else "") or "").strip()
    return client_host or "unknown"


def _request_key(request: Request, principal: str) -> str:
    return f"{_client_host(request)}:{str(principal or '').strip().lower()}"


@router.post("/access/request")
def bridge_paint_access_request_route(
    payload: BridgePaintAccessRequest,
    request: Request,
    response: Response,
):
    _no_store(response)
    enforce_rate_limit(
        scope="bridge_paint_access_request",
        key=_request_key(request, str(payload.email)),
        limit=max(1, int(settings.bridge_paint_access_rate_limit or 5)),
        window_seconds=max(1, int(settings.auth_rate_limit_window_seconds or 60)),
    )
    enforce_rate_limit(
        scope="bridge_paint_access_request_ip",
        key=_client_host(request),
        limit=max(10, int(settings.bridge_paint_access_rate_limit or 5) * 4),
        window_seconds=max(1, int(settings.auth_rate_limit_window_seconds or 60)),
    )
    try:
        return request_bridge_paint_access(
            email=str(payload.email),
            access_token=payload.access_token,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Secure event access is temporarily unavailable.",
        ) from exc


@router.get("/invitations")
def list_bridge_paint_invitations_route(
    response: Response,
    limit: int = Query(default=100, ge=1, le=500),
    current_user: dict[str, Any] = Depends(require_super_admin),
):
    del current_user
    _no_store(response)
    try:
        return list_bridge_paint_invitations(limit=limit)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.post("/invitations", status_code=status.HTTP_201_CREATED)
def create_bridge_paint_invitation_route(
    payload: BridgePaintInvitationCreate,
    response: Response,
    current_user: dict[str, Any] = Depends(require_super_admin),
):
    _no_store(response)
    if not payload.confirmed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Confirm the invited recipient and selected package before sending.",
        )
    try:
        result = create_bridge_paint_invitation(
            current_user=current_user,
            email=str(payload.email),
            package_code=payload.package_code,
            reason=payload.reason,
        )
        if not bool(result.get("invitation_created", True)):
            response.status_code = status.HTTP_200_OK
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.post("/invitations/{invitation_id}/revoke")
def revoke_bridge_paint_invitation_route(
    invitation_id: str,
    payload: BridgePaintInvitationRevoke,
    response: Response,
    current_user: dict[str, Any] = Depends(require_super_admin),
):
    _no_store(response)
    if not payload.confirmed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Confirm revocation before continuing.",
        )
    try:
        return revoke_bridge_paint_invitation(
            invitation_id=invitation_id,
            current_user=current_user,
            reason=payload.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
