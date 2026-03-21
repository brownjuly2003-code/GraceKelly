from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from gracekelly.core.execution_history import ExecutionHistory
from gracekelly.core.model_stats import ModelPerformance, aggregate_model_stats, rank_models_by_success_rate

router = APIRouter(prefix="/api/v1", tags=["analytics"])
logger = logging.getLogger(__name__)


class ModelStatsView(BaseModel):
    model_id: str
    total_executions: int
    successful: int
    failed: int
    success_rate: float
    avg_duration_ms: float


class AnalyticsResponse(BaseModel):
    total_models: int
    total_executions: int
    models: list[ModelStatsView]
    top_models: list[ModelStatsView]


@router.get("/analytics", response_model=AnalyticsResponse)
def get_analytics(request: Request) -> AnalyticsResponse:
    repository = getattr(request.app.state, "task_repository", None)
    step_records: list[dict[str, object]] = []

    if repository is not None:
        try:
            tasks = repository.list_recent(limit=100)
            for task in tasks:
                steps = repository.list_steps(task.task_id)
                for step in steps:
                    step_records.append({
                        "model_id": step.model_id,
                        "status": step.status,
                        "duration_ms": step.duration_ms,
                    })
        except Exception as exc:
            logger.error("Analytics storage read failed: %s", exc)
            raise HTTPException(status_code=503, detail="Storage unavailable.")

    if not step_records:
        history = getattr(request.app.state, "execution_history", None)
        if history is not None:
            for rec in history.list_recent(limit=100):
                step_records.append({
                    "model_id": rec.model_id,
                    "status": rec.status,
                    "duration_ms": rec.duration_ms,
                })

    stats = aggregate_model_stats(step_records)
    ranked = rank_models_by_success_rate(stats, min_executions=1)

    models = [
        ModelStatsView(
            model_id=perf.model_id,
            total_executions=perf.total_executions,
            successful=perf.successful,
            failed=perf.failed,
            success_rate=round(perf.success_rate, 3),
            avg_duration_ms=perf.avg_duration_ms,
        )
        for perf in stats.values()
    ]

    top_models = [
        ModelStatsView(
            model_id=perf.model_id,
            total_executions=perf.total_executions,
            successful=perf.successful,
            failed=perf.failed,
            success_rate=round(perf.success_rate, 3),
            avg_duration_ms=perf.avg_duration_ms,
        )
        for perf in ranked[:5]
    ]

    return AnalyticsResponse(
        total_models=len(stats),
        total_executions=sum(perf.total_executions for perf in stats.values()),
        models=models,
        top_models=top_models,
    )
