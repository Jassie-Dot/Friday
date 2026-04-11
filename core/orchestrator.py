from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path

from agents.base import AgentContext, AgentResponse
from agents.registry import AgentRegistry
from core.llm import OllamaClient
from core.models import AgentName, ObjectiveRequest, PresenceMode, StepExecution, StepStatus, TaskPlan, TaskRecord, TaskStep, TaskStatus, utc_now
from core.realtime import RealtimeHub
from memory.store import MemoryStore

logger = logging.getLogger(__name__)

# Keywords that indicate a task rather than a conversation
_TASK_KEYWORDS = frozenset({
    "search", "research", "scrape", "web", "browse", "internet",
    "image", "visual", "art", "render", "draw", "picture", "generate",
    "transcribe", "dictation", "record",
    "browser", "open app", "launch", "automation",
    "run", "execute", "script", "code", "compile", "build", "install",
    "file", "folder", "directory", "delete", "create", "move", "copy",
    "download", "upload", "deploy",
})


def _is_conversational(objective: str) -> bool:
    """Return True if the objective looks like casual conversation rather than a task."""
    lower = objective.lower().strip()
    # Very short messages are almost always conversational
    if len(lower.split()) <= 4:
        # But check for task keywords even in short messages
        if not any(kw in lower for kw in _TASK_KEYWORDS):
            return True
    # Questions that start with who/what/why/how/when/where + conversational
    if re.match(r"^(hey|hi|hello|yo|sup|good morning|good evening|good night|thanks|thank you|bye|goodbye)", lower):
        return True
    if re.match(r"^(who|what|why|how|when|where|can you|could you|tell me|explain|describe)", lower):
        if not any(kw in lower for kw in _TASK_KEYWORDS):
            return True
    return False


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
            except Exception as exc:
                logger.error("Task execution failed completely: %s", exc, exc_info=True)
                if record:
                    record.status = TaskStatus.failed
                    record.summary = f"System error: {exc}"
                try:
                    await self.realtime.set_presence(
                        mode=PresenceMode.error,
                        headline="System fault detected",
                        whisper="Something went wrong, Boss",
                        terminal_text=f"I hit a wall on that one, Boss. Error: {exc}",
                        active_agents=[],
                        current_objective=request.objective if request else None,
                        energy=0.95,
                    )
                except Exception:
                    pass
            finally:
                self._queue.task_done()

    # ──────────────────────────────────────────────
    # FAST-PATH: Skip planner for conversational input
    # ──────────────────────────────────────────────
    async def _execute(self, record: TaskRecord, request: ObjectiveRequest) -> None:
        if _is_conversational(request.objective):
            await self._execute_fast_chat(record, request)
        else:
            await self._execute_full(record, request)

    async def _execute_fast_chat(self, record: TaskRecord, request: ObjectiveRequest) -> None:
        """Direct chat path — no planner, no multi-step. Instant response."""
        memories = self.memory.query(request.objective, limit=3)

        await self.realtime.set_presence(
            mode=PresenceMode.thinking,
            headline="Processing",
            whisper=request.objective,
            terminal_text="One moment, Boss...",
            active_agents=[AgentName.chat],
            current_objective=request.objective,
            energy=0.5,
        )
        record.status = TaskStatus.running
        record.updated_at = utc_now()

        # Single-step plan for bookkeeping
        step = TaskStep(
            title="Respond to Boss",
            agent=AgentName.chat,
            goal=request.objective,
        )
        record.plan = TaskPlan(
            objective=request.objective,
            reasoning="Fast-path conversational response",
            steps=[step],
        )

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
            response = AgentResponse(
                success=False,
                summary=f"Sorry Boss, I hit a snag: {exc}",
                error=str(exc),
            )

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
        record.status = TaskStatus.completed if response.success else TaskStatus.failed
        record.summary = response.summary
        record.updated_at = utc_now()

        # Push conversation to frontend
        await self.realtime.add_conversation(
            role="user",
            text=request.objective,
        )
        await self.realtime.add_conversation(
            role="friday",
            text=response.summary,
        )

        await self.realtime.set_presence(
            mode=PresenceMode.responding,
            headline="FRIDAY",
            whisper="Response ready",
            terminal_text=response.summary,
            active_agents=[],
            current_objective=request.objective,
            energy=0.35,
        )

        if request.store_memory:
            for entry in response.memory_entries:
                self.memory.add(entry["document"], entry.get("metadata", {}))

        await self._journal(record)

        # Return to idle after a beat
        await asyncio.sleep(0.5)
        await self.realtime.set_presence(
            mode=PresenceMode.idle,
            headline="FRIDAY",
            whisper="Standing by, Boss",
            active_agents=[],
            current_objective=None,
            energy=0.15,
        )

    # ──────────────────────────────────────────────
    # FULL PIPELINE: Planner → Agent steps
    # ──────────────────────────────────────────────
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

            presence_mode = PresenceMode.thinking
            if step.agent == AgentName.chat:
                presence_mode = PresenceMode.responding

            await self.realtime.set_presence(
                mode=presence_mode,
                headline=f"{step.agent.value.title()} protocol active",
                whisper=step.title,
                active_agents=[step.agent],
                current_objective=request.objective,
                energy=0.8 if step.agent == AgentName.chat else 0.6,
            )
            response = await self._run_step(record, request, step, memories)

            if response.success:
                await self.realtime.set_presence(
                    mode=presence_mode,
                    headline=f"{step.agent.value.title()} protocol active",
                    whisper=step.title,
                    terminal_text=response.summary,
                    active_agents=[step.agent],
                    current_objective=request.objective,
                    energy=0.5,
                )

            if not response.success:
                record.status = TaskStatus.failed
                await self.realtime.set_presence(
                    mode=PresenceMode.error,
                    headline="Protocol fault",
                    whisper=step.title,
                    terminal_text=response.error or response.summary,
                    active_agents=[AgentName.debug],
                    current_objective=request.objective,
                    energy=0.95,
                )
                break

        if record.status != TaskStatus.failed:
            record.status = TaskStatus.completed

            # FAST PATH: single-step chat — use the output directly
            if len(plan.steps) == 1 and plan.steps[0].agent == AgentName.chat and record.step_results:
                summary = record.step_results[0].output
            else:
                summary = await self._summarize(record)

            record.summary = summary

            await self.realtime.add_conversation(role="friday", text=summary)

            await self.realtime.set_presence(
                mode=PresenceMode.responding,
                headline="Mission complete",
                whisper=request.objective,
                terminal_text=summary,
                active_agents=[],
                current_objective=request.objective,
                energy=0.35,
            )
        else:
            if not record.summary:
                record.summary = await self._summarize(record)
            await self.realtime.add_conversation(
                role="friday",
                text=record.summary or "I wasn't able to complete that one, Boss.",
            )

        if request.store_memory:
            record.learning_note = await self._learning_note(record)
        record.updated_at = utc_now()
        await self._journal(record)
        await self.realtime.set_presence(
            mode=PresenceMode.idle,
            headline="FRIDAY",
            whisper="Standing by, Boss",
            active_agents=[],
            current_objective=None,
            energy=0.15,
        )

    async def _run_step(self, record: TaskRecord, request: ObjectiveRequest, step, memories):
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
        if retry_inputs:
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
        return response

    async def _summarize(self, record: TaskRecord) -> str:
        fallback = "\n".join(f"{item.agent.value}: {item.output}" for item in record.step_results[-5:])[:2000]
        try:
            result = await self.llm.json_response(
                [
                    {
                        "role": "system",
                        "content": (
                            'You are FRIDAY, the AI companion from Iron Man. '
                            'Summarize what you accomplished for the Boss. Be concise, confident, and slightly witty. '
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

    async def _journal(self, record: TaskRecord) -> None:
        self._journal_path.parent.mkdir(parents=True, exist_ok=True)
        with self._journal_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record.model_dump(mode="json"), ensure_ascii=True))
            handle.write("\n")

    def get_task(self, task_id: str) -> TaskRecord | None:
        return self.tasks.get(task_id)

    def list_tasks(self) -> list[TaskRecord]:
        return list(self.tasks.values())[-50:]
