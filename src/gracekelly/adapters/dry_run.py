from __future__ import annotations

from gracekelly.core.contracts import ExecutionAdapter, ExecutionMode, ExecutionRequest, ExecutionResult, StepStatus


class DryRunExecutionAdapter(ExecutionAdapter):
    name = "dry-run"

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        return ExecutionResult(
            adapter_name=self.name,
            model_id=request.step.model.id,
            model_display_name=request.step.model.display_name,
            execution_mode=ExecutionMode.DRY_RUN,
            status=StepStatus.COMPLETED,
            output_text=f"[dry-run] Simulated response for: {request.prompt[:100]}",
            duration_ms=0,
            details={
                "simulated": True,
                "requested_models": [model.display_name for model in request.models],
                "active_model": request.step.model.display_name,
                "reasoning": request.reasoning,
            },
        )

    def healthcheck(self) -> dict[str, object]:
        return {
            "status": "ok",
            "adapter_name": self.name,
            "simulated": True,
        }
