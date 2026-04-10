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
    debug = "debug"
    memory = "memory"
    web = "web"
    system = "system"
    vision = "vision"
    voice = "voice"


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
    responding = "responding"
    error = "error"


class FrontendMode(str, Enum):
    particles = "particles"
    antigravity = "antigravity"


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
