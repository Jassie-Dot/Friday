from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


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


class AgentName(str, Enum):
    planner = "planner"
    executor = "executor"
    debug = "debug"
    memory = "memory"
    web = "web"
    vision = "vision"
    system = "system"
    voice = "voice"


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


class TaskRequest(BaseModel):
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


class AgentMessage(BaseModel):
    source: AgentName
    target: AgentName | None = None
    task_id: str
    message_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
