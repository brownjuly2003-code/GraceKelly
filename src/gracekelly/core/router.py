from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from time import perf_counter

from gracekelly.core.concurrency import ModelConcurrencyGate
from gracekelly.core.contracts import (
    CancellationToken,
    ExecutionAdapter,
    ExecutionBatchResult,
    ExecutionMode,
    ExecutionPlan,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStep,
    FailureCode,
    MergeStrategy,
    StepStatus,
    TaskStatus,
)
from gracekelly.core.models import list_models


class ExecutionRouter:
    def __init__(
        self,
        dry_run_adapter: ExecutionAdapter,
        api_adapters: dict[str, ExecutionAdapter] | None = None,
        browser_adapter: ExecutionAdapter | None = None,
        concurrency_gate: ModelConcurrencyGate | None = None,
    ) -> None:
        self._dry_run_adapter = dry_run_adapter
        self._api_adapters = api_adapters or {}
        self._browser_adapter = browser_adapter
        self._concurrency_gate = concurrency_gate or ModelConcurrencyGate()
        self._model_limits = {
            model.id: model.concurrency_limit
            for model in list_models()
        }

    def execute(
        self,
        *,
        task_id: str,
        prompt: str,
        plan: ExecutionPlan,
        reasoning: bool,
        metadata: dict[str, object],
    ) -> ExecutionBatchResult:
        cancellation = CancellationToken()

        if plan.dry_run:
            return self._execute_sequential(
                task_id, prompt, plan, reasoning, metadata, cancellation,
            )
        return self._execute_parallel(
            task_id, prompt, plan, reasoning, metadata, cancellation,
        )

    def _execute_sequential(
        self,
        task_id: str,
        prompt: str,
        plan: ExecutionPlan,
        reasoning: bool,
        metadata: dict[str, object],
        cancellation: CancellationToken,
    ) -> ExecutionBatchResult:
        results: list[ExecutionResult] = []
        for step in plan.steps:
            request = ExecutionRequest(
                task_id=task_id, prompt=prompt, plan=plan, step=step,
                reasoning=reasoning, metadata=dict(metadata), cancellation=cancellation,
            )
            started = perf_counter()
            result = self._dry_run_adapter.execute(request)
            result = self._stamp_duration(result, started)
            results.append(result)
        return self._aggregate(plan, tuple(results))

    def _execute_parallel(
        self,
        task_id: str,
        prompt: str,
        plan: ExecutionPlan,
        reasoning: bool,
        metadata: dict[str, object],
        cancellation: CancellationToken,
    ) -> ExecutionBatchResult:
        indexed_results: dict[int, ExecutionResult] = {}

        def run_step(idx: int, step: ExecutionStep) -> tuple[int, ExecutionResult]:
            if cancellation.is_cancelled:
                return idx, self._cancelled_result(step)
            request = ExecutionRequest(
                task_id=task_id, prompt=prompt, plan=plan, step=step,
                reasoning=reasoning, metadata=dict(metadata), cancellation=cancellation,
            )
            started = perf_counter()
            result = self._dispatch_step(step, request)
            return idx, self._stamp_duration(result, started)

        with ThreadPoolExecutor(max_workers=len(plan.steps)) as pool:
            futures = {
                pool.submit(run_step, idx, step): idx
                for idx, step in enumerate(plan.steps)
            }
            for future in as_completed(futures):
                idx, result = future.result()
                indexed_results[idx] = result
                if (
                    plan.cancel_on_quorum
                    and self._successful_count(tuple(indexed_results.values())) >= plan.quorum
                ):
                    cancellation.request_cancel()

        ordered = []
        for idx in range(len(plan.steps)):
            if idx in indexed_results:
                ordered.append(indexed_results[idx])
            else:
                ordered.append(self._cancelled_result(plan.steps[idx]))
        return self._aggregate(plan, tuple(ordered))

    def _dispatch_step(self, step: ExecutionStep, request: ExecutionRequest) -> ExecutionResult:
        if step.backend.value == "api":
            adapter = self._api_adapters.get(step.provider)
            if adapter is None:
                return self._missing_adapter_result(
                    step.model.id, step.model.display_name,
                    adapter_name=f"{step.backend.value}.{step.provider}",
                    execution_mode=ExecutionMode.API,
                    message=f"No API adapter registered for provider '{step.provider}'.",
                )
            return self._execute_with_concurrency_limit(adapter, request)
        if self._browser_adapter is None:
            return self._missing_adapter_result(
                step.model.id, step.model.display_name,
                adapter_name=f"{step.backend.value}.{step.provider}",
                execution_mode=ExecutionMode.BROWSER,
                message="Browser adapter is not connected yet.",
            )
        return self._execute_with_concurrency_limit(self._browser_adapter, request)

    @staticmethod
    def _stamp_duration(result: ExecutionResult, started: float) -> ExecutionResult:
        if result.duration_ms is not None:
            return result
        duration_ms = max(0, int((perf_counter() - started) * 1000))
        return replace(result, duration_ms=duration_ms)

    def _aggregate(
        self,
        plan: ExecutionPlan,
        results: tuple[ExecutionResult, ...],
    ) -> ExecutionBatchResult:
        execution_mode = ExecutionMode.DRY_RUN if plan.dry_run else self._resolve_execution_mode(results)
        successful = tuple(item for item in results if item.status == StepStatus.COMPLETED)
        failed = tuple(item for item in results if item.status == StepStatus.FAILED)
        failure_codes = sorted(
            item.failure_code.value
            for item in failed
            if item.failure_code is not None
        )
        cancelled_steps = [
            step.step_index
            for step, result in zip(plan.steps, results, strict=True)
            if result.status == StepStatus.CANCELLED
        ]
        winning_step = None
        if plan.merge_strategy == MergeStrategy.FIRST_SUCCESS or len(plan.steps) == 1:
            winning_step = next(
                (
                    (step, result)
                    for step, result in zip(plan.steps, results, strict=True)
                    if result.status == StepStatus.COMPLETED
                ),
                None,
            )

        if plan.dry_run:
            task_status = TaskStatus.COMPLETED
            failure_code = None
            failure_message = None
            output_text = None
        elif len(successful) >= plan.quorum:
            task_status = TaskStatus.COMPLETED
            failure_code = None
            failure_message = None
            output_text = self._merge_outputs(plan.merge_strategy, successful)
        elif failed:
            task_status = TaskStatus.FAILED
            failure_code, failure_message = self._resolve_task_failure(failed)
            output_text = None
        else:
            task_status = TaskStatus.CANCELLED
            failure_code = None
            failure_message = None
            output_text = None

        details = {
            "quorum": plan.quorum,
            "merge_strategy": plan.merge_strategy,
            "adapter_names": sorted({item.adapter_name for item in results}),
            "completed_step_count": len(successful),
            "failed_step_count": len(failed),
            "cancelled_step_count": len(cancelled_steps),
            "failure_codes": failure_codes,
            "winning_step_index": winning_step[0].step_index if winning_step else None,
            "winning_model_id": winning_step[1].model_id if winning_step else None,
            "cancelled_steps": cancelled_steps,
            "cancel_reason": "quorum_reached" if cancelled_steps and task_status == TaskStatus.COMPLETED else None,
        }
        return ExecutionBatchResult(
            execution_mode=execution_mode,
            task_status=task_status,
            results=results,
            output_text=output_text,
            failure_code=failure_code,
            failure_message=failure_message,
            details=details,
        )

    def healthcheck(self) -> dict[str, object]:
        active_by_model = self._concurrency_gate.snapshot()
        saturated_models = sorted(
            model_id
            for model_id, active in active_by_model.items()
            if active >= self._model_limits.get(model_id, 1)
        )
        return {
            "status": "ok",
            "active_model_executions": sum(active_by_model.values()),
            "active_by_model": active_by_model,
            "model_limits": dict(self._model_limits),
            "saturated_models": saturated_models,
        }

    def _successful_count(self, results: tuple[ExecutionResult, ...]) -> int:
        return sum(1 for item in results if item.status == StepStatus.COMPLETED)

    def _resolve_execution_mode(self, results: tuple[ExecutionResult, ...]) -> ExecutionMode:
        execution_modes = sorted({item.execution_mode for item in results})
        return execution_modes[0] if len(execution_modes) == 1 else ExecutionMode.MIXED

    def _merge_outputs(
        self,
        merge_strategy: MergeStrategy,
        results: tuple[ExecutionResult, ...],
    ) -> str | None:
        outputs = [item.output_text for item in results if item.output_text]
        if not outputs:
            return None
        if merge_strategy == MergeStrategy.FIRST_SUCCESS:
            return outputs[0]
        return "\n\n".join(outputs)

    def _resolve_task_failure(
        self,
        failed: tuple[ExecutionResult, ...],
    ) -> tuple[FailureCode, str]:
        first_failure = failed[0]
        failure_codes = {item.failure_code for item in failed if item.failure_code is not None}
        if len(failed) == 1 and first_failure.failure_code is not None and first_failure.failure_message:
            return first_failure.failure_code, first_failure.failure_message
        if len(failure_codes) == 1 and first_failure.failure_code is not None:
            return (
                first_failure.failure_code,
                f"All {len(failed)} steps failed: {first_failure.failure_message or first_failure.failure_code.value}",
            )
        summary = ", ".join(
            f"{item.model_id}={item.failure_code.value if item.failure_code else FailureCode.UNKNOWN_ERROR.value}"
            for item in failed
        )
        return FailureCode.UNKNOWN_ERROR, f"{len(failed)} steps failed with different errors: {summary}"

    def _missing_adapter_result(
        self,
        model_id: str,
        model_display_name: str,
        *,
        adapter_name: str,
        execution_mode: ExecutionMode,
        message: str,
    ) -> ExecutionResult:
        return ExecutionResult(
            adapter_name=adapter_name,
            model_id=model_id,
            model_display_name=model_display_name,
            execution_mode=execution_mode,
            status=StepStatus.FAILED,
            failure_code=FailureCode.PROVIDER_UNAVAILABLE,
            failure_message=message,
            details={"configured": False},
        )

    def _execute_with_concurrency_limit(
        self,
        adapter: ExecutionAdapter,
        request: ExecutionRequest,
    ) -> ExecutionResult:
        step = request.step
        acquired = self._concurrency_gate.try_acquire(
            step.model.id,
            limit=step.model.concurrency_limit,
        )
        if not acquired:
            return self._concurrency_limited_result(step)
        try:
            return adapter.execute(request)
        finally:
            self._concurrency_gate.release(step.model.id)

    def _concurrency_limited_result(self, step: ExecutionStep) -> ExecutionResult:
        return ExecutionResult(
            adapter_name=f"{step.backend.value}.{step.provider}",
            model_id=step.model.id,
            model_display_name=step.model.display_name,
            execution_mode=ExecutionMode(step.backend.value),
            status=StepStatus.FAILED,
            failure_code=FailureCode.RATE_LIMITED,
            failure_message=(
                f"Concurrency limit reached for model '{step.model.display_name}' "
                f"(limit={step.model.concurrency_limit})."
            ),
            details={
                "provider": step.provider,
                "concurrency_limit": step.model.concurrency_limit,
            },
        )

    def _cancelled_result(self, step: ExecutionStep) -> ExecutionResult:
        return ExecutionResult(
            adapter_name=f"{step.backend.value}.{step.provider}",
            model_id=step.model.id,
            model_display_name=step.model.display_name,
            execution_mode=ExecutionMode(step.backend.value),
            status=StepStatus.CANCELLED,
            details={"cancelled": True},
        )
