from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect


router = APIRouter()


@router.websocket("/ws/presence")
async def presence_socket(websocket: WebSocket) -> None:
    runtime = websocket.app.state.runtime
    await runtime.realtime.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        runtime.realtime.disconnect(websocket)
