from __future__ import annotations

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.models import ObjectiveRequest

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/presence")
async def presence_socket(websocket: WebSocket) -> None:
    runtime = websocket.app.state.runtime
    await runtime.realtime.connect(websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            # ── Handle incoming commands from the frontend ──
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type")

            if msg_type == "objective":
                # Frontend sending a text or voice command
                objective = msg.get("text", "").strip()
                if objective:
                    request = ObjectiveRequest(
                        objective=objective,
                        context=msg.get("context", {"source": "websocket"}),
                    )
                    await runtime.orchestrator.submit(request)

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        runtime.realtime.disconnect(websocket)
    except Exception as exc:
        logger.warning("WebSocket handler error: %s", exc)
        runtime.realtime.disconnect(websocket)
