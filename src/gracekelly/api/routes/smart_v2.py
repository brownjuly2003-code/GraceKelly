from __future__ import annotations

import asyncio
import inspect
import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from gracekelly.app_state import get_app_state
from gracekelly.core.complexity import assess_complexity
from gracekelly.core.consensus_v2 import ConsensusExecutorV2, ConsensusV2Config
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
__all__ = ["ConsensusExecutorV2"]


class SmartV2Request(BaseModel):
    prompt: str = Field(min_length=1, max_length=40000)
    model: str = Field(default="mistral-small", min_length=1, max_length=120)
    reliability_level: str | None = Field(default=None)
    pattern: str | None = Field(default=None)


class DissentingViewResponse(BaseModel):
    perspective: str
    support_ratio: float


class SmartV2Response(BaseModel):
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
    consensus_status: str | None
    consensus_score: float | None
    cluster_confidence: float | None
    dissenting_views: list[DissentingViewResponse]


@router.post(
    "/smart/v2",
    response_model=SmartV2Response,
    summary="Auto-routing smart execution with Consensus V2",
    description=(
        "Like /smart but uses the Consensus V2 engine when consensus is required: "
        "HAC clustering, cross-pollination, debate rounds, divergence handling, and dissenting-view extraction. "
        "Returns cluster confidence and dissenting perspectives alongside the best answer."
    ),
    response_description="Answer with V2 consensus metadata: cluster confidence, dissenting views, consensus score",
    responses={
        400: {"description": "Invalid model, unknown pattern/reliability level, or conflicting options"},
    },
)
async def run_smart_v2(payload: SmartV2Request, request: Request) -> SmartV2Response:
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
        raise HTTPException(
            status_code=400,
            detail="Use reliability_level OR pattern, not both.",
        )

    if payload.pattern is not None:
        try:
            resolved = resolve_from_pattern(ExecutionPattern(payload.pattern))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown pattern: {payload.pattern}",
            )
    elif payload.reliability_level is not None:
        try:
            resolved = resolve_from_level(ReliabilityLevel(payload.reliability_level))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown level: {payload.reliability_level}",
            )
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

    async def execute_request(prompt_text: str) -> str:
        call_count["n"] += 1
        exec_request = ExecutionRequest(
            task_id="smart-v2",
            prompt=prompt_text,
            plan=plan,
            step=step,
            reasoning=resolved.reasoning,
        )
        async_result = adapter.execute_async(exec_request)
        if inspect.isawaitable(async_result):
            result = await async_result
        else:
            result = adapter.execute(exec_request)
        if result.status == StepStatus.COMPLETED and result.output_text:
            return result.output_text
        return f"[{result.failure_code or 'error'}] {result.failure_message or 'No output'}"

    def execute_fn(prompt_text: str) -> str:
        call_count["n"] += 1
        exec_request = ExecutionRequest(
            task_id="smart-v2",
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
    consensus_status: str | None = None
    consensus_score: float | None = None
    cluster_confidence: float | None = None
    dissenting_views: list[DissentingViewResponse] = []
    answer: str

    if resolved.use_decomposition:
        decomp_result = await asyncio.to_thread(execute_decomposed, payload.prompt, execute_fn)
        answer = decomp_result.final_answer
        was_decomposed = decomp_result.was_decomposed
    elif resolved.use_consensus and embeddings_client is not None:
        v2_config = ConsensusV2Config(
            use_adaptive_params=True,
            use_debate=True,
            use_cross_pollination=True,
            use_cluster_confidence=True,
            use_divergence_handling=True,
        )
        executor = ConsensusExecutorV2(embeddings_client, v2_config)
        v2_result = await asyncio.to_thread(executor.execute, payload.prompt, execute_fn)
        answer = v2_result.best_response
        used_consensus = True
        consensus_status = v2_result.final_result.status.value
        consensus_score = v2_result.consensus_result.consensus_score
        cluster_confidence = v2_result.weighted_score
        dissenting_views = [
            DissentingViewResponse(
                perspective=dv.perspective[:500],
                support_ratio=dv.support_ratio,
            )
            for dv in v2_result.final_result.dissenting_views
        ]
    else:
        answer = await execute_request(payload.prompt)

    used_roles = False
    if resolved.roles and len(resolved.roles) > 0:
        role_exec = RoleExecutor(execute_fn)
        answer, _ = await asyncio.to_thread(role_exec.execute_and_verify, payload.prompt)
        used_roles = True

    return SmartV2Response(
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
        consensus_status=consensus_status,
        consensus_score=consensus_score,
        cluster_confidence=cluster_confidence,
        dissenting_views=dissenting_views,
    )
