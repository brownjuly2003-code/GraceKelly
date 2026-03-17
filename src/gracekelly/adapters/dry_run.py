from __future__ import annotations

from gracekelly.core.contracts import ExecutionAdapter, ExecutionRequest, ExecutionResult, StepStatus


class DryRunExecutionAdapter(ExecutionAdapter):
    name = "dry-run"

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        return ExecutionResult(
            adapter_name=self.name,
            model_id=request.step.model.id,
            model_display_name=request.step.model.display_name,
            execution_mode="dry-run",
            status=StepStatus.COMPLETED,
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
