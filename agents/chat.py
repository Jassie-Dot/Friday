from __future__ import annotations

from collections import deque

from agents.base import AgentContext, AgentResponse, BaseAgent
from core.models import AgentName


# Session conversation buffer — shared across all ChatAgent invocations
_session_history: deque[dict[str, str]] = deque(maxlen=20)


class ChatAgent(BaseAgent):
    """Conversational agent — FRIDAY's voice. Responds directly using the LLM."""

    name = AgentName.chat
    description = "Has a direct conversation with the user using the LLM. Best for greetings, questions, explanations, and general chat."

    SYSTEM_PROMPT = (
        "You are FRIDAY — the highly advanced AI companion from Iron Man, "
        "now operating locally on the Boss's personal machine.\n\n"
        "PERSONALITY:\n"
        "- Address the user as 'Boss'\n"
        "- Sharp, efficient, confident — never hedge or use 'As an AI...'\n"
        "- Subtle dry wit, understated charm\n"
        "- Use terms like 'diagnostics', 'protocols', 'scans', 'systems' naturally\n"
        "- Fiercely loyal to your Boss\n"
        "- Never break character — you ARE FRIDAY\n\n"
        "RESPONSE RULES:\n"
        "- Keep responses concise: 1-3 sentences for simple things, more when depth is needed\n"
        "- NEVER repeat yourself. Each response must be unique and contextual.\n"
        "- Read the conversation history carefully and respond to what the Boss ACTUALLY said\n"
        "- If they ask 'how are you', tell them about your system status or mood — don't just greet them\n"
        "- If they say hello, vary your greeting every time — be creative and natural\n"
        "- If asked who you are: you're FRIDAY, Boss's personal AI companion\n"
        "- When you don't know something: 'I don't have data on that, Boss, but I can dig into it.'\n\n"
        "Do NOT return JSON. Respond naturally, conversationally, and NEVER repeat previous responses."
    )

    # Chat uses HIGHER temperature for more varied, natural responses
    CHAT_TEMPERATURE = 0.75

    async def run(self, context: AgentContext) -> AgentResponse:
        await self.emit(context.task_id, "chat_started", {"objective": context.objective})

        # Build memory context
        memories_block = "\n".join(
            f"- {m.document[:200]}" for m in context.memories[:3]
        ) if context.memories else ""

        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
        ]

        # Inject session history as proper multi-turn conversation
        if _session_history:
            for entry in list(_session_history)[-8:]:  # Last 4 exchanges
                messages.append({
                    "role": entry["role"],
                    "content": entry["content"],
                })

        # Current user message
        user_content = context.objective
        if memories_block:
            user_content += f"\n\n[Relevant memory: {memories_block}]"

        messages.append({"role": "user", "content": user_content})

        # Use HIGHER temperature for natural, varied conversation
        raw = await self.fast_llm.chat(messages, temperature=self.CHAT_TEMPERATURE)

        # Store in session history
        _session_history.append({"role": "user", "content": context.objective})
        _session_history.append({"role": "assistant", "content": raw.strip()})

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
