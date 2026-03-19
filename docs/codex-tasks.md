# Задачи для OpenAI Codex

Проект: `D:\GraceKelly` — Python LLM orchestrator.
Дата: 2026-03-19.

---

## Задача 1/3: Role System [moderate]

Рекомендация: 2 параллельных запуска, выбрать лучший.

```
## GOAL
Create a role system for LLM orchestration: 6 specialized roles with system prompts, preferred models, and a formatting function. Two new files: `src/gracekelly/core/roles.py` and `tests/test_roles.py`.

## CONTEXT
Files to CREATE:
- `src/gracekelly/core/roles.py` — role definitions and helpers
- `tests/test_roles.py` — unit tests

Files to READ (do NOT modify):
- `src/gracekelly/core/models.py` — contains MODEL_SPECS tuple with model IDs: "mistral-small", "gpt-5-4-api", "claude-sonnet-4-6-api", "best", "sonar", "claude-sonnet-4-6", "gpt-5-4", "gemini-3-1-pro", "claude-opus-4-6", "thinking", "max", "nemotron-3-super", "kimi-k2-5"
- `src/gracekelly/core/contracts.py` — uses StrEnum, frozen dataclasses with slots=True

Architecture:
- Python >=3.11, no external dependencies for this task
- All files start with `from __future__ import annotations`
- Dataclasses use `@dataclass(frozen=True, slots=True)`
- Enums inherit from `StrEnum`
- Tests use `unittest.TestCase` (not pytest classes)
- Test runner: `python -m pytest tests/test_roles.py -q`

## CONSTRAINTS
- Create ONLY the two files listed above. Do NOT modify any existing files.
- Follow these instructions EXACTLY. Do NOT deviate, improve, or "enhance" beyond what is specified.
- Do NOT add: try/catch blocks, input validation, logging, comments, or docstrings — unless explicitly listed below.
- Simpler is better. No abstractions, no base classes, no registries.
- Preserve project code style: double quotes for strings in non-prompt text, single quotes acceptable inside prompt strings, 4-space indentation, snake_case naming, trailing commas in multi-line structures.

### roles.py specification

```python
from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum

class RoleType(StrEnum):
    VERIFIER = "verifier"
    SYNTHESIZER = "synthesizer"
    JUDGE = "judge"
    DEVIL_ADVOCATE = "devil_advocate"
    FACT_VERIFIER = "fact_verifier"
    DECOMPOSER = "decomposer"

@dataclass(frozen=True, slots=True)
class Role:
    role_type: RoleType
    system_prompt: str
    preferred_models: tuple[str, ...]
    reasoning_required: bool
```

System prompts (English, 3-5 sentences each):
- VERIFIER: "You are a verification specialist. Review the given answer for accuracy, completeness, and logical consistency. Identify any unsupported claims, missing context, or logical errors. Provide a structured assessment with specific issues found."
- SYNTHESIZER: "You are a synthesis specialist. Combine multiple answers into one coherent, comprehensive response. Preserve the strongest points from each source while eliminating redundancy. The final answer should be better than any individual input."
- JUDGE: "You are an impartial quality judge. Evaluate the given answer on a scale of 1-10 across these dimensions: factual accuracy, completeness, clarity, and relevance. Provide specific scores and brief justification for each dimension."
- DEVIL_ADVOCATE: "You are a devil's advocate. Challenge the given answer by finding weaknesses, counterarguments, and edge cases. Your goal is to stress-test the reasoning, not to be contrarian. Highlight genuine vulnerabilities."
- FACT_VERIFIER: "You are a fact-checking specialist. Examine each factual claim in the given answer. For each claim, assess whether it is verifiable, likely accurate, potentially misleading, or demonstrably false. Flag any claims that require citations."
- DECOMPOSER: "You are a task decomposition specialist. Break down the given complex question into independent, answerable sub-questions. Each sub-question should be self-contained and contribute to answering the original question. Return a numbered list."

Preferred models:
- VERIFIER: ("claude-sonnet-4-6-api", "gpt-5-4-api")
- SYNTHESIZER: ("claude-sonnet-4-6-api",)
- JUDGE: ("gpt-5-4-api", "claude-sonnet-4-6-api")
- DEVIL_ADVOCATE: ("gpt-5-4-api",)
- FACT_VERIFIER: ("claude-sonnet-4-6-api", "gpt-5-4-api")
- DECOMPOSER: ("claude-sonnet-4-6-api",)

All roles: reasoning_required = True

Functions:
```python
ROLES: dict[RoleType, Role] = { ... }  # all 6 roles

