from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from agents.base import AgentContext
from agents.registry import AgentRegistry
from core.llm import OllamaClient
from core.models import AgentName, ObjectiveRequest, PresenceMode, StepExecution, StepStatus, TaskPlan, TaskRecord, TaskStatus, utc_now
from core.realtime import RealtimeHub
from memory.store import MemoryStore

logger = logging.getLogger(__name__)


class FridayOrchestrator:
    """Coordinates planning, execution, retry, logging, and learning."""

    def __init__(
        self,
        llm: OllamaClient,
        memory: MemoryStore,
        agents: AgentRegistry,
        realtime: RealtimeHub,
        logs_root: Path,
    ) -> None:
        self.llm = llm
        self.memory = memory
        self.agents = agents
        self.realtime = realtime
        self.logs_root = logs_root
        self.tasks: dict[str, TaskRecord] = {}
        self._queued_requests: dict[str, ObjectiveRequest] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._worker: asyncio.Task[None] | None = None
        self._journal_path = logs_root / "task-history.jsonl"

    async def start(self) -> None:
        if self._worker is None:
            self._worker = asyncio.create_task(self._queue_worker())

    async def stop(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            try:
                await self._worker
            except asyncio.CancelledError:
                pass
            self._worker = None

    async def run(self, request: ObjectiveRequest) -> TaskRecord:
        record = TaskRecord(objective=request.objective)
        self.tasks[record.id] = record
        await self._execute(record, request)
        return record

    async def submit(self, request: ObjectiveRequest) -> TaskRecord:
        record = TaskRecord(objective=request.objective)
        self.tasks[record.id] = record
        self._queued_requests[record.id] = request
        await self._queue.put(record.id)
        return record

    async def _queue_worker(self) -> None:
        while True:
            task_id = await self._queue.get()
            record = self.tasks.get(task_id)
            request = self._queued_requests.pop(task_id, None)
            if record is None or request is None:
                self._queue.task_done()
                continue
            try:
                await self._execute(record, request)
            finally:
                self._queue.task_done()

    async def _execute(self, record: TaskRecord, request: ObjectiveRequest) -> None:
        memories = self.memory.query(request.objective, limit=5)
        await self.realtime.set_presence(
            mode=PresenceMode.thinking,
            headline="Planning objective",
            whisper=request.objective,
            active_agents=[AgentName.planner.value],
            current_objective=request.objective,
            energy=0.45,
        )
        record.status = TaskStatus.planning
        record.updated_at = utc_now()

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
            for entry in planner_response.memory_entries:
                self.memory.add(entry["document"], entry.get("metadata", {}))

        for step in plan.steps:
            step.status = StepStatus.running
            await self.realtime.set_presence(
                mode=PresenceMode.thinking,
                headline=f"{step.agent.value.title()} agent active",
                whisper=step.title,
                active_agents=[step.agent.value],
                current_objective=request.objective,
                energy=0.6,
            )
            response = await self._run_step(record, request, step, memories)
            if not response.success:
                record.status = TaskStatus.failed
                await self.realtime.set_presence(
                    mode=PresenceMode.error,
                    headline="Execution fault",
                    whisper=response.error or response.summary,
                    active_agents=[AgentName.debug.value],
                    current_objective=request.objective,
                    energy=0.95,
                )
                break

        if record.status != TaskStatus.failed:
            record.status = TaskStatus.completed
            await self.realtime.set_presence(
                mode=PresenceMode.responding,
                headline="Objective completed",
                whisper=request.objective,
                active_agents=[],
                current_objective=request.objective,
                energy=0.35,
            )

        record.summary = await self._summarize(record)
        if request.store_memory:
            record.learning_note = await self._learning_note(record)
        record.updated_at = utc_now()
        await self._journal(record)
        await self.realtime.set_presence(
            mode=PresenceMode.idle,
            headline="FRIDAY online",
            whisper="Standing by for the next objective",
            active_agents=[],
            current_objective=None,
            energy=0.15,
        )

    async def _run_step(self, record: TaskRecord, request: ObjectiveRequest, step, memories):
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
            for entry in response.memory_entries:
                self.memory.add(
                    entry["document"],
                    {
                        **entry.get("metadata", {}),
                        "task_id": record.id,
                        "step_id": step.id,
                    },
                )

        if response.success or not request.auto_retry:
            return response

        debugger = self.agents.get(AgentName.debug)
        debug_response = await debugger.run(
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
        execution.data["debug"] = debug_response.data
        retry_inputs = debug_response.data.get("suggested_retry_inputs", {})
        if retry_inputs:
            step.inputs.update(retry_inputs)
            retry = await agent.run(
                AgentContext(
                    task_id=record.id,
                    objective=record.objective,
                    task_context=request.context,
                    step=step,
                    memories=memories,
                    previous_results=record.step_results,
                )
            )
            record.step_results.append(
                StepExecution(
                    step_id=step.id,
                    agent=step.agent,
                    success=retry.success,
                    output=retry.summary,
                    data={**retry.data, "retry": True},
                    error=retry.error,
                    completed_at=utc_now(),
                )
            )
            step.status = StepStatus.completed if retry.success else StepStatus.failed
            return retry
        return response

    async def _summarize(self, record: TaskRecord) -> str:
        fallback = "\n".join(f"{item.agent.value}: {item.output}" for item in record.step_results[-5:])[:2000]
        try:
            result = await self.llm.json_response(
                [
                    {"role": "system", "content": 'Summarize the task result. Return JSON only with {"summary":"..."}'},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "objective": record.objective,
                                "status": record.status.value,
                                "steps": [step.model_dump(mode="json") for step in record.step_results],
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
            logger.warning("Task summary fell back to heuristic text: %s", exc)
        return fallback or "Objective finished without a detailed summary."

    async def _learning_note(self, record: TaskRecord) -> str:
        fallback = "Failures should be narrowed to smaller tool calls; successes should be reused as templates."
        try:
            result = await self.llm.json_response(
                [
                    {
                        "role": "system",
                        "content": 'Return JSON only with {"learning_note":"..."} describing one reusable improvement.',
                    },
                    {
                        "role": "user",
                        "content": json.dumps(record.model_dump(mode="json"), ensure_ascii=True),
                    },
                ],
                model=self.llm.settings.fast_model,
            )
            note = result.get("learning_note", fallback) if isinstance(result, dict) else fallback
        except Exception as exc:
            logger.warning("Learning note fell back to heuristic text: %s", exc)
            note = fallback
        self.memory.add(note, {"type": "learning", "task_id": record.id, "status": record.status.value})
        return note

    async def _journal(self, record: TaskRecord) -> None:
        self._journal_path.parent.mkdir(parents=True, exist_ok=True)
        with self._journal_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.model_dump(mode="json"), ensure_ascii=True))
            handle.write("\n")

    def get_task(self, task_id: str) -> TaskRecord | None:
        return self.tasks.get(task_id)

    def list_tasks(self) -> list[TaskRecord]:
        return list(self.tasks.values())[-50:]
