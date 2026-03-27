from __future__ import annotations

import unittest
from time import perf_counter

from gracekelly.adapters.dry_run import DryRunExecutionAdapter
from gracekelly.core.contracts import (
    ExecutionMode,
    ExecutionResult,
    FailureCode,
    MergeStrategy,
    StepStatus,
)
from gracekelly.core.models import ModelSpec
from gracekelly.core.router import ExecutionRouter


def _model(model_id: str = "sonar") -> ModelSpec:
    from gracekelly.core.models import resolve_model
    return resolve_model(model_id)


def _result(
    *,
    status: StepStatus = StepStatus.COMPLETED,
    execution_mode: ExecutionMode = ExecutionMode.API,
    output_text: str | None = "answer",
    failure_code: FailureCode | None = None,
    failure_message: str | None = None,
    model_id: str = "sonar",
) -> ExecutionResult:
    return ExecutionResult(
        adapter_name="test",
        model_id=model_id,
        model_display_name=model_id,
        execution_mode=execution_mode,
        status=status,
        output_text=output_text,
        failure_code=failure_code,
        failure_message=failure_message,
    )


def _router() -> ExecutionRouter:
    return ExecutionRouter(dry_run_adapter=DryRunExecutionAdapter())


class StampDurationTests(unittest.TestCase):
    def test_stamps_duration_when_not_set(self) -> None:
        result = _result()
        started = perf_counter() - 0.1  # 100ms ago
        stamped = ExecutionRouter._stamp_duration(result, started)
        assert stamped.duration_ms is not None
        self.assertGreaterEqual(stamped.duration_ms, 0)

    def test_preserves_existing_duration(self) -> None:
        result = ExecutionResult(
            adapter_name="test",
            model_id="sonar",
            model_display_name="sonar",
            execution_mode=ExecutionMode.API,
            status=StepStatus.COMPLETED,
            duration_ms=999,
        )
        stamped = ExecutionRouter._stamp_duration(result, perf_counter())
        self.assertEqual(stamped.duration_ms, 999)

    def test_returns_new_object(self) -> None:
        result = _result()
        stamped = ExecutionRouter._stamp_duration(result, perf_counter() - 0.01)
        self.assertIsNot(result, stamped)


class SuccessfulCountTests(unittest.TestCase):
    def setUp(self) -> None:
        self.router = _router()

    def test_all_completed(self) -> None:
        results = (
            _result(status=StepStatus.COMPLETED),
            _result(status=StepStatus.COMPLETED),
        )
        self.assertEqual(self.router._successful_count(results), 2)

    def test_none_completed(self) -> None:
        results = (
            _result(status=StepStatus.FAILED),
            _result(status=StepStatus.CANCELLED),
        )
        self.assertEqual(self.router._successful_count(results), 0)

    def test_mixed(self) -> None:
        results = (
            _result(status=StepStatus.COMPLETED),
            _result(status=StepStatus.FAILED),
            _result(status=StepStatus.COMPLETED),
        )
        self.assertEqual(self.router._successful_count(results), 2)

    def test_empty(self) -> None:
        self.assertEqual(self.router._successful_count(()), 0)


class ResolveExecutionModeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.router = _router()

    def test_single_api_mode(self) -> None:
        results = (_result(execution_mode=ExecutionMode.API),)
        self.assertEqual(self.router._resolve_execution_mode(results), ExecutionMode.API)

    def test_single_browser_mode(self) -> None:
        results = (_result(execution_mode=ExecutionMode.BROWSER),)
        self.assertEqual(self.router._resolve_execution_mode(results), ExecutionMode.BROWSER)

    def test_mixed_modes_returns_mixed(self) -> None:
        results = (
            _result(execution_mode=ExecutionMode.API),
            _result(execution_mode=ExecutionMode.BROWSER),
        )
        self.assertEqual(self.router._resolve_execution_mode(results), ExecutionMode.MIXED)

    def test_all_same_mode_not_mixed(self) -> None:
        results = (
            _result(execution_mode=ExecutionMode.API),
            _result(execution_mode=ExecutionMode.API),
        )
        self.assertNotEqual(self.router._resolve_execution_mode(results), ExecutionMode.MIXED)


class MergeOutputsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.router = _router()

    def test_first_success_returns_first_output(self) -> None:
        results = (
            _result(output_text="first"),
            _result(output_text="second"),
        )
        output = self.router._merge_outputs(MergeStrategy.FIRST_SUCCESS, results)
        self.assertEqual(output, "first")

    def test_concat_joins_all_outputs(self) -> None:
        results = (
            _result(output_text="part1"),
            _result(output_text="part2"),
        )
        output = self.router._merge_outputs(MergeStrategy.CONCAT, results)
        assert output is not None
        self.assertIn("part1", output)
        self.assertIn("part2", output)

    def test_no_outputs_returns_none(self) -> None:
        results = (_result(output_text=None),)
        self.assertIsNone(self.router._merge_outputs(MergeStrategy.FIRST_SUCCESS, results))

    def test_empty_results_returns_none(self) -> None:
        self.assertIsNone(self.router._merge_outputs(MergeStrategy.FIRST_SUCCESS, ()))

    def test_skips_none_outputs_in_concat(self) -> None:
        results = (
            _result(output_text=None),
            _result(output_text="valid"),
        )
        output = self.router._merge_outputs(MergeStrategy.CONCAT, results)
        self.assertEqual(output, "valid")


class ResolveTaskFailureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.router = _router()

    def test_single_failure_preserves_code_and_message(self) -> None:
        failed = (
            _result(
                status=StepStatus.FAILED,
                failure_code=FailureCode.TIMEOUT,
                failure_message="timed out",
            ),
        )
        code, message = self.router._resolve_task_failure(failed)
        self.assertEqual(code, FailureCode.TIMEOUT)
        self.assertEqual(message, "timed out")

    def test_multiple_same_code_aggregates(self) -> None:
        failed = (
            _result(status=StepStatus.FAILED, failure_code=FailureCode.RATE_LIMITED, failure_message="limited"),
            _result(status=StepStatus.FAILED, failure_code=FailureCode.RATE_LIMITED, failure_message="limited"),
        )
        code, message = self.router._resolve_task_failure(failed)
        self.assertEqual(code, FailureCode.RATE_LIMITED)
        self.assertIn("2", message)

    def test_multiple_different_codes_returns_unknown(self) -> None:
        failed = (
            _result(status=StepStatus.FAILED, failure_code=FailureCode.TIMEOUT, failure_message="timeout"),
            _result(status=StepStatus.FAILED, failure_code=FailureCode.RATE_LIMITED, failure_message="limited"),
        )
        code, message = self.router._resolve_task_failure(failed)
        self.assertEqual(code, FailureCode.UNKNOWN_ERROR)
        self.assertIn("2", message)


if __name__ == "__main__":
    unittest.main()
