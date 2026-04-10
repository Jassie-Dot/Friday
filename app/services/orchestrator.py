from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.agents.base import AgentContext
from app.agents.registry import AgentRegistry
from app.core.config import Settings
from app.core.events import EventBus
from app.core.security import PermissionPolicy
from app.llm.ollama import OllamaClient
from app.memory.embeddings import build_embedding_provider
from app.memory.store import MemoryStore
from app.schemas.tasks import AgentName, StepExecution, StepStatus, TaskPlan, TaskRecord, TaskRequest, TaskStatus
from app.services.self_improvement import SelfImprovementService
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class FridayOrchestrator:
    """Owns task lifecycle, agent dispatch, retry/debug flow, and persistence."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.events = EventBus()
        self.policy = PermissionPolicy(settings)
        self.llm = OllamaClient(settings)
        self.memory = MemoryStore(settings, build_embedding_provider(settings))
        self.tools = ToolRegistry(settings, self.policy)
        self.agents = AgentRegistry(self.llm, self.memory, self.tools, self.events)
        self.self_improvement = SelfImprovementService(self.llm, self.memory)

        self.tasks: dict[str, TaskRecord] = {}
        self._queued_requests: dict[str, TaskRequest] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._worker_task: asyncio.Task[None] | None = None
        self._journal_path = settings.logs_dir / "task-history.jsonl"

    async def start(self) -> None:
        if self._worker_task is None:
            self._worker_task = asyncio.create_task(self._queue_worker())

    async def stop(self) -> None:
        if self._worker_task is not None:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
        await self.llm.close()

    async def _queue_worker(self) -> None:
        # Background tasks share the same in-memory queue and agent runtime as
        # synchronous executions, which keeps task state and event streaming unified.
        while True:
            task_id = await self._queue.get()
            request = self._queued_requests.pop(task_id, None)
            record = self.tasks.get(task_id)
            if request is None or record is None:
                self._queue.task_done()
                continue
            try:
                await self._execute(record, request)
            except Exception as exc:
                logger.exception("Background task failed: %s", exc)
                record.status = TaskStatus.failed
                record.summary = str(exc)
                record.updated_at = utc_now()
                await self._journal(record)
            finally:
                self._queue.task_done()

    async def run_task(self, request: TaskRequest) -> TaskRecord:
        record = TaskRecord(objective=request.objective)
        self.tasks[record.id] = record
        await self._execute(record, request)
        return record

    async def submit_task(self, request: TaskRequest) -> TaskRecord:
        record = TaskRecord(objective=request.objective)
        self.tasks[record.id] = record
        self._queued_requests[record.id] = request
        await self._queue.put(record.id)
        return record

    async def _execute(self, record: TaskRecord, request: TaskRequest) -> None:
        record.status = TaskStatus.planning
        record.updated_at = utc_now()

        memories = self.memory.query(request.objective, limit=5)
        planner = self.agents.get(AgentName.planner)
        planner_response = await planner.run(
            AgentContext(
                task_id=record.id,
                objective=request.objective,
                task_context=request.context,
                memories=memories,
            )
        )

        plan = TaskPlan.model_validate(planner_response.data["plan"])
        if len(plan.steps) > request.max_steps:
            plan.steps = plan.steps[: request.max_steps]
        record.plan = plan
        record.status = TaskStatus.running
        record.updated_at = utc_now()

        if request.store_memory:
            for memory_entry in planner_response.memory_entries:
                self.memory.add(memory_entry["document"], memory_entry.get("metadata", {}))

        # Each step is executed by its assigned specialist agent. Failed steps
        # can be handed to the debug agent for one safe retry cycle.
        for step in plan.steps:
            step.status = StepStatus.running
            response = await self._run_step(record, request, step, memories)
            if not response.success:
                record.status = TaskStatus.failed
                break

        if record.status != TaskStatus.failed:
            record.status = TaskStatus.completed

        record.summary = await self._summarize(record)
        if request.store_memory:
            record.learning_note = await self.self_improvement.analyze(record)
        record.updated_at = utc_now()
        await self._journal(record)

    async def _run_step(self, record: TaskRecord, request: TaskRequest, step, memories):
        agent = self.agents.get(step.agent)
        response = await agent.run(
            AgentContext(
                task_id=record.id,
                objective=record.objective,
                task_context=request.context,
                step=step,
                memories=memories,
                previous_results=record.step_results,
            )
        )
        execution = StepExecution(
            step_id=step.id,
            agent=step.agent,
            success=response.success,
            output=response.summary,
            data=response.data,
            error=response.error,
            completed_at=utc_now(),
        )
        record.step_results.append(execution)
        step.status = StepStatus.completed if response.success else StepStatus.failed
        record.updated_at = utc_now()

        if request.store_memory:
            for memory_entry in response.memory_entries:
                self.memory.add(
                    memory_entry["document"],
                    {
                        **memory_entry.get("metadata", {}),
                        "task_id": record.id,
                        "step_id": step.id,
                    },
                )

        if response.success or not request.auto_retry:
            return response

        debug_agent = self.agents.get(AgentName.debug)
        debug = await debug_agent.run(
            AgentContext(
                task_id=record.id,
                objective=record.objective,
                task_context=request.context,
                step=step,
                memories=memories,
                previous_results=record.step_results,
                failure_reason=response.error or response.summary,
            )
        )
        execution.data["debug"] = debug.data
        retry_inputs = debug.data.get("suggested_retry_inputs", {})
        if retry_inputs:
            step.inputs.update(retry_inputs)
            retry_response = await agent.run(
                AgentContext(
                    task_id=record.id,
                    objective=record.objective,
                    task_context=request.context,
                    step=step,
                    memories=memories,
                    previous_results=record.step_results,
                )
            )
            retry_execution = StepExecution(
                step_id=step.id,
                agent=step.agent,
                success=retry_response.success,
                output=retry_response.summary,
                data={**retry_response.data, "retry": True},
                error=retry_response.error,
                completed_at=utc_now(),
            )
            record.step_results.append(retry_execution)
            step.status = StepStatus.completed if retry_response.success else StepStatus.failed
            return retry_response
        return response

    async def _summarize(self, record: TaskRecord) -> str:
        fallback = "\n".join(
            f"{result.agent.value}: {result.output}"
            for result in record.step_results[-5:]
        )[:2000]
        try:
            result = await self.llm.json_response(
                [
                    {
                        "role": "system",
                        "content": 'Summarize task execution. Return JSON only with {"summary":"..."}',
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "objective": record.objective,
                                "status": record.status.value,
                                "results": [item.model_dump(mode="json") for item in record.step_results],
                            },
                            ensure_ascii=True,
                        ),
                    },
                ],
                model=self.llm.settings.fast_model,
            )
            if isinstance(result, dict) and result.get("summary"):
                return result["summary"]
        except Exception as exc:
            logger.warning("Summary generation fell back to heuristic: %s", exc)
        return fallback or "Task finished without detailed summary."

    async def _journal(self, record: TaskRecord) -> None:
        self._journal_path.parent.mkdir(parents=True, exist_ok=True)
        with self._journal_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.model_dump(mode="json"), ensure_ascii=True))
            handle.write("\n")

    def get_task(self, task_id: str) -> TaskRecord | None:
        return self.tasks.get(task_id)

    def list_tasks(self) -> list[TaskRecord]:
        return list(self.tasks.values())[-50:]

    def recent_events(self):
        return self.events.recent()

    async def health(self) -> dict[str, Any]:
        llm_ok = True
        llm_info: dict[str, Any] = {}
        try:
            llm_info = await self.llm.health()
        except Exception as exc:
            llm_ok = False
            llm_info = {"error": str(exc)}

        return {
            "app": self.settings.app_name,
            "status": "ok" if llm_ok else "degraded",
            "workspace_root": str(self.settings.workspace_root),
            "data_root": str(self.settings.data_root),
            "models": {
                "primary": self.settings.primary_model,
                "fast": self.settings.fast_model,
            },
            "ollama": llm_info,
        }
