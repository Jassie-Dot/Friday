from __future__ import annotations

import base64
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
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type")
            if msg_type == "objective":
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
        logger.warning("Presence websocket handler error: %s", exc)
        runtime.realtime.disconnect(websocket)


@router.websocket("/ws/session")
async def session_socket(websocket: WebSocket) -> None:
    runtime = websocket.app.state.runtime
    session = await runtime.sessions.connect(websocket)
    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break

            if message.get("text"):
                try:
                    payload = json.loads(message["text"])
                except json.JSONDecodeError:
                    continue
                await runtime.sessions.handle_message(session, payload)
                continue

            if message.get("bytes"):
                await runtime.sessions.handle_message(
                    session,
                    {
                        "type": "audio.frame",
                        "audio": base64.b64encode(message["bytes"]).decode("ascii"),
                        "sample_rate": runtime.settings.voice_sample_rate,
                    },
                )
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.warning("Voice session websocket handler error: %s", exc)
    finally:
        await runtime.sessions.disconnect(session)
