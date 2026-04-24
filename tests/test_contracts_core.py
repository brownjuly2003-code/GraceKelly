from __future__ import annotations

import unittest

from gracekelly.core.contracts import (
    AdapterHint,
    CancellationToken,
    ExecutionBackend,
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
from gracekelly.core.models import resolve_model


def _model(model_id: str = "sonar"):  # type: ignore[no-untyped-def]
    return resolve_model(model_id)


def _step(model_id: str = "sonar", step_index: int = 0) -> ExecutionStep:
    m = _model(model_id)
    return ExecutionStep(
        model=m,
        backend=ExecutionBackend.API,
        provider=m.provider,
        provider_model_id=m.provider_model_id,
        step_index=step_index,
    )


def _plan(*model_ids: str) -> ExecutionPlan:
    steps = tuple(_step(mid, i) for i, mid in enumerate(model_ids))
    return ExecutionPlan(
        steps=steps,
        quorum=1,
        merge_strategy=MergeStrategy.FIRST_SUCCESS,
        dry_run=False,
        adapter_hint=AdapterHint.AUTO,
        cancel_on_quorum=False,
    )


def _result(
    *,
    status: StepStatus = StepStatus.COMPLETED,
    failure_code: FailureCode | None = None,
) -> ExecutionResult:
    return ExecutionResult(
        adapter_name="test",
        model_id="sonar",
        model_display_name="Sonar",
        execution_mode=ExecutionMode.API,
        status=status,
        failure_code=failure_code,
    )


class CancellationTokenTests(unittest.TestCase):
    def test_default_not_cancelled(self) -> None:
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

    def test_is_cancelled_is_property(self) -> None:
        token = CancellationToken()
        self.assertIsInstance(type(token).is_cancelled, property)


class ExecutionResultIsFailureTests(unittest.TestCase):
    def test_no_failure_code_is_not_failure(self) -> None:
        result = _result(failure_code=None)
        self.assertFalse(result.is_failure)

    def test_with_failure_code_is_failure(self) -> None:
        result = _result(failure_code=FailureCode.TIMEOUT)
        self.assertTrue(result.is_failure)

    def test_completed_status_with_failure_code_is_still_failure(self) -> None:
        result = _result(status=StepStatus.COMPLETED, failure_code=FailureCode.UNKNOWN_ERROR)
        self.assertTrue(result.is_failure)

    def test_failed_status_without_code_is_not_failure(self) -> None:
        result = _result(status=StepStatus.FAILED, failure_code=None)
        self.assertFalse(result.is_failure)


class ExecutionRequestModelsPropertyTests(unittest.TestCase):
    def test_models_returns_tuple_of_model_specs(self) -> None:
        plan = _plan("sonar", "gpt-5-4-api")
        request = ExecutionRequest(
            task_id="t1",
            prompt="Q",
            plan=plan,
            step=plan.steps[0],
            reasoning=False,
        )
        models = request.models
        self.assertIsInstance(models, tuple)
        self.assertEqual(len(models), 2)

    def test_models_order_matches_steps(self) -> None:
        plan = _plan("sonar", "gpt-5-4-api")
        request = ExecutionRequest(
            task_id="t1",
            prompt="Q",
            plan=plan,
            step=plan.steps[0],
            reasoning=False,
        )
        ids = [m.id for m in request.models]
        self.assertEqual(ids[0], "sonar")
        self.assertEqual(ids[1], "gpt-5-4-api")

    def test_single_model_plan(self) -> None:
        plan = _plan("sonar")
        request = ExecutionRequest(
            task_id="t1",
            prompt="Q",
            plan=plan,
            step=plan.steps[0],
            reasoning=False,
        )
        self.assertEqual(len(request.models), 1)


class ExecutionBatchResultTests(unittest.TestCase):
    def test_defaults_to_no_failure(self) -> None:
        batch = ExecutionBatchResult(
            execution_mode=ExecutionMode.API,
            task_status=TaskStatus.COMPLETED,
            results=(_result(),),
        )
        self.assertIsNone(batch.failure_code)
        self.assertIsNone(batch.output_text)

    def test_is_frozen(self) -> None:
        batch = ExecutionBatchResult(
            execution_mode=ExecutionMode.DRY_RUN,
            task_status=TaskStatus.COMPLETED,
            results=(),
        )
        with self.assertRaises((AttributeError, TypeError)):
            batch.task_status = TaskStatus.FAILED  # type: ignore[misc]

    def test_details_defaults_to_empty_dict(self) -> None:
        batch = ExecutionBatchResult(
            execution_mode=ExecutionMode.API,
            task_status=TaskStatus.COMPLETED,
            results=(),
        )
        self.assertEqual(batch.details, {})


class FailureCodeTest(unittest.TestCase):
    def test_all_codes_are_strings(self) -> None:
        for code in FailureCode:
            self.assertIsInstance(str(code), str)

    def test_unknown_error_exists(self) -> None:
        self.assertIn(FailureCode.UNKNOWN_ERROR, list(FailureCode))

    def test_timeout_exists(self) -> None:
        self.assertIn(FailureCode.TIMEOUT, list(FailureCode))


if __name__ == "__main__":
    unittest.main()
