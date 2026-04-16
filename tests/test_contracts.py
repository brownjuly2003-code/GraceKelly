from __future__ import annotations

import unittest
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from gracekelly.core.contracts import (
    AdapterHint,
    CancellationToken,
    ExecutionAdapter,
    ExecutionBackend,
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
from gracekelly.core.models import resolve_model
from gracekelly.schemas import OrchestrateResponse, TaskStepView
from gracekelly.storage.base import TaskRecord, TaskStepRecord
from gracekelly.storage.memory import InMemoryTaskRepository

pytestmark = pytest.mark.usefixtures("inject_shared_test_factories")

if TYPE_CHECKING:
    def _make_execution_step(*args: object, **kwargs: object) -> ExecutionStep: ...

    def _make_execution_plan(*args: object, **kwargs: object) -> ExecutionPlan: ...

    def _make_execution_request(*args: object, **kwargs: object) -> ExecutionRequest: ...


class FailureCodeTests(unittest.TestCase):
    def test_failure_taxonomy_is_stable(self) -> None:
        self.assertEqual(FailureCode.AUTH_FAILED.value, "auth_failed")
        self.assertEqual(FailureCode.MODEL_MISMATCH.value, "model_mismatch")
        self.assertEqual(FailureCode.PROVIDER_UNAVAILABLE.value, "provider_unavailable")
        self.assertEqual(FailureCode.TIMEOUT.value, "timeout")
        self.assertEqual(FailureCode.RATE_LIMITED.value, "rate_limited")
        self.assertEqual(FailureCode.STORAGE_FAILED.value, "storage_failed")
        self.assertEqual(FailureCode.UNKNOWN_ERROR.value, "unknown_error")

    def test_task_step_view_truncates_long_output(self) -> None:
        record = TaskStepRecord(
            task_id="task-1",
            step_index=1,
            model_id="kimi-k2-5",
            model_display_name="Kimi K2.5",
            backend="browser",
            provider="perplexity",
            status=StepStatus.COMPLETED,
            output_text="x" * 12,
        )

        view = TaskStepView.from_record(record, max_output_length=5)

        self.assertEqual(view.output_text, "xxxxx")
        self.assertTrue(view.output_truncated)

    def test_memory_repository_schema_report_is_non_applicable_but_ok(self) -> None:
        repository = InMemoryTaskRepository()

        report = repository.schema_report()

        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["backend"], "memory")
        self.assertEqual(report["schema_version"], "not_applicable")

    def test_orchestrate_response_prefers_completed_adapter_over_cancelled_steps(self) -> None:
        now = datetime.now(UTC)
        task = TaskRecord(
            task_id="task-1",
            status=TaskStatus.COMPLETED,
            accepted_at=now,
            completed_at=now,
            duration_ms=1,
            prompt="prompt",
            reasoning=False,
            execution_mode=ExecutionMode.MIXED,
            dry_run=False,
            model_count=2,
            quorum=1,
            merge_strategy=MergeStrategy.FIRST_SUCCESS,
            adapter_hint=AdapterHint.AUTO,
            cancel_on_quorum=True,
            output_text="winner",
        )
        steps = [
            TaskStepRecord(
                task_id="task-1",
                step_index=1,
                model_id="kimi-k2-5",
                model_display_name="Kimi K2.5",
                backend="browser",
                provider="perplexity",
                status=StepStatus.COMPLETED,
            ),
            TaskStepRecord(
                task_id="task-1",
                step_index=2,
                model_id="mistral-small",
                model_display_name="Mistral Small",
                backend="api",
                provider="mistral",
                status=StepStatus.CANCELLED,
            ),
        ]

        response = OrchestrateResponse.from_task(task, steps, [])

        self.assertEqual(response.adapter_name, "browser.perplexity")


class CancellationTokenTests(unittest.TestCase):
    def test_initial_state_not_cancelled(self) -> None:
        token = CancellationToken()
        self.assertFalse(token.is_cancelled)

    def test_request_cancel_sets_cancelled(self) -> None:
        token = CancellationToken()
        token.request_cancel()
        self.assertTrue(token.is_cancelled)

    def test_request_cancel_idempotent(self) -> None:
        token = CancellationToken()
        token.request_cancel()
        token.request_cancel()
        self.assertTrue(token.is_cancelled)


class ExecutionResultIsFailureTests(unittest.TestCase):
    def test_no_failure_code_is_not_failure(self) -> None:
        result = ExecutionResult(
            adapter_name="api.mistral",
            model_id="mistral-small",
            model_display_name="Mistral Small",
            execution_mode=ExecutionMode.API,
            status=StepStatus.COMPLETED,
        )
        self.assertFalse(result.is_failure)

    def test_with_failure_code_is_failure(self) -> None:
        result = ExecutionResult(
            adapter_name="api.mistral",
            model_id="mistral-small",
            model_display_name="Mistral Small",
            execution_mode=ExecutionMode.API,
            status=StepStatus.FAILED,
            failure_code=FailureCode.TIMEOUT,
        )
        self.assertTrue(result.is_failure)


class ExecutionRequestModelsTests(unittest.TestCase):
    def test_models_returns_all_model_specs(self) -> None:
        spec_a = resolve_model("mistral-small")
        spec_b = resolve_model("kimi-k2-5")
        step_a = _make_execution_step(
            model=spec_a,
            backend=ExecutionBackend.API,
            step_index=0,
        )
        step_b = _make_execution_step(
            model=spec_b,
            backend=ExecutionBackend.BROWSER,
            step_index=1,
        )
        plan = _make_execution_plan(
            steps=(step_a, step_b),
            quorum=1,
            merge_strategy=MergeStrategy.FIRST_SUCCESS,
            dry_run=False,
            adapter_hint=AdapterHint.AUTO,
            cancel_on_quorum=False,
        )
        req = _make_execution_request(
            task_id="t1",
            prompt="hello",
            plan=plan,
            step=step_a,
            reasoning=False,
        )
        self.assertEqual(req.models, (spec_a, spec_b))


class ExecutionAdapterHealthcheckTests(unittest.TestCase):
    def test_default_healthcheck_returns_ok(self) -> None:
        class _ConcreteAdapter(ExecutionAdapter):
            name = "test-adapter"

            def execute(self, request: ExecutionRequest) -> ExecutionResult:  # pragma: no cover
                raise NotImplementedError

        adapter = _ConcreteAdapter()
        result = adapter.healthcheck()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["adapter_name"], "test-adapter")


if __name__ == "__main__":
    unittest.main()