def get_role(role_type: RoleType) -> Role:
    return ROLES[role_type]

def format_prompt_with_role(role: Role, user_prompt: str) -> dict[str, str]:
    return {"system": role.system_prompt, "user": user_prompt}
```

### test_roles.py specification

Exactly these tests, using `unittest.TestCase`:

1. `test_all_role_types_have_definitions` — every RoleType value is in ROLES dict
2. `test_role_count_matches_enum` — len(ROLES) == len(RoleType)
3. `test_all_system_prompts_are_nonempty` — every role.system_prompt has len > 20
4. `test_all_preferred_models_are_valid` — every model ID in preferred_models exists in MODEL_SPECS (import from gracekelly.core.models)
5. `test_all_roles_require_reasoning` — every role.reasoning_required is True
6. `test_get_role_returns_correct_type` — get_role(RoleType.JUDGE).role_type == RoleType.JUDGE
7. `test_get_role_raises_on_invalid` — get_role("nonexistent") raises KeyError
8. `test_format_prompt_structure` — format_prompt_with_role returns dict with exactly keys "system" and "user"
9. `test_format_prompt_preserves_user_prompt` — returned dict["user"] == original prompt
10. `test_format_prompt_uses_role_system_prompt` — returned dict["system"] == role.system_prompt
11. `test_roles_are_frozen` — assigning role.system_prompt = "x" raises FrozenInstanceError
12. `test_verifier_system_prompt_contains_accuracy` — "accuracy" in get_role(RoleType.VERIFIER).system_prompt
13. `test_devil_advocate_system_prompt_contains_challenge` — "challenge" or "weakness" in prompt
14. `test_decomposer_system_prompt_contains_break_down` — "break down" or "sub-question" in prompt
15. `test_role_type_is_str_enum` — RoleType.VERIFIER == "verifier" (StrEnum behavior)

End with:
```python
if __name__ == "__main__":
    unittest.main()
```

## DONE WHEN
- [ ] `src/gracekelly/core/roles.py` exists with RoleType enum (6 values), Role dataclass, ROLES dict, get_role(), format_prompt_with_role()
- [ ] `tests/test_roles.py` exists with exactly 15 test methods in one TestCase class
- [ ] `python -m pytest tests/test_roles.py -q` → 15 passed, 0 failed
- [ ] `python -m pytest -q` → all existing tests still pass (419+)
- [ ] No other files created or modified

## SELF-EVALUATION
After completing the task, evaluate your own work on a scale of 1-10:
- Does the code follow the exact specification? (frozen dataclass, StrEnum, specific prompts)
- Are all 15 tests present and meaningful?
- Does the code style match the project? (from __future__, slots=True, snake_case)
- Are there any unnecessary additions (comments, docstrings, error handling)?

If your self-score is below 9.8/10, identify what's missing and fix it before submitting. Target: 9.8/10.
```

---

## Задача 2/3: Prompt Variation Generator [routine]

Рекомендация: 1 запуск.

```
## GOAL
Create a prompt variation generator that produces rephrased versions of a user prompt using 9 fixed templates. Two new files: `src/gracekelly/core/prompt_variations.py` and `tests/test_prompt_variations.py`.

## CONTEXT
Files to CREATE:
- `src/gracekelly/core/prompt_variations.py` — generator class
- `tests/test_prompt_variations.py` — unit tests

Files to READ (do NOT modify):
- `src/gracekelly/core/models.py` — for code style reference only

Architecture:
- Python >=3.11, no external dependencies
- All files start with `from __future__ import annotations`
- Tests use `unittest.TestCase`
- Test runner: `python -m pytest tests/test_prompt_variations.py -q`

## CONSTRAINTS
- Create ONLY the two files listed above. Do NOT modify any existing files.
- Follow these instructions EXACTLY. Do NOT add features, optimizations, or "improvements".
- Do NOT add: try/catch blocks, logging, comments, docstrings, type guards, or input validation beyond the one ValueError specified below.
- No classes needed — plain functions are sufficient.
- Preserve project code style: 4-space indentation, snake_case, `from __future__ import annotations`.

### prompt_variations.py specification

```python
from __future__ import annotations

