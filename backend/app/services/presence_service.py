from __future__ import annotations

from typing import Any

from fastapi import HTTPException, WebSocket, status

from app.core.security import decode_access_token
from app.core.websocket_manager import websocket_manager
from app.dependencies.auth import COOKIE_NAME
from app.services.auth_service import get_user_by_email
from app.services.workspace_access_service import resolve_workspace_context


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _current_user_id(user: dict[str, Any]) -> str:
    return _normalize(user.get("id") or user.get("_id") or user.get("user_id"))


def _room_name(channel_type: str, channel_id: str = "") -> str:
    normalized_id = _normalize(channel_id)
    return f"{channel_type}:{normalized_id}" if normalized_id else channel_type


def websocket_paths() -> list[str]:
    return ["/ws/experience", "/ws/family/{family_id}", "/ws/project/{project_id}"]


def build_presence_status() -> dict[str, Any]:
    channels = websocket_manager.snapshot()
    return {
        "status": "live",
        "active_connections": websocket_manager.total_connections(),
        "channels": channels,
        "websocket_paths": websocket_paths(),
    }


def build_presence_overview(*, project_id: str = "", family_id: str = "") -> dict[str, Any]:
    snapshot = build_presence_status()
    room_counts = snapshot["channels"]
    return {
        "status": snapshot["status"],
        "active_connections": room_counts.get(_room_name("project", project_id), 0)
        + room_counts.get(_room_name("family", family_id), 0)
        + room_counts.get("experience", 0),
        "project_channel": _room_name("project", project_id) if project_id else None,
        "family_channel": _room_name("family", family_id) if family_id else None,
        "experience_channel": "experience",
        "websocket_paths": websocket_paths(),
    }


def authenticate_presence_user(token: str) -> dict[str, Any]:
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid websocket token.")

    email = _normalize(payload.get("sub") or payload.get("email")).lower()
    user = get_user_by_email(email) if email else None
    if user is None:
        user = {
            "id": _normalize(payload.get("user_id") or payload.get("id")),
            "user_id": _normalize(payload.get("user_id") or payload.get("id")),
            "email": email,
            "role": _normalize(payload.get("role")) or "user",
            "status": "active",
        }
    return user


def authenticate_presence_websocket(websocket: WebSocket) -> dict[str, Any]:
    token = _normalize(websocket.query_params.get("token") or websocket.cookies.get(COOKIE_NAME))
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Websocket authentication token is required.")
    return authenticate_presence_user(token)


def ensure_presence_scope(
    current_user: dict[str, Any],
    *,
    project_id: str = "",
    family_id: str = "",
) -> None:
    if project_id:
        resolve_workspace_context(current_user, project_id=project_id)
    elif family_id:
        resolve_workspace_context(current_user, family_id=family_id)


async def connect_presence_channel(websocket: WebSocket, room: str, payload: dict[str, Any]) -> None:
    await websocket_manager.connect(room, websocket)
    await websocket_manager.send_json(websocket, payload)


async def disconnect_presence_channel(websocket: WebSocket, room: str) -> None:
    await websocket_manager.disconnect(room, websocket)


async def broadcast_presence_event(room: str, payload: dict[str, Any]) -> None:
    await websocket_manager.broadcast(room, payload)
