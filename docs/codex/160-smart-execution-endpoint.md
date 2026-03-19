# 160: Smart Execution Endpoint — TODO

Crown jewel integration. Combines ALL building blocks into one unified endpoint.
Dependency: all core modules exist, consensus route exists as pattern reference.
Complexity: complex | Runs: 2, pick best

```
## GOAL
Create POST /api/v1/smart — a unified endpoint that chains: classify → assess complexity → resolve pattern → optionally decompose → execute with roles → optionally run consensus → return result. Two new files only.

## CONTEXT
Files to CREATE:
- `src/gracekelly/api/routes/smart.py` — unified smart route
- `tests/test_smart_route.py` — integration tests

Files to READ (do NOT modify):
- `src/gracekelly/api/routes/consensus.py` — for route pattern, execute_fn callback, adapter lookup
- `src/gracekelly/core/pattern_resolver.py` — resolve_from_level(), resolve_from_pattern(), ResolvedExecution
- `src/gracekelly/core/reliability.py` — ReliabilityLevel
- `src/gracekelly/core/patterns.py` — ExecutionPattern
- `src/gracekelly/core/task_classifier.py` — classify_task()
- `src/gracekelly/core/complexity.py` — assess_complexity()
- `src/gracekelly/core/decomposition.py` — execute_decomposed()
- `src/gracekelly/core/role_executor.py` — RoleExecutor
- `src/gracekelly/core/consensus_execution.py` — ConsensusExecutor, ConsensusExecutionConfig
- `src/gracekelly/core/consensus.py` — ConsensusConfig
- `src/gracekelly/core/contracts.py` — ExecutionBackend, ExecutionPlan, ExecutionRequest, ExecutionStep, MergeStrategy, AdapterHint, StepStatus
- `src/gracekelly/core/models.py` — resolve_model()

Architecture:
- FastAPI route. Gets adapters + embeddings from app.state (same as consensus route).
- The route builds an execute_fn callback, then orchestrates the pipeline based on resolved pattern.
- Tests mock adapters and embeddings (same mock pattern as test_consensus_route.py).
- Test runner: `python -m pytest tests/test_smart_route.py -q`

## CONSTRAINTS
- Create ONLY the two files listed above. Do NOT modify any existing files.
- Follow these instructions EXACTLY.
- Do NOT add: comments, docstrings.
- Preserve project code style: 4-space indentation, snake_case, `from __future__ import annotations`.

### smart.py (route) specification

```python
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from gracekelly.core.complexity import assess_complexity
from gracekelly.core.consensus import ConsensusConfig
from gracekelly.core.consensus_execution import ConsensusExecutionConfig, ConsensusExecutor
from gracekelly.core.contracts import (
    AdapterHint,
    ExecutionBackend,
    ExecutionPlan,
    ExecutionRequest,
    ExecutionStep,
    MergeStrategy,
    StepStatus,
)
from gracekelly.core.decomposition import execute_decomposed
from gracekelly.core.models import resolve_model
from gracekelly.core.pattern_resolver import resolve_from_level, resolve_from_pattern
from gracekelly.core.patterns import ExecutionPattern
from gracekelly.core.reliability import ReliabilityLevel
from gracekelly.core.role_executor import RoleExecutor
from gracekelly.core.task_classifier import classify_task

router = APIRouter(prefix="/api/v1", tags=["smart"])
logger = logging.getLogger(__name__)


class SmartRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=40000)
    model: str = Field(default="mistral-small", min_length=1, max_length=120)
    reliability_level: str | None = Field(default=None)
    pattern: str | None = Field(default=None)


class SmartResponse(BaseModel):
    answer: str
    task_type: str
    complexity_level: str
    pattern_used: str
    reliability_level: str
    was_decomposed: bool
    used_consensus: bool
    used_roles: bool
    total_llm_calls: int
    model_id: str


