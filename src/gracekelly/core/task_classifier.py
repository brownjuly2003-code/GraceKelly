from __future__ import annotations

import re
from enum import StrEnum


class TaskType(StrEnum):
    CODING = "coding"
    MATH = "math"
    ANALYSIS = "analysis"
    RESEARCH = "research"
    CREATIVE = "creative"
    GENERAL = "general"


_TASK_KEYWORDS: dict[TaskType, tuple[str, ...]] = {
    TaskType.CODING: ("code", "function", "class", "debug", "api", "implement", "python", "javascript", "sql", "bug", "error", "refactor", "compile", "runtime"),
    TaskType.MATH: ("calculate", "equation", "formula", "prove", "theorem", "integral", "derivative", "probability", "algebra", "geometry"),
    TaskType.ANALYSIS: ("analyze", "evaluate", "assess", "review", "audit", "compare", "pros and cons", "trade-off", "benchmark"),
    TaskType.RESEARCH: ("research", "study", "paper", "evidence", "literature", "survey", "findings", "methodology"),
    TaskType.CREATIVE: ("write", "story", "poem", "creative", "design", "imagine", "brainstorm", "narrative", "essay"),
}

_PRIORITY: tuple[TaskType, ...] = (
    TaskType.CODING,
    TaskType.MATH,
    TaskType.ANALYSIS,
    TaskType.RESEARCH,
    TaskType.CREATIVE,
)


def classify_task(prompt: str) -> TaskType:
    if not prompt or not prompt.strip():
        return TaskType.GENERAL
    lower = prompt.lower()
    for task_type in _PRIORITY:
        keywords = _TASK_KEYWORDS[task_type]
        for keyword in keywords:
            if re.search(r"\b" + re.escape(keyword) + r"\b", lower):
                return task_type
    return TaskType.GENERAL
