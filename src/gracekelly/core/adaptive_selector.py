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