_TEMPLATES: tuple[str, ...] = (
    "{prompt}",
    "Explain step by step: {prompt}",
    "Consider multiple perspectives on: {prompt}",
    "What are the key facts about: {prompt}",
    "Provide a detailed analysis of: {prompt}",
    "Summarize the current understanding of: {prompt}",
    "What would experts say about: {prompt}",
    "Break down the following topic: {prompt}",
    "Give a comprehensive answer to: {prompt}",
)


def generate_variations(prompt: str, count: int = 3) -> list[str]:
    if not prompt or not prompt.strip():
        raise ValueError("Prompt must not be empty.")
    results: list[str] = []
    for i in range(count):
        template = _TEMPLATES[i % len(_TEMPLATES)]
        results.append(template.format(prompt=prompt))
    return results
```

That is the COMPLETE implementation. Copy it exactly.

### test_prompt_variations.py specification

Exactly these tests:

1. `test_default_count_is_three` — generate_variations("test") returns list of length 3
2. `test_first_variation_is_original` — generate_variations("hello")[0] == "hello"
3. `test_three_variations_are_unique` — len(set(generate_variations("test", 3))) == 3
4. `test_nine_variations_all_unique` — len(set(generate_variations("test", 9))) == 9
5. `test_count_one_returns_original` — generate_variations("hello", 1) == ["hello"]
6. `test_count_twelve_cycles_templates` — len(generate_variations("x", 12)) == 12 and result[0] == result[9]
7. `test_empty_prompt_raises_value_error` — generate_variations("") raises ValueError
8. `test_whitespace_prompt_raises_value_error` — generate_variations("   ") raises ValueError
9. `test_all_variations_contain_prompt_text` — every item in generate_variations("quantum", 9) contains "quantum"
10. `test_second_variation_starts_with_explain` — generate_variations("test", 2)[1].startswith("Explain step by step:")

End with:
```python
if __name__ == "__main__":
    unittest.main()
```

## DONE WHEN
- [ ] `src/gracekelly/core/prompt_variations.py` exists with `_TEMPLATES` tuple and `generate_variations()` function
- [ ] `tests/test_prompt_variations.py` exists with exactly 10 test methods
- [ ] `python -m pytest tests/test_prompt_variations.py -q` → 10 passed, 0 failed
- [ ] `python -m pytest -q` → all existing tests still pass (419+)
- [ ] No other files created or modified

## SELF-EVALUATION
After completing, score yourself 1-10:
- Is the implementation EXACTLY as specified above? (copy the code, don't rewrite)
- Are all 10 tests present with correct assertions?
- Is there any code beyond what was specified? (if yes, remove it)

If your self-score is below 9.8/10, fix issues before submitting. Target: 9.8/10.
```

---

## Задача 3/3: Task Classifier [moderate]

Рекомендация: 2 параллельных запуска, выбрать лучший.

```
## GOAL
Create a keyword-based task classifier that categorizes user prompts into 6 task types. Two new files: `src/gracekelly/core/task_classifier.py` and `tests/test_task_classifier.py`.

## CONTEXT
Files to CREATE:
- `src/gracekelly/core/task_classifier.py` — classifier
- `tests/test_task_classifier.py` — unit tests

Files to READ (do NOT modify):
- `src/gracekelly/core/contracts.py` — for StrEnum pattern reference

Architecture:
- Python >=3.11, no external dependencies (use only `re` from stdlib)
- All files start with `from __future__ import annotations`
- Enums inherit from `StrEnum` (import from `enum`)
- Tests use `unittest.TestCase`
- Test runner: `python -m pytest tests/test_task_classifier.py -q`

## CONSTRAINTS
- Create ONLY the two files listed above. Do NOT modify any existing files.
- Follow these instructions EXACTLY. Do NOT deviate, improve, or "enhance".
- Do NOT add: try/catch blocks, logging, comments, docstrings, ML models, or NLP libraries.
- Do NOT use nltk, spacy, sklearn, or any external package. Only `re` from stdlib.
- Preserve project code style: 4-space indentation, snake_case, `from __future__ import annotations`.
- Word matching must use word boundaries (`\b`) to avoid matching substrings (e.g., "code" should NOT match "decode").

### task_classifier.py specification

```python
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


