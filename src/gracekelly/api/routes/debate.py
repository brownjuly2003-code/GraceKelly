from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

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
    topic: str = Field(min_length=1, max_length=40000)
    initial_position: str | None = Field(default=None, max_length=40000)
    model: str = Field(default="mistral-small", min_length=1, max_length=120)


class DebateResponse(BaseModel):
    initial_position: str
    challenge: str
    defense: str
    improved_response: str
    model_id: str
    total_llm_calls: int


@router.post("/debate", response_model=DebateResponse)
def run_debate_endpoint(payload: DebateRequest, request: Request) -> DebateResponse:
    api_adapters = get_app_state(request).api_adapters

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
        initial = execute_fn(f"Take a clear position on this topic: {payload.topic}")

    debate_result = run_debate(payload.topic, initial, execute_fn)

    return DebateResponse(
        initial_position=initial,
        challenge=debate_result.challenge,
        defense=debate_result.defense,
        improved_response=debate_result.improved_response,
        model_id=model_spec.id,
        total_llm_calls=call_count["n"],
    )
