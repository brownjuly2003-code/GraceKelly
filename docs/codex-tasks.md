# Задачи для OpenAI Codex

Проект: `D:\GraceKelly` — Python LLM orchestrator.
Дата: 2026-03-19. Обновлено: 2026-03-19 (добавлены задачи 4-8).

Задачи 1-3: строительные блоки Phase 7 (roles), Phase 6 (prompt variations), Phase 10 (task classifier). **DONE** ✓
Задачи 4-8: строительные блоки Phase 6 (consensus), Phase 8 (complexity), Phase 9 (reliability, patterns), Phase 10 (model stats). **DONE** ✓
Задача 9: установка и оценка внешних скиллов из skills.sh.

---

## Задача 1/8: Role System [moderate]

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

## Задача 2/8: Prompt Variation Generator [routine]

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

## Задача 3/8: Task Classifier [moderate]

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

## Задача 4/8: Consensus Data Structures [routine]

Рекомендация: 1 запуск.

```
## GOAL
Create data structures for the consensus engine: configuration, cluster info, and consensus result. Two new files: `src/gracekelly/core/consensus.py` and `tests/test_consensus.py`.

## CONTEXT
Files to CREATE:
- `src/gracekelly/core/consensus.py` — consensus data structures and helpers
- `tests/test_consensus.py` — unit tests

Files to READ (do NOT modify):
- `src/gracekelly/core/contracts.py` — for frozen dataclass + StrEnum pattern reference
- `src/gracekelly/core/execution_profile.py` — for code style reference

Architecture:
- Python >=3.11, no external dependencies for this task
- All files start with `from __future__ import annotations`
- Dataclasses use `@dataclass(frozen=True, slots=True)`
- Tests use `unittest.TestCase`
- Test runner: `python -m pytest tests/test_consensus.py -q`

## CONSTRAINTS
- Create ONLY the two files listed above. Do NOT modify any existing files.
- Follow these instructions EXACTLY. Do NOT deviate, improve, or "enhance" beyond what is specified.
- Do NOT add: try/catch blocks, logging, comments, docstrings, or input validation beyond what is specified below.
- Do NOT add clustering algorithms, sklearn imports, or embedding logic. This task creates ONLY data structures.
- Preserve project code style: 4-space indentation, snake_case, `from __future__ import annotations`, trailing commas in multi-line structures.

### consensus.py specification

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConsensusConfig:
    similarity_threshold: float = 0.85
    consensus_target: float = 0.95
    max_rounds: int = 5
    variations_per_round: int = 3
    enable_peer_review: bool = False
    enable_confidence: bool = True


@dataclass(frozen=True, slots=True)
class ClusterInfo:
    cluster_id: int
    member_indices: tuple[int, ...]
    centroid_index: int
    size: int
    avg_similarity: float


@dataclass(frozen=True, slots=True)
class ConsensusResult:
    consensus_score: float
    num_clusters: int
    top_cluster: ClusterInfo
    all_clusters: tuple[ClusterInfo, ...]
    needs_debate: bool
    round_number: int
    total_responses: int


def needs_another_round(result: ConsensusResult, config: ConsensusConfig) -> bool:
    return (
        result.needs_debate
        and result.round_number < config.max_rounds
    )


def build_consensus_result(
    clusters: list[ClusterInfo],
    round_number: int,
    total_responses: int,
    config: ConsensusConfig,
) -> ConsensusResult:
    if not clusters:
        raise ValueError("At least one cluster is required.")
    sorted_clusters = sorted(clusters, key=lambda c: c.size, reverse=True)
    top = sorted_clusters[0]
    consensus_score = top.size / total_responses if total_responses > 0 else 0.0
    return ConsensusResult(
        consensus_score=consensus_score,
        num_clusters=len(clusters),
        top_cluster=top,
        all_clusters=tuple(sorted_clusters),
        needs_debate=consensus_score < config.consensus_target,
        round_number=round_number,
        total_responses=total_responses,
    )
```

That is the COMPLETE implementation. Copy it exactly.

### test_consensus.py specification

Exactly these tests:

1. `test_default_config_values` — ConsensusConfig() has similarity_threshold=0.85, consensus_target=0.95, max_rounds=5, variations_per_round=3, enable_peer_review=False, enable_confidence=True
2. `test_config_custom_values` — ConsensusConfig(similarity_threshold=0.9, consensus_target=0.8) has correct values
3. `test_config_is_frozen` — assigning config.max_rounds = 10 raises FrozenInstanceError
4. `test_cluster_info_creation` — ClusterInfo(cluster_id=0, member_indices=(0, 1, 2), centroid_index=1, size=3, avg_similarity=0.92) has correct values
5. `test_cluster_info_is_frozen` — assigning cluster.size = 5 raises FrozenInstanceError
6. `test_consensus_result_creation` — create a ConsensusResult with consensus_score=0.8 and verify all fields
7. `test_consensus_result_needs_debate_true` — consensus_score=0.5 with default config → needs_debate=True
8. `test_consensus_result_needs_debate_false` — consensus_score=0.96 with default config → needs_debate=False
9. `test_needs_another_round_true` — needs_debate=True, round_number=1, max_rounds=5 → True
10. `test_needs_another_round_false_converged` — needs_debate=False → False
11. `test_needs_another_round_false_max_rounds` — needs_debate=True, round_number=5, max_rounds=5 → False
12. `test_build_consensus_result_single_cluster` — 1 cluster with 5 members, total=5 → consensus_score=1.0, needs_debate=False
13. `test_build_consensus_result_multiple_clusters` — 2 clusters (3+2 members), total=5 → consensus_score=0.6, needs_debate=True
14. `test_build_consensus_result_sorts_by_size` — pass clusters in wrong order, verify top_cluster is the largest
15. `test_build_consensus_result_empty_raises` — build_consensus_result([], ...) raises ValueError

