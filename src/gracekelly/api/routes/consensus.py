from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

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
        logger.error("Consensus execution failed: %s", exc)
        raise HTTPException(status_code=500, detail="Consensus execution failed.")

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
