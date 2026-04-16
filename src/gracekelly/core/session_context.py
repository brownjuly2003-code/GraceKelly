from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gracekelly.config import Settings
    from gracekelly.storage.base import TaskRepository

logger = logging.getLogger(__name__)


def build_session_context(
    repository: TaskRepository,
    session_id: str,
    prompt: str,
    settings: Settings,
) -> str:
    try:
        turns = repository.list_by_session(session_id, limit=settings.context_window_turns)
    except Exception:
        logger.debug("Failed to load session context for %s", session_id)
        return prompt
    if not turns:
        return prompt
    history_lines: list[str] = []
    for idx, turn in enumerate(turns, 1):
        history_lines.append(
            f"[Turn {idx}]\nUser: {turn.prompt or ''}\nAssistant: {turn.output_text or '(no response)'}"
        )
    context_prefix = "\n\n".join(history_lines)
    max_chars = settings.max_context_chars
    if len(context_prefix) > max_chars:
        trimmed: list[str] = []
        total = 0
        for line in reversed(context_prefix.split("\n")):
            if total + len(line) + 1 > max_chars:
                break
            trimmed.append(line)
            total += len(line) + 1
        context_prefix = "\n".join(reversed(trimmed))
        logger.info("Session context trimmed to %d chars (max %d)", len(context_prefix), max_chars)
    return f"{context_prefix}\n\n[Current]\nUser: {prompt}"
