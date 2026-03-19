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
