from __future__ import annotations

from gracekelly.core.contracts import ExecutionBackend, ExecutionPlan, ExecutionStep, MergeStrategy
from gracekelly.core.models import resolve_model
from gracekelly.schemas import OrchestrateRequest


def build_execution_plan(request: OrchestrateRequest) -> ExecutionPlan:
    requested_models = []
    seen_model_ids: set[str] = set()

    for requested_name in request.requested_model_names():
        model = resolve_model(requested_name)
        if model.id in seen_model_ids:
            raise ValueError(
                f"Duplicate model request after canonicalization: "
                f"'{requested_name}' resolves to '{model.display_name}', which is already requested."
            )
        seen_model_ids.add(model.id)
        requested_models.append(model)

    requested_models = tuple(requested_models)
    if request.reasoning:
        unsupported_reasoning_models = [
            model.display_name for model in requested_models if not model.reasoning_capable
        ]
        if unsupported_reasoning_models:
            raise ValueError(
                "reasoning=true is not supported for: "
                + ", ".join(unsupported_reasoning_models)
            )
    steps = []

    for step_index, model in enumerate(requested_models, start=1):
        backend = ExecutionBackend(model.adapter_kind)
        if request.adapter_hint != "auto" and request.adapter_hint != backend.value:
            raise ValueError(
                f"Model '{model.display_name}' requires backend '{backend.value}', "
                f"but adapter_hint is '{request.adapter_hint}'."
            )

        steps.append(
            ExecutionStep(
                model=model,
                backend=backend,
                provider=model.provider,
                provider_model_id=model.provider_model_id,
                step_index=step_index,
            )
        )

    quorum = min(request.quorum, len(steps))
    if (
        request.merge_strategy == MergeStrategy.CONCAT
        and len(steps) > 1
        and request.cancel_on_quorum
        and quorum < len(steps)
    ):
        raise ValueError(
            "merge_strategy='concat' cannot be combined with cancel_on_quorum=true "
            "unless quorum covers all requested models."
        )
    return ExecutionPlan(
        steps=tuple(steps),
        quorum=quorum,
        merge_strategy=request.merge_strategy,
        dry_run=request.dry_run,
        adapter_hint=request.adapter_hint,
        cancel_on_quorum=request.cancel_on_quorum,
    )
