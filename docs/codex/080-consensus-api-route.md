# 080: Consensus API Route — TODO

Phase 6 integration (step 2/3). Dependency: 070.
Complexity: moderate | Runs: 2

```
## GOAL
Create a new API endpoint POST /api/v1/consensus that runs consensus-based execution. Three new files: route, schema additions, and tests. Does NOT modify any existing files.

## CONTEXT
Files to CREATE:
- `src/gracekelly/api/routes/consensus.py` — new route
- `tests/test_consensus_route.py` — integration tests

Files to READ (do NOT modify):
- `src/gracekelly/core/consensus_execution.py` — ConsensusExecutor, ConsensusExecutionConfig, ConsensusExecutionResult, ExecuteFunc
- `src/gracekelly/core/consensus.py` — ConsensusConfig
- `src/gracekelly/core/embeddings.py` — EmbeddingsClient
- `src/gracekelly/core/contracts.py` — ExecutionRequest, ExecutionResult, ExecutionStep, ExecutionPlan, ExecutionBackend, StepStatus, ExecutionMode, MergeStrategy, AdapterHint, FailureCode
- `src/gracekelly/core/models.py` — resolve_model, ModelSpec
- `src/gracekelly/core/planning.py` — for understanding how ExecutionStep is built
- `src/gracekelly/api/routes/orchestrate.py` — for pattern reference (router, logger, error handling)
- `src/gracekelly/schemas.py` — for Pydantic pattern reference
- `src/gracekelly/main.py` — app.state structure (app.state.api_adapters, app.state.execution_router)

Architecture:
- FastAPI route with APIRouter
- The route gets `embeddings_client` from `app.state.embeddings_client` (will be wired in task 090)
- The route gets `api_adapters` from `app.state.api_adapters`
- Uses `ConsensusExecutor` with a callback that calls an API adapter
- Tests mock app.state to avoid real API calls
- Tests use `unittest.TestCase` with `fastapi.testclient.TestClient`
- Test runner: `python -m pytest tests/test_consensus_route.py -q`

## CONSTRAINTS
- Create ONLY the two files listed above. Do NOT modify any existing files.
- Follow these instructions EXACTLY. Do NOT deviate, improve, or "enhance".
- Do NOT add: logging, comments, docstrings beyond what's specified.
- Do NOT modify schemas.py — define request/response models inline in the route file.
- Preserve project code style: 4-space indentation, snake_case, `from __future__ import annotations`.

### consensus.py (route) specification

```python
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from gracekelly.core.consensus import ConsensusConfig
from gracekelly.core.consensus_execution import ConsensusExecutionConfig, ConsensusExecutor
from gracekelly.core.contracts import (
    ExecutionBackend,
    ExecutionMode,
    ExecutionPlan,
    ExecutionRequest,
    ExecutionStep,
    MergeStrategy,
    AdapterHint,
    StepStatus,
)
from gracekelly.core.models import resolve_model

router = APIRouter(prefix="/api/v1", tags=["consensus"])
logger = logging.getLogger(__name__)


class ConsensusRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=40000)
    model: str = Field(default="mistral-small", min_length=1, max_length=120)
    similarity_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    consensus_target: float = Field(default=0.95, ge=0.0, le=1.0)
    max_rounds: int = Field(default=5, ge=1, le=20)
    variations_per_round: int = Field(default=3, ge=1, le=9)
    use_confidence_weighting: bool = True


class ConsensusResponse(BaseModel):
    consensus_score: float
    num_clusters: int
    best_response: str
    weighted_score: float | None
    total_rounds: int
    total_llm_calls: int
    needs_debate: bool
    top_cluster_size: int


