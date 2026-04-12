from __future__ import annotations

import re


TASK_KEYWORDS = frozenset(
    {
        "search",
        "research",
        "scrape",
        "web",
        "browse",
        "internet",
        "image",
        "visual",
        "art",
        "render",
        "draw",
        "picture",
        "generate",
        "transcribe",
        "dictation",
        "record",
        "browser",
        "open app",
        "launch",
        "automation",
        "run",
        "execute",
        "script",
        "code",
        "compile",
        "build",
        "install",
        "file",
        "folder",
        "directory",
        "delete",
        "create",
        "move",
        "copy",
        "download",
        "upload",
        "deploy",
    }
)


def is_conversational(objective: str) -> bool:
    lower = objective.lower().strip()
    if len(lower.split()) <= 4 and not any(keyword in lower for keyword in TASK_KEYWORDS):
        return True
    if re.match(r"^(hey|hi|hello|yo|sup|good morning|good evening|good night|thanks|thank you|bye|goodbye)", lower):
        return True
    if re.match(r"^(who|what|why|how|when|where|can you|could you|tell me|explain|describe)", lower):
        return not any(keyword in lower for keyword in TASK_KEYWORDS)
    return False
