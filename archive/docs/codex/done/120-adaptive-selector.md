# 120: Adaptive Model Selector — TODO

Phase 10 (Analytics). Dependency: model_stats.py, task_classifier.py exist.
Complexity: moderate | Runs: 2

```
## GOAL
Create an adaptive model selector that picks the best models for a task type based on historical performance. Two new files: `src/gracekelly/core/adaptive_selector.py` and `tests/test_adaptive_selector.py`.

## CONTEXT
Files to CREATE:
- `src/gracekelly/core/adaptive_selector.py` — selector logic
- `tests/test_adaptive_selector.py` — unit tests

Files to READ (do NOT modify):
- `src/gracekelly/core/model_stats.py` — ModelPerformance, aggregate_model_stats(), rank_models_by_success_rate()
- `src/gracekelly/core/task_classifier.py` — TaskType, classify_task()
- `src/gracekelly/core/models.py` — MODEL_SPECS, ModelSpec

Architecture:
- Python >=3.11, no external dependencies
- Selector takes historical step records + prompt → returns ranked model list
- Tests use synthetic step records
- Test runner: `python -m pytest tests/test_adaptive_selector.py -q`

## CONSTRAINTS
- Create ONLY the two files listed above. Do NOT modify any existing files.
- Follow these instructions EXACTLY.
- Do NOT add: logging, comments, docstrings, ML models, database access.
- Preserve project code style: 4-space indentation, snake_case, `from __future__ import annotations`.

### adaptive_selector.py specification

```python
from __future__ import annotations

from dataclasses import dataclass

from gracekelly.core.model_stats import ModelPerformance, aggregate_model_stats, rank_models_by_success_rate
from gracekelly.core.task_classifier import TaskType, classify_task


@dataclass(frozen=True, slots=True)
class ModelRecommendation:
    model_id: str
    score: float
    reason: str


def select_models(
    prompt: str,
    step_records: list[dict[str, object]],
    max_models: int = 3,
    min_executions: int = 3,
) -> list[ModelRecommendation]:
    task_type = classify_task(prompt)
    task_records = [
        r for r in step_records
        if r.get("task_type") == task_type.value
    ]

    if not task_records:
        task_records = step_records

    stats = aggregate_model_stats(task_records)
    ranked = rank_models_by_success_rate(stats, min_executions=min_executions)

    if not ranked:
        ranked = rank_models_by_success_rate(
            aggregate_model_stats(step_records),
            min_executions=1,
        )

    recommendations: list[ModelRecommendation] = []
    for perf in ranked[:max_models]:
        reason = _build_reason(perf, task_type)
        recommendations.append(
            ModelRecommendation(
                model_id=perf.model_id,
                score=round(perf.success_rate, 3),
                reason=reason,
            )
        )
    return recommendations


def _build_reason(perf: ModelPerformance, task_type: TaskType) -> str:
    parts: list[str] = []
    parts.append(f"{perf.success_rate:.0%} success rate")
    parts.append(f"{perf.total_executions} executions")
    if perf.avg_duration_ms > 0:
        parts.append(f"{perf.avg_duration_ms:.0f}ms avg")
    parts.append(f"task type: {task_type.value}")
    return ", ".join(parts)
```

That is the COMPLETE implementation. Copy it exactly.

### test_adaptive_selector.py specification

Exactly these tests:

1. `test_empty_records_returns_empty` — select_models("hello", []) → empty list
2. `test_returns_top_models` — 3 models with different success rates → top model first
3. `test_max_models_limits_output` — 5 models, max_models=2 → 2 recommendations
4. `test_min_executions_filters` — model with 1 execution, min_executions=3 → filtered out
5. `test_task_type_filters_records` — coding prompt filters to coding-tagged records
6. `test_fallback_to_all_records` — no records matching task type → uses all records
7. `test_recommendation_has_reason` — reason contains "success rate" and "executions"
8. `test_recommendation_is_frozen` — ModelRecommendation is frozen
9. `test_score_is_success_rate` — recommendation.score matches model success_rate
10. `test_general_prompt_uses_all` — "Hello" (general) with no task_type-tagged records → uses all
11. `test_coding_prompt_prefers_coding_records` — "Write Python code" uses coding-tagged records
12. `test_multiple_task_types_mixed` — records with different task_types → correct filtering

End with:
```python
if __name__ == "__main__":
    unittest.main()
```

## DONE WHEN
- [ ] `src/gracekelly/core/adaptive_selector.py` exists
- [ ] `tests/test_adaptive_selector.py` exists with exactly 12 test methods
- [ ] `python -m pytest tests/test_adaptive_selector.py -q` → 12 passed, 0 failed
- [ ] `python -m pytest -q` → all existing tests still pass (631+)
- [ ] No other files created or modified

## SELF-EVALUATION
After completing, score yourself 1-10. Target: 9.8/10.
```
