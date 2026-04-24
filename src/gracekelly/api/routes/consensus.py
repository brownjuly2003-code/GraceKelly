from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from gracekelly.api.routes._helpers import resolve_effective_dry_run, resolve_execution_adapter
from gracekelly.app_state import get_app_state
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
from gracekelly.core.models import resolve_model

router = APIRouter(prefix="/api/v1", tags=["consensus"])
logger = logging.getLogger(__name__)


class ConsensusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=40000)
    model: str = Field(default="claude-sonnet-4-6", min_length=1, max_length=120)
    similarity_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    consensus_target: float = Field(default=0.95, ge=0.0, le=1.0)
    max_rounds: int = Field(default=5, ge=1, le=20)
    variations_per_round: int = Field(default=3, ge=1, le=9)
    use_confidence_weighting: bool = True
    dry_run: bool = Field(default=False)


class ConsensusResponse(BaseModel):
    consensus_score: float
    num_clusters: int
    best_response: str
    weighted_score: float | None
    total_rounds: int
    total_llm_calls: int
    needs_debate: bool
    top_cluster_size: int


@router.post(
    "/consensus",
    response_model=ConsensusResponse,
    summary="Run iterative consensus V1",
    description=(
        "Generates multiple response variations per round, clusters them by semantic similarity, "
        "and iterates until the top cluster reaches the consensus target. "
        "Requires an embeddings client to be configured."
    ),
    response_description="Consensus result with score, cluster count, best response, and round statistics",
    responses={
        400: {"description": "Invalid model or no adapter available for the requested provider"},
        503: {"description": "Embeddings client is not configured"},
        500: {"description": "Consensus execution failed (internal error)"},
    },
)
def run_consensus(payload: ConsensusRequest, request: Request) -> ConsensusResponse:
    state = get_app_state(request)

    try:
        model_spec = resolve_model(payload.model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    effective_dry_run = resolve_effective_dry_run(state, payload.dry_run)
    try:
        adapter, backend = resolve_execution_adapter(state, model_spec, effective_dry_run)
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
        dry_run=effective_dry_run,
        adapter_hint=(
            AdapterHint.AUTO
            if effective_dry_run
            else AdapterHint.BROWSER if backend == ExecutionBackend.BROWSER else AdapterHint.API
        ),
        cancel_on_quorum=False,
    )

    if effective_dry_run:
        responses: list[str] = []
        for _ in range(payload.variations_per_round):
            exec_request = ExecutionRequest(
                task_id="consensus",
                prompt=payload.prompt,
                plan=plan,
                step=step,
                reasoning=False,
            )
            exec_result = adapter.execute(exec_request)
            if exec_result.status == StepStatus.COMPLETED and exec_result.output_text:
                responses.append(exec_result.output_text)
            else:
                responses.append(
                    f"[{exec_result.failure_code or 'error'}] {exec_result.failure_message or 'No output'}"
                )
        return ConsensusResponse(
            consensus_score=1.0,
            num_clusters=1,
            best_response=responses[0],
            weighted_score=1.0,
            total_rounds=1,
            total_llm_calls=len(responses),
            needs_debate=False,
            top_cluster_size=len(responses),
        )

    embeddings_client = state.embeddings_client
    if embeddings_client is None:
        raise HTTPException(status_code=503, detail="Embeddings client is not configured.")

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
        consensus_result = executor.execute(payload.prompt, execute_fn)
    except Exception as exc:
        logger.error("Consensus execution failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Consensus execution failed: {exc}") from exc

    return ConsensusResponse(
        consensus_score=consensus_result.consensus_result.consensus_score,
        num_clusters=consensus_result.consensus_result.num_clusters,
        best_response=consensus_result.best_response,
        weighted_score=consensus_result.weighted_score,
        total_rounds=consensus_result.total_rounds,
        total_llm_calls=consensus_result.total_llm_calls,
        needs_debate=consensus_result.consensus_result.needs_debate,
        top_cluster_size=consensus_result.consensus_result.top_cluster.size,
    )
