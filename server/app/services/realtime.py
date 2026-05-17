from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder


class RealtimeManager:
    def __init__(self) -> None:
        self._rooms: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, game_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._rooms[game_id].add(websocket)

    def disconnect(self, game_id: str, websocket: WebSocket) -> None:
        clients = self._rooms.get(game_id)
        if not clients:
            return

        clients.discard(websocket)
        if not clients:
            self._rooms.pop(game_id, None)

    async def broadcast(self, game_id: str, payload: dict[str, Any]) -> None:
        clients = list(self._rooms.get(game_id, set()))
        stale: list[WebSocket] = []
        encoded_payload = jsonable_encoder(payload)

        for websocket in clients:
            try:
                await websocket.send_json(encoded_payload)
            except Exception:
                stale.append(websocket)

        for websocket in stale:
            self.disconnect(game_id, websocket)


realtime = RealtimeManager()
