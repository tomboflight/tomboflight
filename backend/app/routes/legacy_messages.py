from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies.auth import get_current_user
from app.schemas.legacy_message import LegacyMessageCreate, LegacyMessageUpdate
from app.services.legacy_message_service import (
    activate_legacy_message,
    create_legacy_message,
    delete_legacy_message,
    get_legacy_message,
    list_legacy_messages,
    update_legacy_message,
)

router = APIRouter(prefix="/legacy-messages", tags=["Legacy Messages"])


def _current_user_id(user: dict[str, Any]) -> str:
    raw_id = user.get("id") or user.get("_id") or user.get("user_id")
    if raw_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user id is missing.",
        )
    return str(raw_id)


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_legacy_message_route(
    payload: LegacyMessageCreate,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    return create_legacy_message(payload, user_id)


@router.get("/")
def list_legacy_messages_route(
    project_id: str = Query(...),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    return {"items": list_legacy_messages(project_id, user_id)}


@router.get("/{message_id}")
def get_legacy_message_route(
    message_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    try:
        msg = get_legacy_message(message_id, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    if msg is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Legacy message not found.")
    return msg


@router.patch("/{message_id}")
def update_legacy_message_route(
    message_id: str,
    payload: LegacyMessageUpdate,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    try:
        updated = update_legacy_message(message_id, payload, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Legacy message not found.")
    return updated


@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_legacy_message_route(
    message_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    try:
        delete_legacy_message(message_id, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{message_id}/activate")
def activate_legacy_message_route(
    message_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    try:
        updated = activate_legacy_message(message_id, user_id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Legacy message not found.")
    return updated