@router.post("/consensus", response_model=ConsensusResponse)
def run_consensus(payload: ConsensusRequest, request: Request) -> ConsensusResponse:
    embeddings_client = getattr(request.app.state, "embeddings_client", None)
    if embeddings_client is None:
        raise HTTPException(status_code=503, detail="Embeddings client is not configured.")

    api_adapters = getattr(request.app.state, "api_adapters", {})

    try:
        model_spec = resolve_model(payload.model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    adapter = api_adapters.get(model_spec.provider)
    if adapter is None:
        raise HTTPException(
            status_code=400,
            detail=f"No API adapter for provider '{model_spec.provider}'.",
        )

    consensus_config = ConsensusConfig(
        similarity_threshold=payload.similarity_threshold,
        consensus_target=payload.consensus_target,
        max_rounds=payload.max_rounds,
        variations_per_round=payload.variations_per_round,
    )
    exec_config = ConsensusExecutionConfig(
        consensus_config=consensus_config,
        variations_per_round=payload.variations_per_round,
        use_confidence_weighting=payload.use_confidence_weighting,
    )
    executor = ConsensusExecutor(embeddings_client, exec_config)

    step = ExecutionStep(
        model=model_spec,
        backend=ExecutionBackend.API,
        provider=model_spec.provider,
        provider_model_id=model_spec.provider_model_id,
        step_index=0,
    )
    plan = ExecutionPlan(
        steps=(step,),
        quorum=1,
        merge_strategy=MergeStrategy.FIRST_SUCCESS,
        dry_run=False,
        adapter_hint=AdapterHint.API,
        cancel_on_quorum=False,
    )

    def execute_fn(prompt_text: str) -> str:
        exec_request = ExecutionRequest(
            task_id="consensus",
            prompt=prompt_text,
            plan=plan,
            step=step,
            reasoning=False,
        )
        result = adapter.execute(exec_request)
        if result.status == StepStatus.COMPLETED and result.output_text:
            return result.output_text
        return f"[{result.failure_code or 'error'}] {result.failure_message or 'No output'}"

    try:
        result = executor.execute(payload.prompt, execute_fn)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Consensus execution failed: {exc}")

    return ConsensusResponse(
        consensus_score=result.consensus_result.consensus_score,
        num_clusters=result.consensus_result.num_clusters,
        best_response=result.best_response,
        weighted_score=result.weighted_score,
        total_rounds=result.total_rounds,
        total_llm_calls=result.total_llm_calls,
        needs_debate=result.consensus_result.needs_debate,
        top_cluster_size=result.consensus_result.top_cluster.size,
    )
```

That is the COMPLETE implementation. Copy it exactly.

### test_consensus_route.py specification

```python
from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gracekelly.api.routes.consensus import router
from gracekelly.core.embeddings import EmbeddingsClient
from gracekelly.core.contracts import ExecutionMode, StepStatus


def _create_test_app(*, has_embeddings: bool = True, has_adapter: bool = True) -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    if has_embeddings:
        embeddings = MagicMock(spec=EmbeddingsClient)
        embeddings.embed.return_value = [1.0, 0.0, 0.0]
        embeddings.embed_batch.side_effect = lambda texts: [[1.0, 0.0, 0.0] for _ in texts]
        app.state.embeddings_client = embeddings
    else:
        app.state.embeddings_client = None

    if has_adapter:
        adapter = MagicMock()
        adapter.execute.return_value = MagicMock(
            status=StepStatus.COMPLETED,
            output_text="Test response. Confidence: 8/10",
            failure_code=None,
            failure_message=None,
        )
        app.state.api_adapters = {"mistral": adapter}
    else:
        app.state.api_adapters = {}

    return app
```

Exactly these tests:

1. `test_consensus_returns_200` — POST /api/v1/consensus with valid payload → 200
2. `test_consensus_response_fields` — response has all fields: consensus_score, num_clusters, best_response, etc.
3. `test_consensus_score_is_one_for_identical` — identical embeddings → consensus_score == 1.0
4. `test_total_llm_calls_default_three` — default variations_per_round=3 → total_llm_calls == 3
5. `test_no_embeddings_client_returns_503` — has_embeddings=False → 503
6. `test_invalid_model_returns_400` — model="nonexistent-model-xyz" → 400
7. `test_custom_threshold` — similarity_threshold=0.5 → accepted, returns 200
8. `test_weighted_score_present` — use_confidence_weighting=True → weighted_score is not None
9. `test_weighted_score_absent` — use_confidence_weighting=False → weighted_score is None
10. `test_best_response_not_empty` — best_response is a non-empty string
11. `test_needs_debate_false_for_identical` — identical embeddings → needs_debate == False
12. `test_missing_adapter_returns_400` — has_adapter=False, model uses missing provider → 400

End with:
```python
if __name__ == "__main__":
    unittest.main()
```

## DONE WHEN
- [ ] `src/gracekelly/api/routes/consensus.py` exists with ConsensusRequest, ConsensusResponse, run_consensus()
- [ ] `tests/test_consensus_route.py` exists with exactly 12 test methods
- [ ] `python -m pytest tests/test_consensus_route.py -q` → 12 passed, 0 failed
- [ ] `python -m pytest -q` → all existing tests still pass (619+)
- [ ] No existing files modified

## SELF-EVALUATION
After completing, score yourself 1-10:
- Is the route implementation EXACTLY as specified?
- Do all 12 tests pass, including 503/400 error cases?
- Does the execute_fn correctly call adapter.execute and extract output_text?
- Is there any code beyond the specification?

If your self-score is below 9.8/10, fix issues before submitting. Target: 9.8/10.
```
