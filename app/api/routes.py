from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from app.schemas.api import ApiEnvelope, ImageGenerationRequest, MemorySearchRequest, SpeechRequest, VoiceTranscriptionRequest
from app.schemas.tasks import TaskRequest


router = APIRouter(prefix="/api")
page_router = APIRouter()


def orchestrator_from_request(request: Request):
    return request.app.state.orchestrator


@router.get("/health", response_model=ApiEnvelope)
async def health(request: Request) -> ApiEnvelope:
    orchestrator = orchestrator_from_request(request)
    return ApiEnvelope(data=await orchestrator.health())


@router.get("/agents", response_model=ApiEnvelope)
async def list_agents(request: Request) -> ApiEnvelope:
    orchestrator = orchestrator_from_request(request)
    return ApiEnvelope(data={"agents": orchestrator.agents.describe()})


@router.get("/tasks", response_model=ApiEnvelope)
async def list_tasks(request: Request) -> ApiEnvelope:
    orchestrator = orchestrator_from_request(request)
    return ApiEnvelope(data={"tasks": [task.model_dump(mode="json") for task in orchestrator.list_tasks()]})


@router.get("/tasks/{task_id}", response_model=ApiEnvelope)
async def get_task(task_id: str, request: Request) -> ApiEnvelope:
    orchestrator = orchestrator_from_request(request)
    task = orchestrator.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")
    return ApiEnvelope(data=task.model_dump(mode="json"))


@router.post("/tasks/run", response_model=ApiEnvelope)
async def run_task(payload: TaskRequest, request: Request) -> ApiEnvelope:
    orchestrator = orchestrator_from_request(request)
    record = await orchestrator.run_task(payload)
    return ApiEnvelope(data=record.model_dump(mode="json"))


@router.post("/tasks/submit", response_model=ApiEnvelope)
async def submit_task(payload: TaskRequest, request: Request) -> ApiEnvelope:
    orchestrator = orchestrator_from_request(request)
    record = await orchestrator.submit_task(payload)
    return ApiEnvelope(data=record.model_dump(mode="json"))


@router.get("/events", response_model=ApiEnvelope)
async def list_events(request: Request) -> ApiEnvelope:
    orchestrator = orchestrator_from_request(request)
    return ApiEnvelope(data={"events": [event.model_dump(mode="json") for event in orchestrator.recent_events()]})


@router.post("/memory/search", response_model=ApiEnvelope)
async def search_memory(payload: MemorySearchRequest, request: Request) -> ApiEnvelope:
    orchestrator = orchestrator_from_request(request)
    results = orchestrator.memory.query(payload.query, limit=payload.limit, where=payload.where)
    return ApiEnvelope(data={"results": [result.model_dump() for result in results]})


@router.post("/images/generate", response_model=ApiEnvelope)
async def generate_image(payload: ImageGenerationRequest, request: Request) -> ApiEnvelope:
    orchestrator = orchestrator_from_request(request)
    result = await orchestrator.tools.get("image").execute(**payload.model_dump())
    return ApiEnvelope(ok=result.success, message=result.output, data=result.model_dump())


@router.post("/voice/transcribe", response_model=ApiEnvelope)
async def transcribe_audio(payload: VoiceTranscriptionRequest, request: Request) -> ApiEnvelope:
    orchestrator = orchestrator_from_request(request)
    result = await orchestrator.tools.get("voice").execute(action="transcribe", audio_path=str(payload.audio_path))
    return ApiEnvelope(ok=result.success, message=result.output, data=result.model_dump())


@router.post("/voice/speak", response_model=ApiEnvelope)
async def speak_text(payload: SpeechRequest, request: Request) -> ApiEnvelope:
    orchestrator = orchestrator_from_request(request)
    result = await orchestrator.tools.get("voice").execute(
        action="speak",
        text=payload.text,
        output_path=str(payload.output_path) if payload.output_path else None,
    )
    return ApiEnvelope(ok=result.success, message=result.output, data=result.model_dump())


@page_router.get("/", include_in_schema=False)
async def dashboard() -> FileResponse:
    return FileResponse(Path(__file__).resolve().parents[1] / "ui" / "index.html")
