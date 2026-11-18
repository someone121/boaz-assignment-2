"""In-memory WebSocket connection manager for real-time classroom broadcasts."""

from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    """Manages active WebSocket clients grouped by lecture session_id."""

    def __init__(self) -> None:
        self.active_connections: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, websocket: WebSocket, session_id: str) -> None:
        """Accept and register a WebSocket connection for a session channel."""
        await websocket.accept()
        self.active_connections[session_id].append(websocket)

    def disconnect(self, websocket: WebSocket, session_id: str) -> None:
        """Remove a closed WebSocket connection from the session channel."""
        clients = self.active_connections.get(session_id, [])
        if websocket in clients:
            clients.remove(websocket)
        if not clients and session_id in self.active_connections:
            del self.active_connections[session_id]

    async def broadcast_event(self, session_id: str, event: str, data: dict[str, Any]) -> None:
        """Broadcast a typed JSON event ({event, data}) to session subscribers."""
        payload = {"event": event, "data": data}
        targets = list(self.active_connections.get(session_id, []))
        # Also notify clients subscribed to the global channel when applicable.
        if session_id != "global":
            targets.extend(self.active_connections.get("global", []))

        stale: list[tuple[str, WebSocket]] = []
        for ws in targets:
            try:
                await ws.send_json(payload)
            except Exception:
                for key, conns in self.active_connections.items():
                    if ws in conns:
                        stale.append((key, ws))

        for key, ws in stale:
            self.disconnect(ws, key)


ws_manager = ConnectionManager()
