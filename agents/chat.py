from __future__ import annotations

from agents.base import AgentContext, AgentResponse, BaseAgent
from core.models import AgentName


class ChatAgent(BaseAgent):
    """Conversational agent — responds directly using the LLM without tools."""

    name = AgentName.chat
    description = "Has a direct conversation with the user using the LLM. Best for greetings, questions, explanations, and general chat."

    async def run(self, context: AgentContext) -> AgentResponse:
        await self.emit(context.task_id, "chat_started", {"objective": context.objective})

        # Build conversational context from previous results
        history_lines = []
        for prev in context.previous_results[-5:]:
            history_lines.append(f"[{prev.agent.value}]: {prev.output[:300]}")
        history_block = "\n".join(history_lines) if history_lines else "No previous context."

        memories_block = "\n".join(
            f"- {m.document[:200]}" for m in context.memories[:3]
        ) if context.memories else "No relevant memories."

        raw = await self.fast_llm.chat(
            [
                {
                    "role": "system",
                    "content": (
                        "You are FRIDAY, an advanced local AI assistant running on the user's machine. "
                        "You are helpful, concise, and professional. "
                        "Respond naturally to the user. Do NOT return JSON. "
                        "If you don't know something, say so honestly."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Objective: {context.objective}\n\n"
                        f"Previous context:\n{history_block}\n\n"
                        f"Relevant memories:\n{memories_block}\n\n"
                        f"Additional context: {context.task_context}"
                    ),
                },
            ]
        )

        await self.emit(context.task_id, "chat_finished", {"length": len(raw)})
        return AgentResponse(
            success=True,
            summary=raw.strip()[:2000],
            data={"response": raw.strip()},
            memory_entries=[
                {
                    "document": f"Chat about '{context.objective}': {raw.strip()[:500]}",
                    "metadata": {"agent": self.name.value, "type": "conversation"},
                }
            ],
        )
