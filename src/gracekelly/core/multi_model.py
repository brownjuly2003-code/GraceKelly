from __future__ import annotations

import logging
from dataclasses import dataclass

from gracekelly.core.contracts import (
    AdapterHint,
    ExecutionBackend,
    ExecutionMode,
    ExecutionPlan,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStep,
    MergeStrategy,
    StepStatus,
)
from gracekelly.core.models import ModelSpec

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MultiModelResult:
    responses: tuple[str, ...]
    model_ids: tuple[str, ...]
    failed_models: tuple[str, ...]


class MultiModelExecutor:
    def __init__(
        self,
        adapters: dict[str, object],
        model_specs: list[ModelSpec],
    ) -> None:
        self._adapters = adapters
        self._model_specs = model_specs

    def execute_all(
        self, prompt: str, reasoning: bool = False
    ) -> MultiModelResult:
        responses: list[str] = []
        model_ids: list[str] = []
        failed: list[str] = []
        for spec in self._model_specs:
            adapter = self._adapters.get(spec.provider)
            if adapter is None:
                failed.append(spec.id)
                continue
            step = ExecutionStep(
                model=spec,
                backend=ExecutionBackend.API,
                provider=spec.provider,
                provider_model_id=spec.provider_model_id,
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
            try:
                result = adapter.execute(
                    ExecutionRequest(
                        task_id="multi-model",
                        prompt=prompt,
                        plan=plan,
                        step=step,
                        reasoning=reasoning,
                    )
                )
                if (
                    result.status == StepStatus.COMPLETED
                    and result.output_text
                ):
                    responses.append(result.output_text)
                    model_ids.append(spec.id)
                else:
                    failed.append(spec.id)
            except Exception:
                failed.append(spec.id)
                logger.warning("Model %s failed", spec.id)
        return MultiModelResult(
            tuple(responses), tuple(model_ids), tuple(failed)
        )
