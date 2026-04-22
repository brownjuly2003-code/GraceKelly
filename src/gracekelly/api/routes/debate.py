from __future__ import annotations

import asyncio
import inspect
import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from gracekelly.api.routes._helpers import resolve_execution_adapter
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
from gracekelly.core.debate_round import run_debate
from gracekelly.core.models import resolve_model

router = APIRouter(prefix="/api/v1", tags=["debate"])
logger = logging.getLogger(__name__)


class DebateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1, max_length=40000)
    initial_position: str | None = Field(default=None, max_length=40000)
    model: str = Field(default="mistral-small", min_length=1, max_length=120)
    dry_run: bool = Field(default=False)


class DebateResponse(BaseModel):
    initial_position: str
    challenge: str
    defense: str
    improved_response: str
    model_id: str
    total_llm_calls: int


@router.post(
    "/debate",
    response_model=DebateResponse,
    summary="Run a Devil's Advocate debate round",
    description=(
        "Generates an initial position on the topic, then runs a structured debate: "
        "challenge (Devil's Advocate), defense, and improved final response. "
        "Optionally supply your own `initial_position` to skip the first LLM call."
    ),
    response_description="Debate transcript: initial position, challenge, defense, improved response, and call count",
    responses={
        400: {"description": "Invalid model or no adapter available for the requested provider"},
    },
)
async def run_debate_endpoint(payload: DebateRequest, request: Request) -> DebateResponse:
    state = get_app_state(request)

    try:
        model_spec = resolve_model(payload.model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        adapter, backend = resolve_execution_adapter(state, model_spec, payload.dry_run)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    step = ExecutionStep(
        model=model_spec,
        backend=backend,
        provider=model_spec.provider,
        provider_model_id=model_spec.provider_model_id,
        step_index=0,
    )
    plan = ExecutionPlan(
        steps=(step,),
        quorum=1,
        merge_strategy=MergeStrategy.FIRST_SUCCESS,
        dry_run=payload.dry_run,
        adapter_hint=(
            AdapterHint.AUTO
            if payload.dry_run
            else AdapterHint.BROWSER if backend == ExecutionBackend.BROWSER else AdapterHint.API
        ),
        cancel_on_quorum=False,
    )

    call_count = {"n": 0}

    async def execute_request(prompt_text: str) -> str:
        call_count["n"] += 1
        exec_request = ExecutionRequest(
            task_id="debate",
            prompt=prompt_text,
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
            return result.output_text
        return f"[{result.failure_code or 'error'}] {result.failure_message or 'No output'}"

    def execute_fn(prompt_text: str) -> str:
        call_count["n"] += 1
        exec_request = ExecutionRequest(
            task_id="debate",
            prompt=prompt_text,
            plan=plan,
            step=step,
            reasoning=True,
        )
        result = adapter.execute(exec_request)
        if result.status == StepStatus.COMPLETED and result.output_text:
            return result.output_text
        return f"[{result.failure_code or 'error'}] {result.failure_message or 'No output'}"

    if payload.initial_position:
        initial = payload.initial_position
    else:
        initial = await execute_request(f"Take a clear position on this topic: {payload.topic}")

    debate_result = await asyncio.to_thread(run_debate, payload.topic, initial, execute_fn)

    return DebateResponse(
        initial_position=initial,
        challenge=debate_result.challenge,
        defense=debate_result.defense,
        improved_response=debate_result.improved_response,
        model_id=model_spec.id,
        total_llm_calls=call_count["n"],
    )
