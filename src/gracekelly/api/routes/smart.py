from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from gracekelly.app_state import get_app_state
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
    state = get_app_state(request)
    api_adapters = state.api_adapters
    embeddings_client = state.embeddings_client

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
