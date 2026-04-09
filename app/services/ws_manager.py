"""WebSocket connection manager for real-time teacher/runtime state push.

Maintains a registry of open WebSocket connections keyed by attempt_id.
When the teacher advances state the router calls broadcast(), pushing the
updated CommandStateResponse JSON to every connected client for that attempt.

Polling continues as a safety-net fallback; the WS layer just makes updates arrive in <10 ms instead of
up to the polling interval.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        # attempt_id -> list of open WebSocket connections
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, ws: WebSocket, attempt_id: str) -> None:
        await ws.accept()
        self._connections[attempt_id].append(ws)

    def disconnect(self, ws: WebSocket, attempt_id: str) -> None:
        conns = self._connections.get(attempt_id, [])
        self._connections[attempt_id] = [c for c in conns if c is not ws]

    async def broadcast(self, attempt_id: str, data: dict[str, Any]) -> None:
        """Send data to every client watching this attempt. Dead sockets are pruned."""
        dead: list[WebSocket] = []
        for ws in list(self._connections.get(attempt_id, [])):
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, attempt_id)

    def connection_count(self, attempt_id: str) -> int:
        return len(self._connections.get(attempt_id, []))


# Singleton — imported by routers that need to broadcast or open connections.
manager = ConnectionManager()
