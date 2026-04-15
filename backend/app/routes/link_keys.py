from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.dependencies.auth import (
    get_current_user,
    has_internal_admin_access,
)
from app.schemas.link_key import LinkKeyResponse, build_link_key_response
from app.services.link_key_service import (
    generate_link_key,
    get_active_key_for_project,
    list_link_keys_for_user,
    revoke_link_key,
    user_can_access_project,
)

router = APIRouter(prefix="/link-keys", tags=["Link Keys"])


class LinkKeyGeneratePayload(BaseModel):
    key_type: str = Field(default="branch_link_key", min_length=1, max_length=50)
    target_email: str = Field(default="", max_length=320)
    allowed_role: str = Field(default="", max_length=50)
    max_uses: int = Field(default=1, ge=1, le=20)

def _current_user_id(user: dict[str, Any]) -> str:
    raw_id = user.get("id") or user.get("_id") or user.get("user_id")
    if raw_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user id is missing.",
        )
    return str(raw_id)


def _current_user_email(user: dict[str, Any]) -> str:
    return str(user.get("email") or "").strip().lower()


def _is_admin(user: dict[str, Any]) -> bool:
    return has_internal_admin_access(user)


@router.get("/my-list")
def list_my_link_keys(
    project_id: str | None = Query(default=None),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    user_email = _current_user_email(current_user)
    items = list_link_keys_for_user(
        user_id,
        user_email=user_email,
        project_id=project_id,
        include_revoked=True,
    )
    return {"items": [build_link_key_response(item) for item in items]}


@router.get("/my-active", response_model=LinkKeyResponse)
def get_my_active_link_key(
    project_id: str = Query(..., min_length=1),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    user_email = _current_user_email(current_user)
    allow_admin = _is_admin(current_user)

    if not allow_admin and not user_can_access_project(project_id, user_id, user_email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this project link key.",
        )

    item = get_active_key_for_project(project_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active link key found for this project.",
        )

    return build_link_key_response(item)


@router.post("/project/{project_id}/generate", response_model=LinkKeyResponse)
def generate_project_link_key(
    project_id: str,
    payload: LinkKeyGeneratePayload | None = None,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    user_email = _current_user_email(current_user)
    allow_admin = _is_admin(current_user)

    try:
        item = generate_link_key(
            project_id=project_id,
            user_id=user_id,
            user_email=user_email,
            allow_admin=allow_admin,
            key_type=(payload.key_type if payload else "branch_link_key"),
            target_email=(payload.target_email if payload else ""),
            allowed_role=(payload.allowed_role if payload else ""),
            max_uses=(payload.max_uses if payload else 1),
        )
        return build_link_key_response(item)
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


@router.post("/{key_id}/revoke", response_model=LinkKeyResponse)
def revoke_project_link_key(
    key_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    user_email = _current_user_email(current_user)
    allow_admin = _is_admin(current_user)

    try:
        item = revoke_link_key(
            key_id=key_id,
            actor_user_id=user_id,
            actor_user_email=user_email,
            allow_admin=allow_admin,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Link key not found.",
        )

    return build_link_key_response(item)
