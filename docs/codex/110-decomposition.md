# 110: Task Decomposition Module — TODO

Phase 8 (Task Decomposition). Dependency: complexity.py exists.
Complexity: moderate | Runs: 2

```
## GOAL
Create a task decomposition module that breaks complex prompts into subtasks and synthesizes results. Two new files: `src/gracekelly/core/decomposition.py` and `tests/test_decomposition.py`.

## CONTEXT
Files to CREATE:
- `src/gracekelly/core/decomposition.py` — decomposition logic
- `tests/test_decomposition.py` — unit tests

Files to READ (do NOT modify):
- `src/gracekelly/core/complexity.py` — ComplexityLevel, assess_complexity()
- `src/gracekelly/core/roles.py` — RoleType (DECOMPOSER, SYNTHESIZER)

Architecture:
- Python >=3.11, no external dependencies
- Decomposition uses a callback (execute_fn) to call LLM for decomposition and synthesis
- Tests mock the LLM callback
- Test runner: `python -m pytest tests/test_decomposition.py -q`

## CONSTRAINTS
- Create ONLY the two files listed above. Do NOT modify any existing files.
- Follow these instructions EXACTLY.
- Do NOT add: logging, comments, docstrings, async support.
- Preserve project code style: 4-space indentation, snake_case, `from __future__ import annotations`.

### decomposition.py specification

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable

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
```

That is the COMPLETE implementation. Copy it exactly.

### test_decomposition.py specification

Exactly these tests:

1. `test_simple_prompt_not_decomposed` — "What is 2+2?" → was_decomposed=False, 1 subtask
2. `test_simple_prompt_no_llm_decomposition_call` — simple prompt → execute_fn called only once (for execution, not decomposition)
3. `test_complex_prompt_decomposed` — complex prompt + execute_fn returns JSON array of 3 → was_decomposed=True, 3 subtasks
4. `test_decompose_invalid_json_fallback` — execute_fn returns "not json" → fallback to 1 subtask
5. `test_decompose_empty_array_fallback` — execute_fn returns "[]" → fallback to 1 subtask
6. `test_subtask_index_sequential` — 3 subtasks → indices [0, 1, 2]
7. `test_synthesis_called_when_decomposed` — was_decomposed=True → execute_fn called extra time for synthesis
8. `test_no_synthesis_when_not_decomposed` — was_decomposed=False → no synthesis call
9. `test_final_answer_is_synthesis` — decomposed → final_answer is the synthesis result
10. `test_final_answer_is_direct_when_simple` — not decomposed → final_answer is the direct answer
11. `test_result_is_frozen` — DecompositionResult is frozen
12. `test_subtask_is_frozen` — SubTask is frozen
13. `test_execute_fn_call_count_decomposed` — 3 subtasks → execute_fn called 5 times (1 decompose + 3 execute + 1 synthesize)
14. `test_complexity_level_preserved` — result.complexity_level matches assess_complexity()

End with:
```python
if __name__ == "__main__":
    unittest.main()
```

## DONE WHEN
- [ ] `src/gracekelly/core/decomposition.py` exists
- [ ] `tests/test_decomposition.py` exists with exactly 14 test methods
- [ ] `python -m pytest tests/test_decomposition.py -q` → 14 passed, 0 failed
- [ ] `python -m pytest -q` → all existing tests still pass (631+)
- [ ] No other files created or modified

## SELF-EVALUATION
After completing, score yourself 1-10. Target: 9.8/10.
```
