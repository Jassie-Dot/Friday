from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AgentName(str, Enum):
    planner = "planner"
    executor = "executor"
    critic = "critic"
    evolution = "evolution"
    debug = "debug"
    memory = "memory"
    web = "web"
    system = "system"
    vision = "vision"
    voice = "voice"
    chat = "chat"


class TaskStatus(str, Enum):
    queued = "queued"
    planning = "planning"
    running = "running"
    completed = "completed"
    failed = "failed"


class StepStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class PresenceMode(str, Enum):
    idle = "idle"
    listening = "listening"
    thinking = "thinking"
    speaking = "speaking"
    executing = "executing"
    error = "error"


class FrontendMode(str, Enum):
    particles = "particles"
    antigravity = "antigravity"
    three_d_core = "3d-core"


class MemoryHit(BaseModel):
    id: str
    document: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskStep(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    agent: AgentName
    goal: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    expected_output: str = ""
    status: StepStatus = StepStatus.pending


class TaskPlan(BaseModel):
    objective: str
    reasoning: str = ""
    steps: list[TaskStep] = Field(default_factory=list)


class StepExecution(BaseModel):
    step_id: str
    agent: AgentName
    success: bool
    output: str
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None


class TaskMetrics(BaseModel):
    queue_ms: float = 0.0
    planning_ms: float = 0.0
    execution_ms: float = 0.0
    total_ms: float = 0.0
    first_response_ms: float = 0.0
    cache_hit: bool = False
    routed_model: str = ""
    interrupted: bool = False


class TaskCritique(BaseModel):
    score: float = 0.5
    strengths: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class EvolutionNote(BaseModel):
    prompt_key: str | None = None
    variant_id: str | None = None
    summary: str = ""
    suggested_upgrades: list[str] = Field(default_factory=list)


class ObjectiveRequest(BaseModel):
    objective: str
    context: dict[str, Any] = Field(default_factory=dict)
    max_steps: int = 8
    auto_retry: bool = True
    store_memory: bool = True


class TaskRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    objective: str
    status: TaskStatus = TaskStatus.queued
    plan: TaskPlan | None = None
    step_results: list[StepExecution] = Field(default_factory=list)
    summary: str = ""
    learning_note: str | None = None
    critique: TaskCritique | None = None
    evolution: EvolutionNote | None = None
    metrics: TaskMetrics = Field(default_factory=TaskMetrics)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class AgentEvent(BaseModel):
    source: AgentName
    task_id: str
    message_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class PresenceSnapshot(BaseModel):
    mode: PresenceMode = PresenceMode.idle
    headline: str = "FRIDAY online"
    whisper: str = "Standing by"
    active_agents: list[AgentName] = Field(default_factory=list)
    current_objective: str | None = None
    audio_level: float = 0.0
    energy: float = 0.15
    frontend_mode: FrontendMode = FrontendMode.particles
    terminal_text: str = ""
    updated_at: datetime = Field(default_factory=utc_now)


class ApiEnvelope(BaseModel):
    ok: bool = True
    message: str = "success"
    data: Any = Field(default_factory=dict)


def as_jsonable(model: BaseModel | Mapping[str, Any] | list[Any] | Any) -> Any:
    if isinstance(model, BaseModel):
        return model.model_dump(mode="json")
    if isinstance(model, Mapping):
        return dict(model)
    return model
