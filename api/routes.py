from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from core.models import ApiEnvelope, ObjectiveRequest


router = APIRouter(prefix="/api")


def runtime_from_request(request: Request):
    return request.app.state.runtime


@router.get("/health", response_model=ApiEnvelope)
async def health(request: Request) -> ApiEnvelope:
    runtime = runtime_from_request(request)
    return ApiEnvelope(data=await runtime.health())


@router.get("/agents", response_model=ApiEnvelope)
async def list_agents(request: Request) -> ApiEnvelope:
    runtime = runtime_from_request(request)
    return ApiEnvelope(data={"agents": runtime.agents.describe()})


@router.get("/tasks", response_model=ApiEnvelope)
async def list_tasks(request: Request) -> ApiEnvelope:
    runtime = runtime_from_request(request)
    return ApiEnvelope(data={"tasks": [task.model_dump(mode="json") for task in runtime.orchestrator.list_tasks()]})


@router.get("/tasks/{task_id}", response_model=ApiEnvelope)
async def get_task(task_id: str, request: Request) -> ApiEnvelope:
    runtime = runtime_from_request(request)
    task = runtime.orchestrator.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    return ApiEnvelope(data=task.model_dump(mode="json"))


@router.post("/objectives/run", response_model=ApiEnvelope)
async def run_objective(payload: ObjectiveRequest, request: Request) -> ApiEnvelope:
    runtime = runtime_from_request(request)
    record = await runtime.orchestrator.run(payload)
    return ApiEnvelope(data=record.model_dump(mode="json"))


@router.post("/objectives/submit", response_model=ApiEnvelope)
async def submit_objective(payload: ObjectiveRequest, request: Request) -> ApiEnvelope:
    runtime = runtime_from_request(request)
    record = await runtime.orchestrator.submit(payload)
    return ApiEnvelope(data=record.model_dump(mode="json"))


@router.get("/state", response_model=ApiEnvelope)
async def get_state(request: Request) -> ApiEnvelope:
    runtime = runtime_from_request(request)
    return ApiEnvelope(
        data={
            "presence": runtime.realtime.presence.model_dump(mode="json"),
            "events": [event.model_dump(mode="json") for event in runtime.realtime.recent_events()],
        }
    )


@router.get("/frontend", response_model=ApiEnvelope)
async def frontend_meta(request: Request) -> ApiEnvelope:
    runtime = runtime_from_request(request)
    settings = runtime.settings
    return ApiEnvelope(
        data={
            "active_mode": settings.frontend_mode.value,
            "available_modes": ["3d-core", "particles", "antigravity"],
            "three_d_core_url": f"http://{settings.three_d_core_host}:{settings.three_d_core_port}",
            "particles_url": f"http://{settings.particles_host}:{settings.particles_port}",
            "antigravity_url": f"http://{settings.antigravity_host}:{settings.antigravity_port}",
            "api_url": f"http://{settings.host}:{settings.port}",
        }
    )


@router.post("/memory/search", response_model=ApiEnvelope)
async def search_memory(payload: dict, request: Request) -> ApiEnvelope:
    runtime = runtime_from_request(request)
    query = payload.get("query", "")
    limit = int(payload.get("limit", 5))
    where = payload.get("where")
    results = runtime.memory.query(query, limit=limit, where=where)
    return ApiEnvelope(data={"results": [item.model_dump() for item in results]})


@router.post("/images/generate", response_model=ApiEnvelope)
async def generate_image(payload: dict, request: Request) -> ApiEnvelope:
    runtime = runtime_from_request(request)
    result = await runtime.tools.get("image").execute(**payload)
    return ApiEnvelope(ok=result.success, message=result.output, data=result.model_dump())


@router.post("/voice/transcribe", response_model=ApiEnvelope)
async def transcribe(payload: dict, request: Request) -> ApiEnvelope:
    runtime = runtime_from_request(request)
    result = await runtime.tools.get("voice").execute(action="transcribe", audio_path=payload.get("audio_path"))
    return ApiEnvelope(ok=result.success, message=result.output, data=result.model_dump())


@router.post("/voice/speak", response_model=ApiEnvelope)
async def speak(payload: dict, request: Request) -> ApiEnvelope:
    runtime = runtime_from_request(request)
    result = await runtime.tools.get("voice").execute(
        action="speak",
        text=payload.get("text"),
        output_path=payload.get("output_path"),
    )
    return ApiEnvelope(ok=result.success, message=result.output, data=result.model_dump())


@router.get("/", include_in_schema=False)
async def api_root() -> ApiEnvelope:
    return ApiEnvelope(data={"message": "FRIDAY API online", "docs": "/docs"})
