from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from gracekelly.app_state import get_app_state
from gracekelly.core.complexity import assess_complexity
from gracekelly.core.contracts import (
    AdapterHint,
    ExecutionBackend,
    ExecutionPlan,
    ExecutionRequest,
    ExecutionStep,
    MergeStrategy,
    StepStatus,
)
from gracekelly.core.models import MODEL_SPECS, ModelSpec, resolve_model
from gracekelly.core.multi_model import MultiModelExecutor
from gracekelly.core.pattern_resolver import resolve_from_level
from gracekelly.core.reliability import ReliabilityLevel
from gracekelly.core.task_classifier import classify_task

router = APIRouter(prefix="/api/v1", tags=["pipeline"])
logger = logging.getLogger(__name__)


class PipelineRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=40000)
    model: str = Field(default="mistral-small", min_length=1, max_length=120)
    reliability_level: str | None = Field(default=None)
    multi_model: bool = Field(default=False)


class PipelineResponse(BaseModel):
    answer: str
    task_type: str
    pattern_used: str
    reliability_level: str
    total_llm_calls: int
    model_id: str
    models_used: list[str] = Field(default_factory=list)


@router.post(
    "/pipeline",
    response_model=PipelineResponse,
    summary="Execute a reliability-level pipeline",
    description=(
        "Runs a prompt through a reliability-level-selected execution pattern. "
        "Set `multi_model=true` to fan out across all configured API providers and aggregate results."
    ),
    response_description="Pipeline answer with pattern, reliability level, model list, and LLM call count",
    responses={
        400: {"description": "Invalid model, unknown reliability level, or no adapter available"},
    },
)
async def run_pipeline(payload: PipelineRequest, request: Request) -> PipelineResponse:
    api_adapters = get_app_state(request).api_adapters

    try:
        model_spec = resolve_model(payload.model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    adapter = api_adapters.get(model_spec.provider)
    if adapter is None:
        raise HTTPException(
            status_code=400,
            detail=f"No adapter for '{model_spec.provider}'.",
        )

    if payload.reliability_level:
        try:
            resolved = resolve_from_level(ReliabilityLevel(payload.reliability_level))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown level: {payload.reliability_level}",
            )
    else:
        complexity = assess_complexity(payload.prompt)
        if complexity.level.value == "complex":
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
            task_id="pipeline",
            prompt=prompt_text,
            plan=plan,
            step=step,
            reasoning=resolved.reasoning,
        )
        if hasattr(type(adapter), "execute_async"):
            result = await adapter.execute_async(exec_request)
        else:
            result = adapter.execute(exec_request)
        if result.status == StepStatus.COMPLETED and result.output_text:
            return result.output_text
        return f"[{result.failure_code or 'error'}] {result.failure_message or 'No output'}"

    if payload.multi_model:
        available_specs: list[ModelSpec] = [model_spec]
        for provider_name, prov_adapter in api_adapters.items():
            if provider_name == model_spec.provider:
                continue
            if not getattr(prov_adapter, "has_api_key", False):
                continue
            for spec in MODEL_SPECS:
                if spec.provider == provider_name and spec.adapter_kind == "api":
                    available_specs.append(spec)
                    break
        executor = MultiModelExecutor(api_adapters, available_specs)
        mm_result = await asyncio.to_thread(
            executor.execute_all,
            payload.prompt, reasoning=resolved.reasoning,
        )
        call_count["n"] = len(mm_result.responses) + len(mm_result.failed_models)
        answer = mm_result.responses[0] if mm_result.responses else await execute_request(payload.prompt)
        models_used = list(mm_result.model_ids)
        if not models_used:
            models_used = [model_spec.id]
    else:
        answer = await execute_request(payload.prompt)
        models_used = [model_spec.id]

    task_type = classify_task(payload.prompt)

    return PipelineResponse(
        answer=answer,
        task_type=task_type.value,
        pattern_used=resolved.pattern.value,
        reliability_level=resolved.reliability_level.value,
        total_llm_calls=call_count["n"],
        model_id=model_spec.id,
        models_used=models_used,
    )
