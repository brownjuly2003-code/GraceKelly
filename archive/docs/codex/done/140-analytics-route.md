# 140: Analytics API Route — TODO

Phase 10 (Analytics). Dependency: model_stats.py, task_classifier.py, adaptive_selector.py exist.
Complexity: moderate | Runs: 2

```
## GOAL
Create GET /api/v1/analytics endpoint that returns model performance stats and recommendations. Two new files: `src/gracekelly/api/routes/analytics.py` and `tests/test_analytics_route.py`.

## CONTEXT
Files to CREATE:
- `src/gracekelly/api/routes/analytics.py` — analytics route
- `tests/test_analytics_route.py` — integration tests

Files to READ (do NOT modify):
- `src/gracekelly/core/model_stats.py` — aggregate_model_stats(), rank_models_by_success_rate()
- `src/gracekelly/core/adaptive_selector.py` — select_models() (if it exists from task 120; if not, skip recommendations)
- `src/gracekelly/api/routes/orchestrate.py` — for route pattern reference
- `src/gracekelly/storage/base.py` — TaskRepository, TaskStepRecord

Architecture:
- FastAPI route with APIRouter
- Gets step records from storage via app.state.task_repository
- Tests create mock repository with synthetic data
- Test runner: `python -m pytest tests/test_analytics_route.py -q`

## CONSTRAINTS
- Create ONLY the two files listed above. Do NOT modify any existing files.
- Follow these instructions EXACTLY.
- Do NOT add: logging beyond the logger declaration, comments, docstrings.
- Do NOT modify main.py — the route will be wired later.
- Preserve project code style: 4-space indentation, snake_case, `from __future__ import annotations`.

### analytics.py (route) specification

```python
from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

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
        except Exception:
            pass

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
```

That is the COMPLETE implementation. Copy it exactly.

### test_analytics_route.py specification

```python
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gracekelly.api.routes.analytics import router


def _create_test_app(*, has_repository: bool = True, tasks_data: list | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    if has_repository:
        repo = MagicMock()
        mock_tasks = tasks_data or []
        repo.list_recent.return_value = mock_tasks
        repo.list_steps.return_value = []
        app.state.task_repository = repo
    else:
        app.state.task_repository = None

    return app
```

Exactly these tests:

1. `test_analytics_returns_200` — GET /api/v1/analytics → 200
2. `test_analytics_empty_no_tasks` — no tasks → total_models=0, total_executions=0
3. `test_analytics_response_fields` — response has total_models, total_executions, models, top_models
4. `test_analytics_no_repository_returns_200` — has_repository=False → 200 with empty data
5. `test_models_list_type` — models is a list
6. `test_top_models_list_type` — top_models is a list
7. `test_total_models_count` — matches len(models)
8. `test_model_stats_view_fields` — each model has: model_id, total_executions, successful, failed, success_rate, avg_duration_ms

End with:
```python
if __name__ == "__main__":
    unittest.main()
```

## DONE WHEN
- [ ] `src/gracekelly/api/routes/analytics.py` exists
- [ ] `tests/test_analytics_route.py` exists with exactly 8 test methods
- [ ] `python -m pytest tests/test_analytics_route.py -q` → 8 passed, 0 failed
- [ ] `python -m pytest -q` → all existing tests still pass (631+)
- [ ] No existing files modified

## SELF-EVALUATION
After completing, score yourself 1-10. Target: 9.8/10.
```
