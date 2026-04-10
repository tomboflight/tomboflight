from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status

from app.dependencies.auth import get_current_user
from app.schemas.experience import PresenceStatusResponse
from app.services.presence_service import (
    WS_EXPERIENCE_PATH,
    WS_FAMILY_PATH,
    WS_PROJECT_PATH,
    authenticate_presence_websocket,
    build_presence_overview,
    build_presence_status,
    connect_presence_channel,
    disconnect_presence_channel,
    ensure_presence_scope,
)

router = APIRouter(tags=["Presence"])


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


@router.get("/presence/status", response_model=PresenceStatusResponse)
def get_presence_status_route(
    current_user: dict[str, Any] = Depends(get_current_user),
):
    del current_user
    return build_presence_status()


@router.websocket(WS_EXPERIENCE_PATH)
async def websocket_experience(websocket: WebSocket):
    try:
        current_user = authenticate_presence_websocket(websocket)
    except HTTPException:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    room = "experience"
    await connect_presence_channel(
        websocket,
        room,
        {
            "event": "presence.connected",
            "channel": room,
            "user_id": str(current_user.get("_id") or current_user.get("id") or current_user.get("user_id") or ""),
            "connected_at": _timestamp(),
        },
    )

    try:
        while True:
            client_message = await websocket.receive_text()
            await websocket.send_json({"event": "presence.heartbeat", "channel": room, "received": client_message, "timestamp": _timestamp()})
    except WebSocketDisconnect:
        await disconnect_presence_channel(websocket, room)


@router.websocket(WS_FAMILY_PATH)
async def websocket_family(websocket: WebSocket, family_id: str):
    try:
        current_user = authenticate_presence_websocket(websocket)
        ensure_presence_scope(current_user, family_id=family_id)
    except HTTPException:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    room = f"family:{family_id}"
    await connect_presence_channel(
        websocket,
        room,
        {
            "event": "presence.connected",
            "channel": room,
            "family_id": family_id,
            "presence": build_presence_overview(family_id=family_id),
            "connected_at": _timestamp(),
        },
    )

    try:
        while True:
            client_message = await websocket.receive_text()
            await websocket.send_json({"event": "presence.heartbeat", "channel": room, "received": client_message, "timestamp": _timestamp()})
    except WebSocketDisconnect:
        await disconnect_presence_channel(websocket, room)


@router.websocket(WS_PROJECT_PATH)
async def websocket_project(websocket: WebSocket, project_id: str):
    try:
        current_user = authenticate_presence_websocket(websocket)
        ensure_presence_scope(current_user, project_id=project_id)
    except HTTPException:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    room = f"project:{project_id}"
    await connect_presence_channel(
        websocket,
        room,
        {
            "event": "presence.connected",
            "channel": room,
            "project_id": project_id,
            "presence": build_presence_overview(project_id=project_id),
            "connected_at": _timestamp(),
        },
    )

    try:
        while True:
            client_message = await websocket.receive_text()
            await websocket.send_json({"event": "presence.heartbeat", "channel": room, "received": client_message, "timestamp": _timestamp()})
    except WebSocketDisconnect:
        await disconnect_presence_channel(websocket, room)
