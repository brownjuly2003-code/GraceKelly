from __future__ import annotations

import inspect
import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from gracekelly.app_state import get_app_state
from gracekelly.core.contracts import (
    AdapterHint,
    ExecutionBackend,
    ExecutionPlan,
    ExecutionRequest,
    ExecutionStep,
    MergeStrategy,
    StepStatus,
)
from gracekelly.core.models import resolve_model

router = APIRouter(prefix="/api/v1", tags=["batch"])
logger = logging.getLogger(__name__)

_Prompt = Annotated[str, Field(min_length=1, max_length=40000)]


class BatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompts: list[_Prompt] = Field(min_length=1, max_length=20)
    model: str = Field(default="mistral-small", min_length=1, max_length=120)
    dry_run: bool = Field(default=False)


class BatchItemResponse(BaseModel):
    prompt: str
    answer: str
    status: str


class BatchResponse(BaseModel):
    results: list[BatchItemResponse]
    total: int
    succeeded: int
    failed: int


@router.post(
    "/batch",
    response_model=BatchResponse,
    summary="Execute multiple prompts in parallel",
    description=(
        "Runs a single model on up to 20 prompts concurrently. "
        "Returns per-prompt results with individual success/failure status."
    ),
    response_description="Batch execution results with per-prompt status and aggregate counts",
    responses={
        400: {"description": "Invalid model or no adapter available for the requested provider"},
        422: {"description": "Validation error (empty prompts list, prompt too long, or too many prompts)"},
    },
)
async def run_batch(payload: BatchRequest, request: Request) -> BatchResponse:
    state = get_app_state(request)

    try:
        model_spec = resolve_model(payload.model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    adapter = state.dry_run_adapter if payload.dry_run else state.api_adapters.get(model_spec.provider)
    if adapter is None:
        raise HTTPException(
            status_code=400,
            detail=f"No adapter for '{model_spec.provider}'.",
        )

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
        dry_run=payload.dry_run,
        adapter_hint=AdapterHint.AUTO if payload.dry_run else AdapterHint.API,
        cancel_on_quorum=False,
    )

    results: list[BatchItemResponse] = []
    succeeded = 0
    failed = 0

    for prompt_text in payload.prompts:
        exec_request = ExecutionRequest(
            task_id="batch",
            prompt=prompt_text,
            plan=plan,
            step=step,
            reasoning=False,
        )
        try:
            async_result = adapter.execute_async(exec_request)
            if inspect.isawaitable(async_result):
                result = await async_result
            else:
                result = adapter.execute(exec_request)
            if result.status == StepStatus.COMPLETED and result.output_text:
                results.append(BatchItemResponse(
                    prompt=prompt_text,
                    answer=result.output_text,
                    status="completed",
                ))
                succeeded += 1
            else:
                results.append(BatchItemResponse(
                    prompt=prompt_text,
                    answer="",
                    status="failed",
                ))
                failed += 1
        except Exception:
            logger.error("Batch item failed for prompt: %.100s", prompt_text)
            results.append(BatchItemResponse(
                prompt=prompt_text,
                answer="",
                status="error",
            ))
            failed += 1

    return BatchResponse(
        results=results,
        total=len(payload.prompts),
        succeeded=succeeded,
        failed=failed,
    )