# Priority order: CODING > MATH > ANALYSIS > RESEARCH > CREATIVE > GENERAL
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
```

That is the COMPLETE implementation. Copy it exactly.

### test_task_classifier.py specification

Exactly these tests:

1. `test_python_function_is_coding` — classify_task("Write a Python function to sort a list") == TaskType.CODING
2. `test_debug_is_coding` — classify_task("Debug this error in my code") == TaskType.CODING
3. `test_calculate_integral_is_math` — classify_task("Calculate the integral of x^2") == TaskType.MATH
4. `test_prove_theorem_is_math` — classify_task("Prove the Pythagorean theorem") == TaskType.MATH
5. `test_analyze_market_is_analysis` — classify_task("Analyze market trends for Q4") == TaskType.ANALYSIS
6. `test_compare_is_analysis` — classify_task("Compare React and Vue frameworks") == TaskType.ANALYSIS
7. `test_research_papers_is_research` — classify_task("Research papers on transformer architectures") == TaskType.RESEARCH
8. `test_write_poem_is_creative` — classify_task("Write a poem about spring") == TaskType.CREATIVE
9. `test_brainstorm_is_creative` — classify_task("Brainstorm ideas for a startup") == TaskType.CREATIVE
10. `test_hello_world_is_general` — classify_task("Hello, how are you?") == TaskType.GENERAL
11. `test_case_insensitive` — classify_task("WRITE PYTHON CODE") == TaskType.CODING
12. `test_coding_beats_creative` — classify_task("Write code for a game") == TaskType.CODING (priority: CODING > CREATIVE)
13. `test_coding_beats_analysis` — classify_task("Analyze this code for bugs") == TaskType.CODING
14. `test_empty_string_is_general` — classify_task("") == TaskType.GENERAL
15. `test_whitespace_is_general` — classify_task("   ") == TaskType.GENERAL
16. `test_word_boundary_no_substring` — classify_task("I need to decode this message") == TaskType.GENERAL (not CODING — "decode" contains "code" but word boundary prevents match)
17. `test_task_type_is_str_enum` — TaskType.CODING == "coding"
18. `test_all_task_types_count` — len(TaskType) == 6

End with:
```python
if __name__ == "__main__":
    unittest.main()
```

## DONE WHEN
- [ ] `src/gracekelly/core/task_classifier.py` exists with TaskType enum, _TASK_KEYWORDS dict, classify_task() function
- [ ] `tests/test_task_classifier.py` exists with exactly 18 test methods
- [ ] `python -m pytest tests/test_task_classifier.py -q` → 18 passed, 0 failed
- [ ] `python -m pytest -q` → all existing tests still pass (419+)
- [ ] No other files created or modified
- [ ] classify_task("I need to decode this") returns GENERAL, not CODING

## SELF-EVALUATION
After completing, score yourself 1-10:
- Is the implementation EXACTLY as specified? (no extra functions, no ML, no comments)
- Do all 18 tests pass, especially test 16 (word boundary)?
- Is there any code beyond the specification? (if yes, remove it)
- Does `re.search(r"\b" + re.escape(keyword) + r"\b", lower)` correctly handle multi-word keywords like "pros and cons"?

If your self-score is below 9.8/10, identify gaps and fix before submitting. Target: 9.8/10.
```

---

## Общие инструкции для всех задач

**Платформа**: Windows 11, Python 3.13, проект в `D:\GraceKelly`.
**pytest config**: `pyproject.toml` уже содержит `pythonpath = ["src"]` — импорты работают без `pip install -e`.
**Проверка**: `python -m pytest -q` (вся suite должна остаться зелёной: 419+ passed).

**Стиль проекта**:
- `from __future__ import annotations` — первая строка каждого .py файла
- `@dataclass(frozen=True, slots=True)` для immutable data
- `StrEnum` для перечислений (не обычный Enum)
- `unittest.TestCase` для тестов (не голые функции pytest)
- 4 пробела отступ
- snake_case для переменных и функций
- Без docstrings, без комментариев (кроме где явно указано)