End with:
```python
if __name__ == "__main__":
    unittest.main()
```

## DONE WHEN
- [ ] `src/gracekelly/core/consensus.py` exists with ConsensusConfig, ClusterInfo, ConsensusResult, needs_another_round(), build_consensus_result()
- [ ] `tests/test_consensus.py` exists with exactly 15 test methods
- [ ] `python -m pytest tests/test_consensus.py -q` → 15 passed, 0 failed
- [ ] `python -m pytest -q` → all existing tests still pass (419+)
- [ ] No other files created or modified

## SELF-EVALUATION
After completing, score yourself 1-10:
- Is the implementation EXACTLY as specified? (copy the code, don't add clustering)
- Are all 15 tests present with correct assertions?
- Is there any code beyond the specification? (remove it)

If your self-score is below 9.8/10, fix issues before submitting. Target: 9.8/10.
```

---

## Задача 5/8: Complexity Assessor [moderate]

Рекомендация: 2 параллельных запуска, выбрать лучший.

```
## GOAL
Create a keyword-based complexity assessor that evaluates whether a user prompt is simple, moderate, or complex, and whether it should be decomposed into subtasks. Two new files: `src/gracekelly/core/complexity.py` and `tests/test_complexity.py`.

## CONTEXT
Files to CREATE:
- `src/gracekelly/core/complexity.py` — complexity assessment logic
- `tests/test_complexity.py` — unit tests

Files to READ (do NOT modify):
- `src/gracekelly/core/contracts.py` — for StrEnum pattern
- `src/gracekelly/core/task_classifier.py` — for code style reference (if it exists; if not, use contracts.py)

Architecture:
- Python >=3.11, no external dependencies (use only `re` from stdlib)
- All files start with `from __future__ import annotations`
- Enums inherit from `StrEnum`
- Tests use `unittest.TestCase`
- Test runner: `python -m pytest tests/test_complexity.py -q`

## CONSTRAINTS
- Create ONLY the two files listed above. Do NOT modify any existing files.
- Follow these instructions EXACTLY. Do NOT deviate, improve, or "enhance".
- Do NOT add: try/catch blocks, logging, comments, docstrings, ML models, or NLP libraries.
- Do NOT use nltk, spacy, sklearn, or any external package. Only `re` from stdlib.
- Preserve project code style: 4-space indentation, snake_case, `from __future__ import annotations`.
- Word matching must use word boundaries (`\b`) to avoid substring matching.

### complexity.py specification

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class ComplexityLevel(StrEnum):
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


_COMPLEXITY_INDICATORS: tuple[str, ...] = (
    "compare",
    "analyze",
    "evaluate",
    "trade-off",
    "pros and cons",
    "step by step",
    "multiple",
    "different perspectives",
    "comprehensive",
    "in-depth",
    "detailed analysis",
    "implications",
    "consequences",
    "relationship between",
    "how does .+ affect",
    "explain the difference",
    "advantages and disadvantages",
    "critically assess",
)

_DECOMPOSITION_SIGNALS: tuple[str, ...] = (
    "and also",
    "additionally",
    "furthermore",
    "as well as",
    "along with",
    "on top of that",
    "not only .+ but also",
    "first .+ then .+ finally",
    "both .+ and",
    "several",
    "multiple aspects",
)


@dataclass(frozen=True, slots=True)
class ComplexityAssessment:
    level: ComplexityLevel
    score: float
    indicators_found: tuple[str, ...]
    should_decompose: bool
    word_count: int


def assess_complexity(prompt: str) -> ComplexityAssessment:
    if not prompt or not prompt.strip():
        return ComplexityAssessment(
            level=ComplexityLevel.SIMPLE,
            score=0.0,
            indicators_found=(),
            should_decompose=False,
            word_count=0,
        )

    lower = prompt.lower()
    words = prompt.split()
    word_count = len(words)

    indicators_found: list[str] = []
    for indicator in _COMPLEXITY_INDICATORS:
        if re.search(r"\b" + indicator + r"\b", lower):
            indicators_found.append(indicator)

    decomposition_signals: list[str] = []
    for signal in _DECOMPOSITION_SIGNALS:
        if re.search(signal, lower):
            decomposition_signals.append(signal)

    indicator_score = min(1.0, len(indicators_found) / 4.0)
    length_score = min(1.0, word_count / 50.0)
    decomp_score = min(1.0, len(decomposition_signals) / 2.0)

    score = (indicator_score * 0.5) + (length_score * 0.3) + (decomp_score * 0.2)
    score = round(score, 3)

    if score >= 0.6:
        level = ComplexityLevel.COMPLEX
    elif score >= 0.3:
        level = ComplexityLevel.MODERATE
    else:
        level = ComplexityLevel.SIMPLE

    should_decompose = (
        level == ComplexityLevel.COMPLEX
        or len(decomposition_signals) >= 2
    )

    return ComplexityAssessment(
        level=level,
        score=score,
        indicators_found=tuple(indicators_found),
        should_decompose=should_decompose,
        word_count=word_count,
    )
```

That is the COMPLETE implementation. Copy it exactly.

### test_complexity.py specification

Exactly these tests:

1. `test_empty_prompt_is_simple` — assess_complexity("") → level=SIMPLE, score=0.0, should_decompose=False
2. `test_whitespace_is_simple` — assess_complexity("   ") → level=SIMPLE, score=0.0
3. `test_short_question_is_simple` — assess_complexity("What is Python?") → level=SIMPLE
4. `test_single_indicator_moderate` — assess_complexity("Analyze the market trends") → indicators_found contains "analyze"
5. `test_multiple_indicators_complex` — assess_complexity("Compare and evaluate the trade-off between speed and accuracy in a comprehensive detailed analysis") → level=COMPLEX
6. `test_long_prompt_affects_score` — assess_complexity with a 60-word prompt → score > score of 5-word prompt with same indicators
7. `test_decomposition_signal_detected` — assess_complexity("Explain X and also describe Y additionally Z") → should_decompose=True
8. `test_no_decomposition_for_simple` — assess_complexity("What is 2+2?") → should_decompose=False
9. `test_word_count_accurate` — assess_complexity("one two three four five") → word_count=5
10. `test_case_insensitive` — assess_complexity("COMPARE the ADVANTAGES AND DISADVANTAGES") → indicators_found contains "compare"
11. `test_score_between_zero_and_one` — assess_complexity with any prompt → 0.0 <= score <= 1.0
12. `test_indicators_found_is_tuple` — assert isinstance(result.indicators_found, tuple)
13. `test_assessment_is_frozen` — assigning result.level = "simple" raises FrozenInstanceError
14. `test_complexity_level_is_str_enum` — ComplexityLevel.SIMPLE == "simple"
15. `test_complex_forces_decompose` — any result with level=COMPLEX → should_decompose=True
16. `test_regex_indicator_how_does_affect` — assess_complexity("How does inflation affect housing prices?") → indicators_found contains "how does .+ affect"
17. `test_all_complexity_levels_count` — len(ComplexityLevel) == 3

End with:
```python
if __name__ == "__main__":
    unittest.main()
```

## DONE WHEN
- [ ] `src/gracekelly/core/complexity.py` exists with ComplexityLevel, ComplexityAssessment, assess_complexity()
- [ ] `tests/test_complexity.py` exists with exactly 17 test methods
- [ ] `python -m pytest tests/test_complexity.py -q` → 17 passed, 0 failed
- [ ] `python -m pytest -q` → all existing tests still pass (419+)
- [ ] No other files created or modified

## SELF-EVALUATION
After completing, score yourself 1-10:
- Is the implementation EXACTLY as specified? (copy the code, don't rewrite the formula)
- Do all 17 tests pass, especially tests 6 (length effect) and 16 (regex indicator)?
- Is there any code beyond the specification? (if yes, remove it)
- Does the score formula produce values in [0.0, 1.0] range for all inputs?

If your self-score is below 9.8/10, fix issues before submitting. Target: 9.8/10.
```

---

## Задача 6/8: Reliability Levels [routine]

Рекомендация: 1 запуск.

```
## GOAL
Create reliability level definitions that map orchestration quality tiers to execution parameters. Two new files: `src/gracekelly/core/reliability.py` and `tests/test_reliability.py`.

## CONTEXT
Files to CREATE:
- `src/gracekelly/core/reliability.py` — reliability levels and configs
- `tests/test_reliability.py` — unit tests

Files to READ (do NOT modify):
- `src/gracekelly/core/contracts.py` — for StrEnum, MergeStrategy
- `src/gracekelly/core/consensus.py` — for ConsensusConfig (if it exists from task 4; if not, skip consensus_config field)

Architecture:
- Python >=3.11, no external dependencies
- All files start with `from __future__ import annotations`
- Enums inherit from `StrEnum`
- Dataclasses use `@dataclass(frozen=True, slots=True)`
- Tests use `unittest.TestCase`
- Test runner: `python -m pytest tests/test_reliability.py -q`

## CONSTRAINTS
- Create ONLY the two files listed above. Do NOT modify any existing files.
- Follow these instructions EXACTLY. Do NOT deviate, improve, or "enhance".
- Do NOT add: try/catch blocks, logging, comments, docstrings, or features not listed below.
- Preserve project code style: 4-space indentation, snake_case, `from __future__ import annotations`.

### reliability.py specification

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ReliabilityLevel(StrEnum):
    QUICK = "quick"
    STANDARD = "standard"
    HIGH = "high"
    MAXIMUM = "maximum"


@dataclass(frozen=True, slots=True)
class ReliabilityConfig:
    level: ReliabilityLevel
    min_models: int
    max_models: int
    use_verification: bool
    use_devil_advocate: bool
    use_consensus: bool
    consensus_threshold: float
    use_decomposition: bool
    max_consensus_rounds: int
    use_peer_review: bool
    use_confidence: bool
    description: str


RELIABILITY_CONFIGS: dict[ReliabilityLevel, ReliabilityConfig] = {
    ReliabilityLevel.QUICK: ReliabilityConfig(
        level=ReliabilityLevel.QUICK,
        min_models=1,
        max_models=1,
        use_verification=True,
        use_devil_advocate=False,
        use_consensus=False,
        consensus_threshold=0.0,
        use_decomposition=False,
        max_consensus_rounds=0,
        use_peer_review=False,
        use_confidence=False,
        description="Single model with fact verification. Fast, low cost.",
    ),
    ReliabilityLevel.STANDARD: ReliabilityConfig(
        level=ReliabilityLevel.STANDARD,
        min_models=2,
        max_models=3,
        use_verification=True,
        use_devil_advocate=False,
        use_consensus=False,
        consensus_threshold=0.0,
        use_decomposition=False,
        max_consensus_rounds=0,
        use_peer_review=False,
        use_confidence=True,
        description="Two models with comparison and synthesis. Balanced.",
    ),
    ReliabilityLevel.HIGH: ReliabilityConfig(
        level=ReliabilityLevel.HIGH,
        min_models=3,
        max_models=5,
        use_verification=True,
        use_devil_advocate=True,
        use_consensus=True,
        consensus_threshold=0.85,
        use_decomposition=True,
        max_consensus_rounds=1,
        use_peer_review=False,
        use_confidence=True,
        description="Three+ models with full verification, devil's advocate, and consensus.",
    ),
    ReliabilityLevel.MAXIMUM: ReliabilityConfig(
        level=ReliabilityLevel.MAXIMUM,
        min_models=5,
        max_models=5,
        use_verification=True,
        use_devil_advocate=True,
        use_consensus=True,
        consensus_threshold=0.95,
        use_decomposition=True,
        max_consensus_rounds=5,
        use_peer_review=True,
        use_confidence=True,
        description="All models, iterative consensus loop, peer review, all roles.",
    ),
}


def get_reliability_config(level: ReliabilityLevel) -> ReliabilityConfig:
    return RELIABILITY_CONFIGS[level]


def resolve_reliability_level(name: str) -> ReliabilityLevel:
    level = ReliabilityLevel(name)
    return level
```

That is the COMPLETE implementation. Copy it exactly.

### test_reliability.py specification

Exactly these tests:

1. `test_all_levels_have_configs` — every ReliabilityLevel value is in RELIABILITY_CONFIGS
2. `test_config_count_matches_enum` — len(RELIABILITY_CONFIGS) == len(ReliabilityLevel)
3. `test_quick_is_minimal` — QUICK: min_models=1, use_consensus=False, use_devil_advocate=False
4. `test_standard_uses_two_models` — STANDARD: min_models=2, use_confidence=True
5. `test_high_uses_consensus` — HIGH: use_consensus=True, consensus_threshold=0.85, use_devil_advocate=True
6. `test_maximum_is_full` — MAXIMUM: min_models=5, max_consensus_rounds=5, use_peer_review=True, consensus_threshold=0.95
7. `test_configs_are_frozen` — assigning config.min_models = 10 raises FrozenInstanceError
8. `test_get_reliability_config` — get_reliability_config(ReliabilityLevel.HIGH).level == ReliabilityLevel.HIGH
9. `test_get_reliability_config_raises_on_invalid` — get_reliability_config("nonexistent") raises KeyError
10. `test_resolve_reliability_level_valid` — resolve_reliability_level("quick") == ReliabilityLevel.QUICK
11. `test_resolve_reliability_level_invalid` — resolve_reliability_level("ultra") raises ValueError
12. `test_reliability_level_is_str_enum` — ReliabilityLevel.QUICK == "quick"
13. `test_all_configs_have_descriptions` — every config.description has len > 10
14. `test_consensus_threshold_increases_with_level` — QUICK < STANDARD <= HIGH < MAXIMUM thresholds

End with:
```python
if __name__ == "__main__":
    unittest.main()
```

## DONE WHEN
- [ ] `src/gracekelly/core/reliability.py` exists with ReliabilityLevel, ReliabilityConfig, RELIABILITY_CONFIGS, get_reliability_config(), resolve_reliability_level()
- [ ] `tests/test_reliability.py` exists with exactly 14 test methods
- [ ] `python -m pytest tests/test_reliability.py -q` → 14 passed, 0 failed
- [ ] `python -m pytest -q` → all existing tests still pass (419+)
- [ ] No other files created or modified

## SELF-EVALUATION
After completing, score yourself 1-10:
- Is the implementation EXACTLY as specified? (copy the RELIABILITY_CONFIGS dict exactly)
- Are all 14 tests present with correct assertions?
- Does test 14 correctly verify increasing thresholds across levels?
- Is there any code beyond the specification? (if yes, remove it)

If your self-score is below 9.8/10, fix issues before submitting. Target: 9.8/10.
```

---

## Задача 7/8: Execution Patterns [moderate]

Рекомендация: 2 параллельных запуска, выбрать лучший.

```
## GOAL
Create named execution patterns (SONAR, SINGLE, DUAL, etc.) that map orchestration strategies to concrete execution parameters. Two new files: `src/gracekelly/core/patterns.py` and `tests/test_patterns.py`.

## CONTEXT
Files to CREATE:
- `src/gracekelly/core/patterns.py` — pattern definitions and lookup
- `tests/test_patterns.py` — unit tests

Files to READ (do NOT modify):
- `src/gracekelly/core/contracts.py` — for MergeStrategy (StrEnum: "first_success", "concat")
- `src/gracekelly/core/reliability.py` — for ReliabilityLevel (if it exists from task 6; if not, use a string literal instead)

Architecture:
- Python >=3.11, no external dependencies
- All files start with `from __future__ import annotations`
- Enums inherit from `StrEnum`
- Dataclasses use `@dataclass(frozen=True, slots=True)`
- Tests use `unittest.TestCase`
- Test runner: `python -m pytest tests/test_patterns.py -q`

IMPORTANT: This module imports MergeStrategy from `gracekelly.core.contracts`. The import MUST be:
```python
from gracekelly.core.contracts import MergeStrategy
```
Do NOT redefine MergeStrategy. Do NOT copy it. Import it.

## CONSTRAINTS
- Create ONLY the two files listed above. Do NOT modify any existing files.
- Follow these instructions EXACTLY. Do NOT deviate, improve, or "enhance".
- Do NOT add: try/catch blocks, logging, comments, docstrings.
- Preserve project code style: 4-space indentation, snake_case, `from __future__ import annotations`, trailing commas.

### patterns.py specification

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from gracekelly.core.contracts import MergeStrategy


class ExecutionPattern(StrEnum):
    SONAR = "sonar"
    SINGLE = "single"
    DUAL = "dual"
    FIVE_MODELS = "five_models"
    FIVE_MODELS_COMPARE = "five_models_compare"
    CONSENSUS = "consensus"
    MAXIMUM = "maximum"


@dataclass(frozen=True, slots=True)
class PatternConfig:
    pattern: ExecutionPattern
    model_count: int | None
    reasoning: bool
    merge_strategy: MergeStrategy
    quorum: int
    use_consensus: bool
    use_roles: bool
    iterative: bool
    description: str


PATTERN_CONFIGS: dict[ExecutionPattern, PatternConfig] = {
    ExecutionPattern.SONAR: PatternConfig(
        pattern=ExecutionPattern.SONAR,
        model_count=1,
        reasoning=False,
        merge_strategy=MergeStrategy.FIRST_SUCCESS,
        quorum=1,
        use_consensus=False,
        use_roles=False,
        iterative=False,
        description="Single Sonar model, no reasoning. Maximum speed.",
    ),
    ExecutionPattern.SINGLE: PatternConfig(
        pattern=ExecutionPattern.SINGLE,
        model_count=1,
        reasoning=True,
        merge_strategy=MergeStrategy.FIRST_SUCCESS,
        quorum=1,
        use_consensus=False,
        use_roles=False,
        iterative=False,
        description="Single model with reasoning enabled.",
    ),
    ExecutionPattern.DUAL: PatternConfig(
        pattern=ExecutionPattern.DUAL,
        model_count=2,
        reasoning=True,
        merge_strategy=MergeStrategy.CONCAT,
        quorum=2,
        use_consensus=False,
        use_roles=False,
        iterative=False,
        description="Two models, both answers returned for comparison.",
    ),
    ExecutionPattern.FIVE_MODELS: PatternConfig(
        pattern=ExecutionPattern.FIVE_MODELS,
        model_count=5,
        reasoning=True,
        merge_strategy=MergeStrategy.CONCAT,
        quorum=3,
        use_consensus=False,
        use_roles=False,
        iterative=False,
        description="All models, answers returned as-is.",
    ),
    ExecutionPattern.FIVE_MODELS_COMPARE: PatternConfig(
        pattern=ExecutionPattern.FIVE_MODELS_COMPARE,
        model_count=5,
        reasoning=True,
        merge_strategy=MergeStrategy.FIRST_SUCCESS,
        quorum=3,
        use_consensus=False,
        use_roles=True,
        iterative=False,
        description="All models, then Judge role analyzes differences.",
    ),
    ExecutionPattern.CONSENSUS: PatternConfig(
        pattern=ExecutionPattern.CONSENSUS,
        model_count=3,
        reasoning=True,
        merge_strategy=MergeStrategy.FIRST_SUCCESS,
        quorum=3,
        use_consensus=True,
        use_roles=True,
        iterative=False,
        description="Three models with embedding-based consensus clustering.",
    ),
    ExecutionPattern.MAXIMUM: PatternConfig(
        pattern=ExecutionPattern.MAXIMUM,
        model_count=5,
        reasoning=True,
        merge_strategy=MergeStrategy.FIRST_SUCCESS,
        quorum=5,
        use_consensus=True,
        use_roles=True,
        iterative=True,
        description="All models, iterative consensus loop until threshold.",
    ),
}


def get_pattern_config(pattern: ExecutionPattern) -> PatternConfig:
    return PATTERN_CONFIGS[pattern]


def resolve_pattern(name: str) -> ExecutionPattern:
    return ExecutionPattern(name)


def patterns_using_consensus() -> tuple[ExecutionPattern, ...]:
    return tuple(
        p for p, cfg in PATTERN_CONFIGS.items() if cfg.use_consensus
    )


def patterns_using_roles() -> tuple[ExecutionPattern, ...]:
    return tuple(
        p for p, cfg in PATTERN_CONFIGS.items() if cfg.use_roles
    )
```

That is the COMPLETE implementation. Copy it exactly.

### test_patterns.py specification

Exactly these tests:

1. `test_all_patterns_have_configs` — every ExecutionPattern value is in PATTERN_CONFIGS
2. `test_config_count_matches_enum` — len(PATTERN_CONFIGS) == len(ExecutionPattern)
3. `test_sonar_is_fast` — SONAR: model_count=1, reasoning=False, use_consensus=False
4. `test_single_has_reasoning` — SINGLE: model_count=1, reasoning=True
5. `test_dual_uses_concat` — DUAL: model_count=2, merge_strategy=MergeStrategy.CONCAT
6. `test_five_models_quorum_three` — FIVE_MODELS: model_count=5, quorum=3
7. `test_five_models_compare_uses_roles` — FIVE_MODELS_COMPARE: use_roles=True, use_consensus=False
8. `test_consensus_uses_consensus` — CONSENSUS: use_consensus=True, model_count=3
9. `test_maximum_is_iterative` — MAXIMUM: iterative=True, use_consensus=True, use_roles=True, model_count=5
10. `test_get_pattern_config` — get_pattern_config(ExecutionPattern.DUAL).pattern == ExecutionPattern.DUAL
11. `test_get_pattern_config_raises_on_invalid` — get_pattern_config("nonexistent") raises KeyError
12. `test_resolve_pattern_valid` — resolve_pattern("sonar") == ExecutionPattern.SONAR
13. `test_resolve_pattern_invalid` — resolve_pattern("ultra") raises ValueError
14. `test_patterns_using_consensus` — returns tuple containing CONSENSUS and MAXIMUM, not SONAR
15. `test_patterns_using_roles` — returns tuple containing FIVE_MODELS_COMPARE, CONSENSUS, MAXIMUM, not SONAR
16. `test_pattern_is_str_enum` — ExecutionPattern.SONAR == "sonar"
17. `test_configs_are_frozen` — assigning config.quorum = 10 raises FrozenInstanceError
18. `test_all_configs_have_descriptions` — every config.description has len > 10

End with:
```python
if __name__ == "__main__":
    unittest.main()
```

## DONE WHEN
- [ ] `src/gracekelly/core/patterns.py` exists with ExecutionPattern, PatternConfig, PATTERN_CONFIGS, get_pattern_config(), resolve_pattern(), patterns_using_consensus(), patterns_using_roles()
- [ ] `tests/test_patterns.py` exists with exactly 18 test methods
- [ ] `python -m pytest tests/test_patterns.py -q` → 18 passed, 0 failed
- [ ] `python -m pytest -q` → all existing tests still pass (419+)
- [ ] No other files created or modified
- [ ] MergeStrategy is IMPORTED from gracekelly.core.contracts, NOT redefined

## SELF-EVALUATION
After completing, score yourself 1-10:
- Is MergeStrategy imported, not copied?
- Are all 7 pattern configs exactly as specified?
- Do all 18 tests pass, especially tests 14-15 (filter functions)?
- Is there any code beyond the specification? (if yes, remove it)

If your self-score is below 9.8/10, fix issues before submitting. Target: 9.8/10.
```

---

## Задача 8/8: Model Performance Stats [moderate]

Рекомендация: 2 параллельных запуска, выбрать лучший.

```
## GOAL
Create a model performance aggregator that computes success rates, average latency, and rankings from execution step records. Two new files: `src/gracekelly/core/model_stats.py` and `tests/test_model_stats.py`.

## CONTEXT
Files to CREATE:
- `src/gracekelly/core/model_stats.py` — performance aggregation
- `tests/test_model_stats.py` — unit tests

Files to READ (do NOT modify):
- `src/gracekelly/core/contracts.py` — for StepStatus (StrEnum: "pending", "completed", "failed", "cancelled")

Architecture:
- Python >=3.11, no external dependencies
- All files start with `from __future__ import annotations`
- Dataclasses use `@dataclass(frozen=True, slots=True)`
- Tests use `unittest.TestCase`
- Test runner: `python -m pytest tests/test_model_stats.py -q`
- The aggregator does NOT import storage classes. It takes plain dicts as input to avoid coupling.

IMPORTANT: Input data format is `list[dict]` — each dict has keys:
- `"model_id"` (str)
- `"status"` (str — "completed" or "failed")
- `"duration_ms"` (int | None)

This avoids importing storage classes. Keep it decoupled.

## CONSTRAINTS
- Create ONLY the two files listed above. Do NOT modify any existing files.
- Follow these instructions EXACTLY. Do NOT deviate, improve, or "enhance".
- Do NOT add: try/catch blocks, logging, comments, docstrings, pandas, or database access.
- Do NOT import from gracekelly.storage. The function takes plain dicts.
- Preserve project code style: 4-space indentation, snake_case, `from __future__ import annotations`.

### model_stats.py specification

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelPerformance:
    model_id: str
    total_executions: int
    successful: int
    failed: int
    success_rate: float
    avg_duration_ms: float
    total_duration_ms: int


def aggregate_model_stats(
    step_records: list[dict[str, object]],
) -> dict[str, ModelPerformance]:
    by_model: dict[str, list[dict[str, object]]] = {}
    for record in step_records:
        model_id = str(record["model_id"])
        by_model.setdefault(model_id, []).append(record)

    result: dict[str, ModelPerformance] = {}
    for model_id, records in sorted(by_model.items()):
        total = len(records)
        successful = sum(1 for r in records if r.get("status") == "completed")
        failed = sum(1 for r in records if r.get("status") == "failed")
        durations = [
            r["duration_ms"]
            for r in records
            if r.get("duration_ms") is not None and isinstance(r["duration_ms"], (int, float))
        ]
        total_duration = sum(int(d) for d in durations)
        avg_duration = total_duration / len(durations) if durations else 0.0

        result[model_id] = ModelPerformance(
            model_id=model_id,
            total_executions=total,
            successful=successful,
            failed=failed,
            success_rate=successful / total if total > 0 else 0.0,
            avg_duration_ms=round(avg_duration, 1),
            total_duration_ms=total_duration,
        )
    return result


def rank_models_by_success_rate(
    stats: dict[str, ModelPerformance],
    min_executions: int = 1,
) -> list[ModelPerformance]:
    eligible = [
        perf for perf in stats.values()
        if perf.total_executions >= min_executions
    ]
    return sorted(
        eligible,
        key=lambda p: (-p.success_rate, p.avg_duration_ms),
    )
```

That is the COMPLETE implementation. Copy it exactly.

### test_model_stats.py specification

Exactly these tests:

1. `test_empty_input` — aggregate_model_stats([]) returns empty dict
2. `test_single_success` — one record {"model_id": "m1", "status": "completed", "duration_ms": 100} → success_rate=1.0, total=1
3. `test_single_failure` — one record with status="failed" → success_rate=0.0, failed=1
4. `test_mixed_results` — 3 completed + 2 failed for "m1" → success_rate=0.6, total=5
5. `test_multiple_models` — records for "m1" and "m2" → 2 keys in result
6. `test_avg_duration_calculation` — 3 records with durations 100, 200, 300 → avg_duration_ms=200.0
7. `test_duration_none_excluded` — records with duration_ms=None are excluded from avg but counted in total_executions
8. `test_total_duration_sum` — 3 records with 100, 200, 300 → total_duration_ms=600
9. `test_rank_by_success_rate` — model with 100% success ranked before 50% success
10. `test_rank_tiebreak_by_latency` — two models with same success_rate → lower avg_duration ranked first
11. `test_rank_min_executions_filter` — model with 1 execution filtered out when min_executions=5
12. `test_rank_empty_stats` — rank_models_by_success_rate({}) returns empty list
13. `test_performance_is_frozen` — assigning perf.success_rate = 1.0 raises FrozenInstanceError
14. `test_sorted_by_model_id` — result dict keys are in alphabetical order
15. `test_success_rate_rounded` — 1 success out of 3 → success_rate ≈ 0.333 (3 decimals)

End with:
```python
if __name__ == "__main__":
    unittest.main()
```

## DONE WHEN
- [ ] `src/gracekelly/core/model_stats.py` exists with ModelPerformance, aggregate_model_stats(), rank_models_by_success_rate()
- [ ] `tests/test_model_stats.py` exists with exactly 15 test methods
- [ ] `python -m pytest tests/test_model_stats.py -q` → 15 passed, 0 failed
- [ ] `python -m pytest -q` → all existing tests still pass (419+)
- [ ] No other files created or modified
- [ ] No imports from gracekelly.storage — input is plain list[dict]

## SELF-EVALUATION
After completing, score yourself 1-10:
- Is the implementation EXACTLY as specified? (copy the code, don't add features)
- Are all 15 tests present with correct assertions?
- Does test 15 verify rounding behavior correctly?
- Is there any code beyond the specification? (if yes, remove it)
- Are there any imports from gracekelly.storage? (there should NOT be)

If your self-score is below 9.8/10, fix issues before submitting. Target: 9.8/10.
```

---

## Задача 9/9: Установка и оценка внешних скиллов [routine]

Рекомендация: 1 запуск.

```
## GOAL
Install 3 Claude Code skills from the skills.sh marketplace, verify they work, and write a short evaluation report. Output: `docs/skills-evaluation.md`.

## CONTEXT
Files to CREATE:
- `docs/skills-evaluation.md` — evaluation report

Files NOT to modify: anything in `src/` or `tests/`.

Skills to install and evaluate:
1. `softaworks/agent-toolkit@codex` (3.4K installs) — Codex integration toolkit
2. `rysweet/amplihack@roadmap-strategist` (109 installs) — roadmap/strategic planning
3. `rookie-ricardo/erduo-skills@gemini-watermark-remover` (1.4K installs) — watermark removal via Gemini

Installation command: `npx skills add <owner/repo@skill> -g -y`
Skills directory: `~/.claude/skills/`

## CONSTRAINTS
- Do NOT modify any project code or tests.
- Do NOT run pytest or modify pyproject.toml.
- Install each skill, then READ its SKILL.md file to evaluate it.
- Do NOT uninstall any existing skills.
- If a skill fails to install (network, npm issues), note it and move on.
- Platform: Windows 11. Use bash syntax.

### Evaluation criteria for each skill

For each installed skill, evaluate on a scale of 1-10:

1. **Actionability** — does the skill provide concrete steps, or just vague guidance?
2. **Specificity** — does it address real agent weaknesses, or is it generic advice?
3. **Token efficiency** — is it concise (<500 words core), or bloated?
4. **Conflict risk** — does it overlap with our existing skills? (check against: `codex-task`, `research-driven-planning`, `watermark-remove`, `writing-plans`)
5. **Adoption recommendation** — ADOPT / EVALUATE_FURTHER / SKIP

### Report format (docs/skills-evaluation.md)

```markdown
# Skills Evaluation Report

Date: 2026-03-19

## Summary

| Skill | Installs | Actionability | Specificity | Token Eff. | Conflict | Verdict |
|-------|----------|---------------|-------------|------------|----------|---------|
| ... | ... | /10 | /10 | /10 | low/medium/high | ADOPT/SKIP |

## 1. softaworks/agent-toolkit@codex

**What it does**: [1-2 sentences]
**Key strengths**: [bullets]
**Weaknesses**: [bullets]
**Conflicts with**: [list or "none"]
**Verdict**: [ADOPT / EVALUATE_FURTHER / SKIP] — [reason]

## 2. rysweet/amplihack@roadmap-strategist

[same structure]

## 3. rookie-ricardo/erduo-skills@gemini-watermark-remover

[same structure]

## Recommendations

[Which to keep, which to remove, any integration notes]
```

## DONE WHEN
- [ ] All 3 skills installed (or installation failures documented)
- [ ] Each skill's SKILL.md has been read and evaluated
- [ ] `docs/skills-evaluation.md` exists with the evaluation table and 3 detailed sections
- [ ] No project files modified
- [ ] Report uses the exact format specified above
```

---

## Общие инструкции для всех задач

**Платформа**: Windows 11, Python 3.13, проект в `D:\GraceKelly`.
**pytest config**: `pyproject.toml` уже содержит `pythonpath = ["src"]` — импорты работают без `pip install -e`.
**Проверка**: `python -m pytest -q` (вся suite должна остаться зелёной: 419+ passed).
**Порядок**: задачи 1-3 можно выполнять параллельно. Задачи 4-8 можно выполнять параллельно, но задача 7 (patterns) импортирует MergeStrategy из contracts.py — убедись, что он существует.
**Суммарный прирост тестов**: задачи 1-8 добавляют 15+10+18+15+17+14+18+15 = **122 новых теста**.

**Стиль проекта**:
- `from __future__ import annotations` — первая строка каждого .py файла
- `@dataclass(frozen=True, slots=True)` для immutable data
- `StrEnum` для перечислений (не обычный Enum)
- `unittest.TestCase` для тестов (не голые функции pytest)
- 4 пробела отступ
- snake_case для переменных и функций
- Без docstrings, без комментариев (кроме где явно указано)
