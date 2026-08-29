from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies.auth import get_current_user
from app.schemas.legacy_message import LegacyMessageCreate, LegacyMessageUpdate
from app.services.legacy_message_service import (
    SCHEDULED_RELEASE_TRIGGERS,
    activate_legacy_message,
    create_legacy_message,
    delete_legacy_message,
    get_legacy_message,
    get_legacy_message_access_descriptor,
    list_legacy_messages,
    release_legacy_message,
    update_legacy_message,
)
from app.services.workspace_access_service import (
    require_workspace_capability,
    require_workspace_member_role,
)

router = APIRouter(prefix="/legacy-messages", tags=["Legacy Messages"])

LEGACY_MESSAGE_READ_ROLES = (
    "billing_owner",
    "co_owner",
    "family_manager",
    "contributor",
    "viewer",
)
LEGACY_MESSAGE_WRITE_ROLES = (
    "billing_owner",
    "co_owner",
    "family_manager",
    "contributor",
)


def _current_user_id(user: dict[str, Any]) -> str:
    raw_id = user.get("id") or user.get("_id") or user.get("user_id")
    normalized_user_id = str(raw_id or "").strip()
    if not normalized_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated user id is missing.",
        )
    return normalized_user_id


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _requires_scheduled_reveal(release_trigger: str) -> bool:
    normalized_trigger = _normalize(release_trigger).lower()
    # Unknown or missing trigger data is treated as scheduled so entitlement
    # drift and malformed legacy rows fail closed at the route boundary.
    return (
        normalized_trigger in SCHEDULED_RELEASE_TRIGGERS
        or normalized_trigger
        not in {
            "immediate",
            "manual",
        }
    )


def _resolve_legacy_message_context(
    current_user: dict[str, Any],
    *,
    project_id: str,
    scheduled_reveal: bool,
    write: bool,
) -> str:
    context = require_workspace_capability(
        current_user,
        project_id=project_id,
        capabilities=("can_use_future_message_vault",),
        detail="Your active package does not include future-message Vault access.",
    )

    if not context.get("is_admin"):
        entitlements = context.get("resolved_entitlements") or {}
        if not bool(entitlements.get("can_use_household_vault")):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your active package does not include household Vault access.",
            )
        if scheduled_reveal and not bool(entitlements.get("can_use_scheduled_reveal")):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your active package does not include scheduled message release.",
            )

    require_workspace_member_role(
        context,
        allowed_roles=(
            LEGACY_MESSAGE_WRITE_ROLES if write else LEGACY_MESSAGE_READ_ROLES
        ),
        detail=(
            "Your workspace role cannot manage legacy messages."
            if write
            else "Your workspace role cannot access legacy messages."
        ),
    )
    authorized_project_id = _normalize((context.get("project") or {}).get("_id"))
    if not authorized_project_id or authorized_project_id != _normalize(project_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Legacy message does not belong to the active workspace.",
        )
    return authorized_project_id


def _message_descriptor_or_404(message_id: str) -> dict[str, str]:
    descriptor = get_legacy_message_access_descriptor(message_id)
    if descriptor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Legacy message not found.",
        )
    return descriptor


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_legacy_message_route(
    payload: LegacyMessageCreate,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    authorized_project_id = _resolve_legacy_message_context(
        current_user,
        project_id=payload.project_id,
        scheduled_reveal=_requires_scheduled_reveal(payload.release_trigger),
        write=True,
    )
    try:
        return create_legacy_message(
            payload,
            user_id,
            authorized_project_id=authorized_project_id,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc


@router.get("/")
def list_legacy_messages_route(
    project_id: str = Query(...),
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    authorized_project_id = _resolve_legacy_message_context(
        current_user,
        project_id=project_id,
        scheduled_reveal=False,
        write=False,
    )
    try:
        items = list_legacy_messages(
            project_id,
            user_id,
            authorized_project_id=authorized_project_id,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    return {"items": items}


@router.get("/{message_id}")
def get_legacy_message_route(
    message_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    descriptor = _message_descriptor_or_404(message_id)
    authorized_project_id = _resolve_legacy_message_context(
        current_user,
        project_id=descriptor["project_id"],
        scheduled_reveal=_requires_scheduled_reveal(descriptor["release_trigger"]),
        write=False,
    )
    try:
        msg = get_legacy_message(
            message_id,
            user_id,
            authorized_project_id=authorized_project_id,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc

    if msg is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Legacy message not found."
        )
    return msg


@router.patch("/{message_id}")
def update_legacy_message_route(
    message_id: str,
    payload: LegacyMessageUpdate,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    descriptor = _message_descriptor_or_404(message_id)
    effective_trigger = payload.release_trigger or descriptor["release_trigger"]
    authorized_project_id = _resolve_legacy_message_context(
        current_user,
        project_id=descriptor["project_id"],
        scheduled_reveal=(
            _requires_scheduled_reveal(descriptor["release_trigger"])
            or _requires_scheduled_reveal(effective_trigger)
        ),
        write=True,
    )
    try:
        updated = update_legacy_message(
            message_id,
            payload,
            user_id,
            authorized_project_id=authorized_project_id,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Legacy message not found."
        )
    return updated


@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_legacy_message_route(
    message_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    descriptor = _message_descriptor_or_404(message_id)
    authorized_project_id = _resolve_legacy_message_context(
        current_user,
        project_id=descriptor["project_id"],
        scheduled_reveal=_requires_scheduled_reveal(descriptor["release_trigger"]),
        write=True,
    )
    try:
        delete_legacy_message(
            message_id,
            user_id,
            authorized_project_id=authorized_project_id,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.post("/{message_id}/activate")
def activate_legacy_message_route(
    message_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    descriptor = _message_descriptor_or_404(message_id)
    authorized_project_id = _resolve_legacy_message_context(
        current_user,
        project_id=descriptor["project_id"],
        scheduled_reveal=_requires_scheduled_reveal(descriptor["release_trigger"]),
        write=True,
    )
    try:
        updated = activate_legacy_message(
            message_id,
            user_id,
            authorized_project_id=authorized_project_id,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Legacy message not found."
        )
    return updated


@router.post("/{message_id}/release")
def release_legacy_message_route(
    message_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
):
    user_id = _current_user_id(current_user)
    descriptor = _message_descriptor_or_404(message_id)
    authorized_project_id = _resolve_legacy_message_context(
        current_user,
        project_id=descriptor["project_id"],
        scheduled_reveal=_requires_scheduled_reveal(descriptor["release_trigger"]),
        write=True,
    )
    try:
        released = release_legacy_message(
            message_id,
            user_id,
            authorized_project_id=authorized_project_id,
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    if released is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Legacy message not found."
        )
    return released
