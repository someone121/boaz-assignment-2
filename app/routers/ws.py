"""WebSocket endpoint for real-time classroom updates."""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.ws_manager import ws_manager

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/{session_id}")
async def classroom_websocket(websocket: WebSocket, session_id: str) -> None:
    """Maintain persistent real-time socket for lecturer, student, and forum views."""
    await ws_manager.connect(websocket, session_id)
    try:
        while True:
            # Keep socket alive and ignore/echo lightweight client pings.
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, session_id)