@router.post("/smart", response_model=SmartResponse)
def run_smart(payload: SmartRequest, request: Request) -> SmartResponse:
    api_adapters = getattr(request.app.state, "api_adapters", {})
    embeddings_client = getattr(request.app.state, "embeddings_client", None)

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

    if payload.reliability_level is not None and payload.pattern is not None:
        raise HTTPException(status_code=400, detail="Use reliability_level OR pattern, not both.")

    if payload.pattern is not None:
        try:
            resolved = resolve_from_pattern(ExecutionPattern(payload.pattern))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown pattern: {payload.pattern}")
    elif payload.reliability_level is not None:
        try:
            resolved = resolve_from_level(ReliabilityLevel(payload.reliability_level))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Unknown level: {payload.reliability_level}")
    else:
        complexity = assess_complexity(payload.prompt)
        if complexity.should_decompose:
            resolved = resolve_from_level(ReliabilityLevel.HIGH)
        elif complexity.level.value == "complex":
            resolved = resolve_from_level(ReliabilityLevel.STANDARD)
        else:
            resolved = resolve_from_level(ReliabilityLevel.QUICK)

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

    call_count = {"n": 0}

    def execute_fn(prompt_text: str) -> str:
        call_count["n"] += 1
        exec_request = ExecutionRequest(
            task_id="smart",
            prompt=prompt_text,
            plan=plan,
            step=step,
            reasoning=resolved.reasoning,
        )
        result = adapter.execute(exec_request)
        if result.status == StepStatus.COMPLETED and result.output_text:
            return result.output_text
        return f"[{result.failure_code or 'error'}] {result.failure_message or 'No output'}"

    task_type = classify_task(payload.prompt)
    used_consensus = False
    was_decomposed = False
    answer: str

    if resolved.use_decomposition:
        decomp_result = execute_decomposed(payload.prompt, execute_fn)
        answer = decomp_result.final_answer
        was_decomposed = decomp_result.was_decomposed
    elif resolved.use_consensus and embeddings_client is not None:
        consensus_config = ConsensusConfig(
            consensus_target=resolved.consensus_threshold,
            max_rounds=resolved.max_consensus_rounds,
        )
        exec_config = ConsensusExecutionConfig(
            consensus_config=consensus_config,
        )
        executor = ConsensusExecutor(embeddings_client, exec_config)
        consensus_result = executor.execute(payload.prompt, execute_fn)
        answer = consensus_result.best_response
        used_consensus = True
    else:
        answer = execute_fn(payload.prompt)

    used_roles = False
    if resolved.roles and len(resolved.roles) > 0:
        role_exec = RoleExecutor(execute_fn)
        answer, _ = role_exec.execute_and_verify(payload.prompt)
        used_roles = True

    return SmartResponse(
        answer=answer,
        task_type=task_type.value,
        complexity_level=assess_complexity(payload.prompt).level.value,
        pattern_used=resolved.pattern.value,
        reliability_level=resolved.reliability_level.value,
        was_decomposed=was_decomposed,
        used_consensus=used_consensus,
        used_roles=used_roles,
        total_llm_calls=call_count["n"],
        model_id=model_spec.id,
    )
```

That is the COMPLETE implementation. Copy it exactly.

### test_smart_route.py specification

```python
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gracekelly.api.routes.smart import router
from gracekelly.core.embeddings import EmbeddingsClient
from gracekelly.core.contracts import StepStatus


def _create_test_app(*, has_embeddings: bool = True) -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    adapter = MagicMock()
    adapter.execute.return_value = MagicMock(
        status=StepStatus.COMPLETED,
        output_text="Test response. Confidence: 8/10",
        failure_code=None,
        failure_message=None,
    )
    app.state.api_adapters = {"mistral": adapter}

    if has_embeddings:
        embeddings = MagicMock(spec=EmbeddingsClient)
        embeddings.embed.return_value = [1.0, 0.0, 0.0]
        embeddings.embed_batch.side_effect = lambda texts: [[1.0, 0.0, 0.0] for _ in texts]
        app.state.embeddings_client = embeddings
    else:
        app.state.embeddings_client = None

    return app
```

Exactly these tests:

1. `test_smart_returns_200` — POST with valid prompt → 200
2. `test_smart_response_has_answer` — response has non-empty "answer" field
3. `test_smart_auto_detects_task_type` — "Write Python code" → task_type == "coding"
4. `test_smart_simple_prompt_uses_quick` — "What is 2+2?" → reliability_level == "quick"
5. `test_smart_explicit_level` — reliability_level="maximum" → reliability_level == "maximum"
6. `test_smart_explicit_pattern` — pattern="consensus" → pattern_used == "consensus"
7. `test_smart_both_level_and_pattern_returns_400` — both set → 400
8. `test_smart_invalid_model_returns_400` — model="nonexistent" → 400
9. `test_smart_invalid_level_returns_400` — reliability_level="ultra" → 400
10. `test_smart_invalid_pattern_returns_400` — pattern="nonexistent" → 400
11. `test_smart_total_llm_calls_positive` — total_llm_calls >= 1
12. `test_smart_model_id_present` — model_id is non-empty string
13. `test_smart_complexity_level_present` — complexity_level is one of "simple", "moderate", "complex"
14. `test_smart_no_embeddings_falls_back` — has_embeddings=False, pattern=consensus → still returns 200 (falls back to direct execution)

End with:
```python
if __name__ == "__main__":
    unittest.main()
```

## DONE WHEN
- [ ] `src/gracekelly/api/routes/smart.py` exists
- [ ] `tests/test_smart_route.py` exists with exactly 14 test methods
- [ ] `python -m pytest tests/test_smart_route.py -q` → 14 passed, 0 failed
- [ ] `python -m pytest -q` → all existing tests still pass (693+)
- [ ] No existing files modified

## SELF-EVALUATION
After completing, score yourself 1-10:
- Does the route correctly chain: classify → complexity → resolve → decompose/consensus/direct → roles → return?
- Do all 14 tests pass including edge cases (both level+pattern, no embeddings)?
- Is there any code beyond the specification?

Target: 9.8/10.
```
