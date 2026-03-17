from __future__ import annotations

from dataclasses import replace
from time import perf_counter

from gracekelly.core.contracts import (
    CancellationToken,
    ExecutionAdapter,
    ExecutionBatchResult,
    ExecutionPlan,
    ExecutionRequest,
    ExecutionResult,
    FailureCode,
    MergeStrategy,
    StepStatus,
    TaskStatus,
)


class ExecutionRouter:
    def __init__(
        self,
        dry_run_adapter: ExecutionAdapter,
        api_adapters: dict[str, ExecutionAdapter] | None = None,
        browser_adapter: ExecutionAdapter | None = None,
    ) -> None:
        self._dry_run_adapter = dry_run_adapter
        self._api_adapters = api_adapters or {}
        self._browser_adapter = browser_adapter

    def execute(
        self,
        *,
        task_id: str,
        prompt: str,
        plan: ExecutionPlan,
        reasoning: bool,
        metadata: dict[str, object],
    ) -> ExecutionBatchResult:
        results: list[ExecutionResult] = []
        cancellation = CancellationToken()

        for step in plan.steps:
            if not plan.dry_run and cancellation.is_cancelled:
                results.append(self._cancelled_result(step))
                continue

            request = ExecutionRequest(
                task_id=task_id,
                prompt=prompt,
                plan=plan,
                step=step,
                reasoning=reasoning,
                metadata=dict(metadata),
                cancellation=cancellation,
            )

            started = perf_counter()
            if plan.dry_run:
                result = self._dry_run_adapter.execute(request)
            elif step.backend.value == "api":
                adapter = self._api_adapters.get(step.provider)
                if adapter is None:
                    result = self._missing_adapter_result(
                        step.model.id,
                        step.model.display_name,
                        adapter_name=f"{step.backend.value}.{step.provider}",
                        execution_mode="api",
                        message=f"No API adapter registered for provider '{step.provider}'.",
                    )
                else:
                    result = adapter.execute(request)
            else:
                if self._browser_adapter is None:
                    result = self._missing_adapter_result(
                        step.model.id,
                        step.model.display_name,
                        adapter_name=f"{step.backend.value}.{step.provider}",
                        execution_mode="browser",
                        message="Browser adapter is not connected yet.",
                    )
                else:
                    result = self._browser_adapter.execute(request)

            duration_ms = result.duration_ms
            if duration_ms is None:
                duration_ms = max(0, int((perf_counter() - started) * 1000))
                result = replace(result, duration_ms=duration_ms)

            results.append(result)
            if (
                not plan.dry_run
                and plan.cancel_on_quorum
                and self._successful_count(tuple(results)) >= plan.quorum
            ):
                cancellation.request_cancel()

        return self._aggregate(plan, tuple(results))

    def _aggregate(
        self,
        plan: ExecutionPlan,
        results: tuple[ExecutionResult, ...],
    ) -> ExecutionBatchResult:
        execution_mode = "dry-run" if plan.dry_run else self._resolve_execution_mode(results)
        successful = tuple(item for item in results if item.status == StepStatus.COMPLETED)
        failed = tuple(item for item in results if item.status == StepStatus.FAILED)
        cancelled_steps = [
            step.step_index
            for step, result in zip(plan.steps, results, strict=False)
            if result.status == StepStatus.CANCELLED
        ]
        winning_step = None
        if plan.merge_strategy == MergeStrategy.FIRST_SUCCESS or len(plan.steps) == 1:
            winning_step = next(
                (
                    (step, result)
                    for step, result in zip(plan.steps, results, strict=False)
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

    def _successful_count(self, results: tuple[ExecutionResult, ...]) -> int:
        return sum(1 for item in results if item.status == StepStatus.COMPLETED)

    def _resolve_execution_mode(self, results: tuple[ExecutionResult, ...]) -> str:
        execution_modes = sorted({item.execution_mode for item in results})
        return execution_modes[0] if len(execution_modes) == 1 else "mixed"

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
        execution_mode: str,
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

    def _cancelled_result(self, step) -> ExecutionResult:
        return ExecutionResult(
            adapter_name=f"{step.backend.value}.{step.provider}",
            model_id=step.model.id,
            model_display_name=step.model.display_name,
            execution_mode=step.backend.value,
            status=StepStatus.CANCELLED,
            details={"cancelled": True},
        )
