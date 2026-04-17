from __future__ import annotations

import inspect
import logging

from fastapi import APIRouter, Request
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

router = APIRouter(prefix="/api/v1", tags=["compare"])
logger = logging.getLogger(__name__)


class CompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=40000)
    models: list[str] = Field(default_factory=lambda: ["mistral-small"], min_length=1, max_length=10)
    analyze: bool = Field(default=True)
    dry_run: bool = Field(default=False)


class ModelAnswer(BaseModel):
    model_id: str
    answer: str
    status: str


class CompareResponse(BaseModel):
    answers: list[ModelAnswer]
    analysis: str | None
    total_models: int
    succeeded: int
    failed: int


@router.post(
    "/compare",
    response_model=CompareResponse,
    summary="Compare answers from multiple models",
    description=(
        "Runs the same prompt on each requested model concurrently. "
        "When `analyze=true` and at least two models succeed, an additional LLM call "
        "summarizes differences, strengths, and the best answer."
    ),
    response_description="Per-model answers with optional comparative analysis and aggregate success counts",
    responses={
        422: {"description": "Validation error (empty models list or prompt too long)"},
    },
)
async def run_compare(payload: CompareRequest, request: Request) -> CompareResponse:
    state = get_app_state(request)
    api_adapters = state.api_adapters

    answers: list[ModelAnswer] = []
    succeeded = 0
    failed = 0

    for model_name in payload.models:
        try:
            model_spec = resolve_model(model_name)
        except ValueError:
            answers.append(ModelAnswer(model_id=model_name, answer="", status="unknown_model"))
            failed += 1
            continue

        adapter = state.dry_run_adapter if payload.dry_run else api_adapters.get(model_spec.provider)
        if adapter is None:
            answers.append(ModelAnswer(model_id=model_spec.id, answer="", status="no_adapter"))
            failed += 1
            continue

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

        try:
            exec_request = ExecutionRequest(
                task_id="compare",
                prompt=payload.prompt,
                plan=plan,
                step=step,
                reasoning=True,
            )
            async_result = adapter.execute_async(exec_request)
            if inspect.isawaitable(async_result):
                result = await async_result
            else:
                result = adapter.execute(exec_request)
            if result.status == StepStatus.COMPLETED and result.output_text:
                answers.append(ModelAnswer(model_id=model_spec.id, answer=result.output_text, status="completed"))
                succeeded += 1
            else:
                answers.append(ModelAnswer(model_id=model_spec.id, answer="", status="failed"))
                failed += 1
        except Exception:
            logger.error("Compare failed for model %s", model_spec.id)
            answers.append(ModelAnswer(model_id=model_spec.id, answer="", status="error"))
            failed += 1

    analysis = None
    if payload.analyze and succeeded >= 2:
        completed = [a for a in answers if a.status == "completed"]
        analysis_prompt = f"Original question: {payload.prompt}\n\n"
        for a in completed:
            analysis_prompt += f"[{a.model_id}]: {a.answer[:1000]}\n\n"
        analysis_prompt += (
            "Compare these answers. Identify key differences, strengths, and weaknesses "
            "of each. Which answer is best and why? Be concise."
        )

        first_adapter = None
        first_spec = None
        for model_name in payload.models:
            try:
                spec = resolve_model(model_name)
                adp = state.dry_run_adapter if payload.dry_run else api_adapters.get(spec.provider)
                if adp is not None:
                    first_adapter = adp
                    first_spec = spec
                    break
            except ValueError:
                continue

        if first_adapter and first_spec:
            step = ExecutionStep(
                model=first_spec,
                backend=ExecutionBackend.API,
                provider=first_spec.provider,
                provider_model_id=first_spec.provider_model_id,
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
            try:
                exec_request = ExecutionRequest(
                    task_id="compare-analysis",
                    prompt=analysis_prompt,
                    plan=plan,
                    step=step,
                    reasoning=True,
                )
                async_result = first_adapter.execute_async(exec_request)
                if inspect.isawaitable(async_result):
                    result = await async_result
                else:
                    result = first_adapter.execute(exec_request)
                if result.status == StepStatus.COMPLETED and result.output_text:
                    analysis = result.output_text
            except Exception:
                logger.error("Compare analysis failed")

    return CompareResponse(
        answers=answers,
        analysis=analysis,
        total_models=len(payload.models),
        succeeded=succeeded,
        failed=failed,
    )
