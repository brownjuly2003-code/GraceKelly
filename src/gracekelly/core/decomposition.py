from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass

from gracekelly.core.complexity import ComplexityLevel, assess_complexity


@dataclass(frozen=True, slots=True)
class SubTask:
    index: int
    prompt: str


@dataclass(frozen=True, slots=True)
class DecompositionResult:
    original_prompt: str
    complexity_level: ComplexityLevel
    was_decomposed: bool
    subtasks: tuple[SubTask, ...]
    subtask_results: tuple[str, ...]
    final_answer: str


_DECOMPOSE_PROMPT = (
    "Break this question into independent sub-questions. "
    "Return a JSON array of strings, each being one sub-question. "
    "If the question is simple and doesn't need decomposition, return [\"<original question>\"]. "
    "Return ONLY the JSON array, no other text.\n\n"
    "Question: {prompt}"
)

_SYNTHESIZE_PROMPT = (
    "Combine these answers into one comprehensive response.\n\n"
    "Original question: {prompt}\n\n"
    "{answers}"
)


def decompose_prompt(prompt: str, execute_fn: Callable[[str], str]) -> list[SubTask]:
    assessment = assess_complexity(prompt)
    if assessment.level == ComplexityLevel.SIMPLE:
        return [SubTask(index=0, prompt=prompt)]

    decompose_request = _DECOMPOSE_PROMPT.format(prompt=prompt)
    raw_response = execute_fn(decompose_request)

    try:
        subtask_prompts = json.loads(raw_response)
        if not isinstance(subtask_prompts, list) or not subtask_prompts:
            return [SubTask(index=0, prompt=prompt)]
        return [
            SubTask(index=i, prompt=str(p))
            for i, p in enumerate(subtask_prompts)
        ]
    except (json.JSONDecodeError, TypeError):
        return [SubTask(index=0, prompt=prompt)]


def execute_decomposed(
    prompt: str,
    execute_fn: Callable[[str], str],
) -> DecompositionResult:
    subtasks = decompose_prompt(prompt, execute_fn)
    was_decomposed = len(subtasks) > 1

    subtask_results: list[str] = []
    for subtask in subtasks:
        result = execute_fn(subtask.prompt)
        subtask_results.append(result)

    if was_decomposed:
        answers_text = "\n\n---\n\n".join(
            f"Sub-question {i + 1}: {subtasks[i].prompt}\nAnswer: {r}"
            for i, r in enumerate(subtask_results)
        )
        synthesis_prompt = _SYNTHESIZE_PROMPT.format(
            prompt=prompt,
            answers=answers_text,
        )
        final_answer = execute_fn(synthesis_prompt)
    else:
        final_answer = subtask_results[0]

    assessment = assess_complexity(prompt)
    return DecompositionResult(
        original_prompt=prompt,
        complexity_level=assessment.level,
        was_decomposed=was_decomposed,
        subtasks=tuple(subtasks),
        subtask_results=tuple(subtask_results),
        final_answer=final_answer,
    )
