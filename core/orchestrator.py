from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from time import perf_counter

from agents.base import AgentContext, AgentResponse
from agents.registry import AgentRegistry
from core.intent import is_conversational
from core.llm import OllamaClient
from core.models import (
    AgentName,
    ObjectiveRequest,
    PresenceMode,
    StepExecution,
    StepStatus,
    TaskCritique,
    TaskPlan,
    TaskRecord,
    TaskStatus,
    TaskStep,
    utc_now,
)
from core.realtime import RealtimeHub
from memory.store import MemoryStore

logger = logging.getLogger(__name__)


class FridayOrchestrator:
    """Coordinates planning, execution, critique, journaling, and self-improvement."""

    def __init__(
        self,
        llm: OllamaClient,
        memory: MemoryStore,
        agents: AgentRegistry,
        realtime: RealtimeHub,
        logs_root: Path,
        evolution,
    ) -> None:
        self.llm = llm
        self.memory = memory
        self.agents = agents
        self.realtime = realtime
        self.logs_root = logs_root
        self.evolution = evolution
        self.tasks: dict[str, TaskRecord] = {}
        self._queued_requests: dict[str, ObjectiveRequest] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._worker: asyncio.Task[None] | None = None
        self._journal_path = logs_root / "task-history.jsonl"

    async def start(self) -> None:
        if self._worker is None:
            self._worker = asyncio.create_task(self._queue_worker())

    async def stop(self) -> None:
        if self._worker is None:
            return
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
            record.metrics.queue_ms = max((utc_now() - record.created_at).total_seconds() * 1000, 0.0)
            try:
                await self._execute(record, request)
            except Exception as exc:
                logger.error("Task execution failed completely: %s", exc, exc_info=True)
                record.status = TaskStatus.failed
                record.summary = f"System error: {exc}"
                await self._set_error_presence(request.objective, str(exc))
            finally:
                self._queue.task_done()

    async def _execute(self, record: TaskRecord, request: ObjectiveRequest) -> None:
        started = perf_counter()
        if is_conversational(request.objective):
            await self._execute_fast_chat(record, request)
        else:
            await self._execute_full(record, request)
        record.metrics.total_ms = round((perf_counter() - started) * 1000, 2)
        record.updated_at = utc_now()

    async def _execute_fast_chat(self, record: TaskRecord, request: ObjectiveRequest) -> None:
        memories = self.memory.query(request.objective, limit=3)
        await self.realtime.set_presence(
            mode=PresenceMode.thinking,
            headline="Thinking",
            whisper=request.objective,
            terminal_text="One moment, Boss...",
            active_agents=[AgentName.chat],
            current_objective=request.objective,
            energy=0.52,
        )
        record.status = TaskStatus.running
        record.updated_at = utc_now()

        step = TaskStep(title="Respond to Boss", agent=AgentName.chat, goal=request.objective)
        record.plan = TaskPlan(
            objective=request.objective,
            reasoning="Fast-path conversational response",
            steps=[step],
        )

        step_started = perf_counter()
        chat_agent = self.agents.get(AgentName.chat)
        try:
            response = await chat_agent.run(
                AgentContext(
                    task_id=record.id,
                    objective=request.objective,
                    task_context=request.context,
                    step=step,
                    memories=memories,
                    previous_results=[],
                )
            )
        except Exception as exc:
            logger.error("Chat agent crashed: %s", exc, exc_info=True)
            response = AgentResponse(success=False, summary=f"Sorry Boss, I hit a snag: {exc}", error=str(exc))

        execution = StepExecution(
            step_id=step.id,
            agent=AgentName.chat,
            success=response.success,
            output=response.summary,
            data=response.data,
            error=response.error,
            completed_at=utc_now(),
        )
        record.step_results.append(execution)
        step.status = StepStatus.completed if response.success else StepStatus.failed
        record.status = TaskStatus.completed if response.success else TaskStatus.failed
        record.summary = response.summary
        record.metrics.execution_ms = round((perf_counter() - step_started) * 1000, 2)
        record.metrics.first_response_ms = record.metrics.execution_ms
        record.metrics.routed_model = self.llm.settings.fast_model
        await self.realtime.add_conversation(role="user", text=request.objective)
        await self.realtime.add_conversation(role="friday", text=response.summary)

        await self.realtime.set_presence(
            mode=PresenceMode.speaking,
            headline="FRIDAY",
            whisper="Response ready",
            terminal_text=response.summary,
            active_agents=[],
            current_objective=request.objective,
            energy=0.38,
        )

        if request.store_memory and response.memory_entries:
            for entry in response.memory_entries:
                self.memory.add(entry["document"], entry.get("metadata", {}))

        await self._reflect(record, request)
        await self._journal(record)
        await asyncio.sleep(0.2)
        await self._set_idle_presence()

    async def _execute_full(self, record: TaskRecord, request: ObjectiveRequest) -> None:
        memories = self.memory.query(request.objective, limit=5)
        await self.realtime.add_conversation(role="user", text=request.objective)
        await self.realtime.set_presence(
            mode=PresenceMode.thinking,
            headline="Analyzing",
            whisper=request.objective,
            terminal_text="Running diagnostics on your request, Boss...",
            active_agents=[AgentName.planner],
            current_objective=request.objective,
            energy=0.46,
        )

        record.status = TaskStatus.planning
        planning_started = perf_counter()
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
        record.metrics.planning_ms = round((perf_counter() - planning_started) * 1000, 2)
        record.metrics.first_response_ms = record.metrics.planning_ms

        if request.store_memory:
            for entry in planner_response.memory_entries:
                self.memory.add(entry["document"], entry.get("metadata", {}))

        execution_started = perf_counter()
        for step in plan.steps:
            step.status = StepStatus.running
            await self._set_step_presence(step, request.objective)
            response = await self._run_step(record, request, step, memories)

            if response.success:
                await self.realtime.set_presence(
                    mode=self._presence_for_agent(step.agent),
                    headline=f"{step.agent.value.title()} protocol active",
                    whisper=step.title,
                    terminal_text=response.summary,
                    active_agents=[step.agent],
                    current_objective=request.objective,
                    energy=0.54,
                )
            else:
                record.status = TaskStatus.failed
                await self._set_error_presence(request.objective, response.error or response.summary)
                break

        record.metrics.execution_ms = round((perf_counter() - execution_started) * 1000, 2)
        if record.status != TaskStatus.failed:
            record.status = TaskStatus.completed
            if len(plan.steps) == 1 and plan.steps[0].agent == AgentName.chat and record.step_results:
                record.summary = record.step_results[0].output
            else:
                record.summary = await self._summarize(record)
            await self.realtime.add_conversation(role="friday", text=record.summary)
            await self.realtime.set_presence(
                mode=PresenceMode.speaking,
                headline="Mission complete",
                whisper=request.objective,
                terminal_text=record.summary,
                active_agents=[],
                current_objective=request.objective,
                energy=0.38,
            )
        else:
            if not record.summary:
                record.summary = await self._summarize(record)
            await self.realtime.add_conversation(
                role="friday",
                text=record.summary or "I wasn't able to complete that one, Boss.",
            )

        await self._reflect(record, request)
        await self._journal(record)
        await self._set_idle_presence()

    async def _run_step(
        self,
        record: TaskRecord,
        request: ObjectiveRequest,
        step: TaskStep,
        memories,
    ) -> AgentResponse:
        agent = self.agents.get(step.agent)
        try:
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
        except Exception as exc:
            logger.error("Agent %s crashed: %s", step.agent.value, exc, exc_info=True)
            response = AgentResponse(
                success=False,
                summary=f"Agent {step.agent.value} encountered an error: {exc}",
                error=str(exc),
                data={},
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
        try:
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
        except Exception as exc:
            logger.error("Debugger crashed: %s", exc, exc_info=True)
            debug_response = AgentResponse(success=False, summary=str(exc))

        execution.data["debug"] = debug_response.data
        retry_inputs = debug_response.data.get("suggested_retry_inputs", {})
        if not retry_inputs:
            return response

        step.inputs.update(retry_inputs)
        try:
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
        except Exception as exc:
            logger.error("Agent replay crashed: %s", exc, exc_info=True)
            retry = AgentResponse(success=False, summary=str(exc), error=str(exc))

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

    async def _summarize(self, record: TaskRecord) -> str:
        fallback = "\n".join(f"{item.agent.value}: {item.output}" for item in record.step_results[-5:])[:2000]
        try:
            result = await self.llm.json_response(
                [
                    {
                        "role": "system",
                        "content": (
                            "You are FRIDAY. Summarize what you accomplished for the Boss. "
                            'Return JSON only: {"summary":"..."}'
                        ),
                    },
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
        return fallback or "Objective processed, Boss."

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

    async def _reflect(self, record: TaskRecord, request: ObjectiveRequest) -> None:
        try:
            critic = self.agents.get(AgentName.critic)
            evolution_agent = self.agents.get(AgentName.evolution)

            critique_response = await critic.run(
                AgentContext(
                    task_id=record.id,
                    objective=record.objective,
                    task_context={**request.context, "summary": record.summary, "status": record.status.value},
                    previous_results=record.step_results,
                )
            )
            critique_data = critique_response.data if isinstance(critique_response.data, dict) else {}
            record.critique = TaskCritique.model_validate(critique_data or {})

            evolution_response = await evolution_agent.run(
                AgentContext(
                    task_id=record.id,
                    objective=record.objective,
                    task_context={
                        **request.context,
                        "summary": record.summary,
                        "status": record.status.value,
                        "critique": record.critique.model_dump(mode="json") if record.critique else {},
                    },
                    previous_results=record.step_results,
                    failure_reason=None if record.status == TaskStatus.completed else record.summary,
                )
            )
            record.evolution = self.evolution.apply(record, record.critique, evolution_response.data)
        except Exception as exc:
            logger.warning("Reflection loop failed: %s", exc, exc_info=True)

        if request.store_memory:
            record.learning_note = await self._learning_note(record)

    async def _journal(self, record: TaskRecord) -> None:
        self._journal_path.parent.mkdir(parents=True, exist_ok=True)
        with self._journal_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.model_dump(mode="json"), ensure_ascii=True))
            handle.write("\n")

    async def _set_step_presence(self, step: TaskStep, objective: str) -> None:
        mode = self._presence_for_agent(step.agent)
        await self.realtime.set_presence(
            mode=mode,
            headline=f"{step.agent.value.title()} protocol active",
            whisper=step.title,
            active_agents=[step.agent],
            current_objective=objective,
            energy=0.82 if mode == PresenceMode.executing else 0.62,
        )

    @staticmethod
    def _presence_for_agent(agent: AgentName) -> PresenceMode:
        if agent == AgentName.chat:
            return PresenceMode.speaking
        if agent in {AgentName.executor, AgentName.system}:
            return PresenceMode.executing
        return PresenceMode.thinking

    async def _set_idle_presence(self) -> None:
        await self.realtime.set_presence(
            mode=PresenceMode.idle,
            headline="FRIDAY",
            whisper="Standing by, Boss",
            active_agents=[],
            current_objective=None,
            energy=0.15,
        )

    async def _set_error_presence(self, objective: str, error_text: str) -> None:
        await self.realtime.set_presence(
            mode=PresenceMode.error,
            headline="Protocol fault",
            whisper=objective,
            terminal_text=error_text,
            active_agents=[AgentName.debug],
            current_objective=objective,
            energy=0.95,
        )

    def get_task(self, task_id: str) -> TaskRecord | None:
        return self.tasks.get(task_id)

    def list_tasks(self) -> list[TaskRecord]:
        return list(self.tasks.values())[-50:]
