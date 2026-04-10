from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class WebSocketManager:
    def __init__(self) -> None:
        self._rooms: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, room: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._rooms[room].add(websocket)

    async def disconnect(self, room: str, websocket: WebSocket) -> None:
        async with self._lock:
            connections = self._rooms.get(room)
            if not connections:
                return
            connections.discard(websocket)
            if not connections:
                self._rooms.pop(room, None)

    async def send_json(self, websocket: WebSocket, payload: dict[str, Any]) -> None:
        await websocket.send_json(payload)

    async def broadcast(self, room: str, payload: dict[str, Any]) -> None:
        async with self._lock:
            connections = list(self._rooms.get(room, set()))

        stale: list[WebSocket] = []
        for websocket in connections:
            try:
                await websocket.send_json(payload)
            except Exception:
                stale.append(websocket)

        if stale:
            async with self._lock:
                active = self._rooms.get(room)
                if active is None:
                    return
                for websocket in stale:
                    active.discard(websocket)
                if not active:
                    self._rooms.pop(room, None)

    def snapshot(self) -> dict[str, int]:
        return {
            room: len(connections)
            for room, connections in self._rooms.items()
            if connections
        }

    def total_connections(self) -> int:
        return sum(self.snapshot().values())


websocket_manager = WebSocketManager()
