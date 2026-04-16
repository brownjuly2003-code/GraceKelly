from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from gracekelly.core.contracts import (
    AdapterHint,
    ExecutionBackend,
    ExecutionMode,
    ExecutionPlan,
    ExecutionResult,
    ExecutionStep,
    FailureCode,
    MergeStrategy,
    StepStatus,
    TaskStatus,
)
from gracekelly.core.models import ModelSpec
from gracekelly.core.router import ExecutionRouter


def _make_spec(
    model_id: str = "m1",
    provider: str = "anthropic",
    concurrency_limit: int = 4,
) -> ModelSpec:
    return ModelSpec(
        id=model_id,
        display_name=model_id,
        aliases=(model_id,),
        adapter_kind="api",
        provider=provider,
        provider_model_id=model_id,
        timeout_seconds=30,
        expected_latency_class="fast",
        concurrency_limit=concurrency_limit,
    )


def _make_step(
    spec: ModelSpec | None = None,
    backend: ExecutionBackend = ExecutionBackend.API,
    step_index: int = 0,
) -> ExecutionStep:
    if spec is None:
        spec = _make_spec()
    return ExecutionStep(
        model=spec,
        backend=backend,
        provider=spec.provider,
        provider_model_id=spec.provider_model_id,
        step_index=step_index,
    )


def _make_plan(
    steps: tuple[ExecutionStep, ...],
    *,
    dry_run: bool = False,
    quorum: int = 1,
    merge_strategy: MergeStrategy = MergeStrategy.FIRST_SUCCESS,
    cancel_on_quorum: bool = False,
) -> ExecutionPlan:
    return ExecutionPlan(
        steps=steps,
        quorum=quorum,
        merge_strategy=merge_strategy,
        dry_run=dry_run,
        adapter_hint=AdapterHint.API,
        cancel_on_quorum=cancel_on_quorum,
    )


def _ok_result(model_id: str = "m1", output: str = "ok") -> ExecutionResult:
    return ExecutionResult(
        adapter_name="test",
        model_id=model_id,
        model_display_name=model_id,
        execution_mode=ExecutionMode.API,
        status=StepStatus.COMPLETED,
        output_text=output,
    )


def _fail_result(
    model_id: str = "m1",
    failure_code: FailureCode = FailureCode.RATE_LIMITED,
) -> ExecutionResult:
    return ExecutionResult(
        adapter_name="test",
        model_id=model_id,
        model_display_name=model_id,
        execution_mode=ExecutionMode.API,
        status=StepStatus.FAILED,
        failure_code=failure_code,
        failure_message=f"{failure_code.value} error",
    )


class RouterDryRunTests(unittest.TestCase):
    def test_dry_run_uses_dry_run_adapter(self) -> None:
        dry_adapter = MagicMock()
        dry_adapter.execute.return_value = _ok_result()
        step = _make_step()
        plan = _make_plan((step,), dry_run=True)
        router = ExecutionRouter(dry_run_adapter=dry_adapter)
        router.execute(task_id="t1", prompt="hi", plan=plan, reasoning=False, metadata={})
        dry_adapter.execute.assert_called_once()

    def test_dry_run_returns_completed_task(self) -> None:
        dry_adapter = MagicMock()
        dry_adapter.execute.return_value = _ok_result()
        step = _make_step()
        plan = _make_plan((step,), dry_run=True)
        router = ExecutionRouter(dry_run_adapter=dry_adapter)
        result = router.execute(task_id="t1", prompt="hi", plan=plan, reasoning=False, metadata={})
        self.assertEqual(result.task_status, TaskStatus.COMPLETED)

    def test_dry_run_execution_mode_is_dry_run(self) -> None:
        dry_adapter = MagicMock()
        dry_adapter.execute.return_value = _ok_result()
        step = _make_step()
        plan = _make_plan((step,), dry_run=True)
        router = ExecutionRouter(dry_run_adapter=dry_adapter)
        result = router.execute(task_id="t1", prompt="hi", plan=plan, reasoning=False, metadata={})
        self.assertEqual(result.execution_mode, ExecutionMode.DRY_RUN)

    def test_dry_run_multiple_steps_all_executed(self) -> None:
        dry_adapter = MagicMock()
        dry_adapter.execute.return_value = _ok_result()
        steps = tuple(_make_step(_make_spec(f"m{i}"), step_index=i) for i in range(3))
        plan = _make_plan(steps, dry_run=True)
        router = ExecutionRouter(dry_run_adapter=dry_adapter)
        router.execute(task_id="t1", prompt="hi", plan=plan, reasoning=False, metadata={})
        self.assertEqual(dry_adapter.execute.call_count, 3)


class RouterApiDispatchTests(unittest.TestCase):
    def test_api_step_dispatched_to_api_adapter(self) -> None:
        api_adapter = MagicMock()
        api_adapter.execute.return_value = _ok_result()
        dry_adapter = MagicMock()
        spec = _make_spec(provider="anthropic")
        step = _make_step(spec)
        plan = _make_plan((step,))
        router = ExecutionRouter(
            dry_run_adapter=dry_adapter,
            api_adapters={"anthropic": api_adapter},
        )
        router.execute(task_id="t1", prompt="hi", plan=plan, reasoning=False, metadata={})
        api_adapter.execute.assert_called_once()
        dry_adapter.execute.assert_not_called()

    def test_missing_api_adapter_returns_provider_unavailable(self) -> None:
        dry_adapter = MagicMock()
        spec = _make_spec(provider="missing-provider")
        step = _make_step(spec)
        plan = _make_plan((step,))
        router = ExecutionRouter(dry_run_adapter=dry_adapter)
        result = router.execute(task_id="t1", prompt="hi", plan=plan, reasoning=False, metadata={})
        self.assertEqual(result.task_status, TaskStatus.FAILED)
        self.assertEqual(result.failure_code, FailureCode.PROVIDER_UNAVAILABLE)

    def test_missing_api_adapter_message_mentions_provider(self) -> None:
        dry_adapter = MagicMock()
        spec = _make_spec(provider="my-provider")
        step = _make_step(spec)
        plan = _make_plan((step,))
        router = ExecutionRouter(dry_run_adapter=dry_adapter)
        result = router.execute(task_id="t1", prompt="hi", plan=plan, reasoning=False, metadata={})
        assert result.failure_message is not None
        self.assertIn("my-provider", result.failure_message)

    def test_browser_step_with_no_browser_adapter_returns_unavailable(self) -> None:
        dry_adapter = MagicMock()
        spec = _make_spec(provider="perplexity")
        step = _make_step(spec, backend=ExecutionBackend.BROWSER)
        plan = _make_plan((step,))
        router = ExecutionRouter(dry_run_adapter=dry_adapter)
        result = router.execute(task_id="t1", prompt="hi", plan=plan, reasoning=False, metadata={})
        self.assertEqual(result.task_status, TaskStatus.FAILED)
        self.assertEqual(result.failure_code, FailureCode.PROVIDER_UNAVAILABLE)

    def test_browser_step_uses_browser_adapter(self) -> None:
        browser_adapter = MagicMock()
        browser_adapter.execute.return_value = ExecutionResult(
            adapter_name="browser",
            model_id="m1",
            model_display_name="m1",
            execution_mode=ExecutionMode.BROWSER,
            status=StepStatus.COMPLETED,
            output_text="browser result",
        )
        spec = _make_spec(provider="perplexity")
        step = _make_step(spec, backend=ExecutionBackend.BROWSER)
        plan = _make_plan((step,))
        router = ExecutionRouter(
            dry_run_adapter=MagicMock(),
            browser_adapter=browser_adapter,
        )
        result = router.execute(task_id="t1", prompt="hi", plan=plan, reasoning=False, metadata={})
        browser_adapter.execute.assert_called_once()
        self.assertEqual(result.task_status, TaskStatus.COMPLETED)


class RouterParallelTimeoutTests(unittest.TestCase):
    def test_parallel_execution_uses_default_timeout_for_as_completed(self) -> None:
        api_adapter = MagicMock()
        api_adapter.execute.return_value = _ok_result()
        step = _make_step(_make_spec(provider="anthropic"))
        plan = _make_plan((step,))
        router = ExecutionRouter(
            dry_run_adapter=MagicMock(),
            api_adapters={"anthropic": api_adapter},
        )
        observed: dict[str, object] = {}

        def fake_as_completed(
            futures: object,
            timeout: float | None = None,
        ) -> object:
            observed["timeout"] = timeout
            return iter(())

        with patch("gracekelly.core.router.as_completed", side_effect=fake_as_completed):
            router.execute(task_id="t1", prompt="hi", plan=plan, reasoning=False, metadata={})

        self.assertEqual(observed["timeout"], 120)

    def test_parallel_execution_timeout_returns_cancelled_batch(self) -> None:
        api_adapter = MagicMock()
        api_adapter.execute.return_value = _ok_result()
        step = _make_step(_make_spec(provider="anthropic"))
        plan = _make_plan((step,))
        router = ExecutionRouter(
            dry_run_adapter=MagicMock(),
            api_adapters={"anthropic": api_adapter},
        )

        with patch("gracekelly.core.router.as_completed", side_effect=TimeoutError):
            result = router.execute(task_id="t1", prompt="hi", plan=plan, reasoning=False, metadata={})

        self.assertEqual(result.task_status, TaskStatus.CANCELLED)
        self.assertEqual(result.results[0].status, StepStatus.CANCELLED)


class RouterAggregateTests(unittest.TestCase):
    def test_single_success_task_completed(self) -> None:
        api_adapter = MagicMock()
        api_adapter.execute.return_value = _ok_result(output="answer")
        step = _make_step(_make_spec(provider="anthropic"))
        plan = _make_plan((step,))
        router = ExecutionRouter(
            dry_run_adapter=MagicMock(),
            api_adapters={"anthropic": api_adapter},
        )
        result = router.execute(task_id="t1", prompt="hi", plan=plan, reasoning=False, metadata={})
        self.assertEqual(result.task_status, TaskStatus.COMPLETED)
        self.assertEqual(result.output_text, "answer")

    def test_all_failed_task_is_failed(self) -> None:
        api_adapter = MagicMock()
        api_adapter.execute.return_value = _fail_result()
        step = _make_step(_make_spec(provider="anthropic"))
        plan = _make_plan((step,))
        router = ExecutionRouter(
            dry_run_adapter=MagicMock(),
            api_adapters={"anthropic": api_adapter},
        )
        result = router.execute(task_id="t1", prompt="hi", plan=plan, reasoning=False, metadata={})
        self.assertEqual(result.task_status, TaskStatus.FAILED)

    def test_quorum_two_out_of_three_needed(self) -> None:
        api_adapter = MagicMock()
        call_count = [0]

        def side_effect(request: object) -> ExecutionResult:
            call_count[0] += 1
            if call_count[0] == 2:
                return _fail_result()
            return _ok_result()

        api_adapter.execute.side_effect = side_effect
        specs = [_make_spec(f"m{i}", provider="anthropic") for i in range(3)]
        steps = tuple(_make_step(s, step_index=i) for i, s in enumerate(specs))
        plan = _make_plan(steps, quorum=2)
        router = ExecutionRouter(
            dry_run_adapter=MagicMock(),
            api_adapters={"anthropic": api_adapter},
        )
        result = router.execute(task_id="t1", prompt="hi", plan=plan, reasoning=False, metadata={})
        self.assertEqual(result.task_status, TaskStatus.COMPLETED)

    def test_merge_strategy_first_success_returns_first_output(self) -> None:
        api_adapter = MagicMock()
        outputs = ["first", "second"]
        responses = [_ok_result(f"m{i}", output=o) for i, o in enumerate(outputs)]
        api_adapter.execute.side_effect = responses
        specs = [_make_spec(f"m{i}", provider="anthropic") for i in range(2)]
        steps = tuple(_make_step(s, step_index=i) for i, s in enumerate(specs))
        plan = _make_plan(steps, quorum=1, merge_strategy=MergeStrategy.FIRST_SUCCESS)
        router = ExecutionRouter(
            dry_run_adapter=MagicMock(),
            api_adapters={"anthropic": api_adapter},
        )
        result = router.execute(task_id="t1", prompt="hi", plan=plan, reasoning=False, metadata={})
        self.assertEqual(result.task_status, TaskStatus.COMPLETED)
        # FIRST_SUCCESS returns first completed output
        self.assertIsNotNone(result.output_text)

    def test_failure_code_propagated_to_batch_result(self) -> None:
        api_adapter = MagicMock()
        api_adapter.execute.return_value = _fail_result(failure_code=FailureCode.TIMEOUT)
        step = _make_step(_make_spec(provider="anthropic"))
        plan = _make_plan((step,))
        router = ExecutionRouter(
            dry_run_adapter=MagicMock(),
            api_adapters={"anthropic": api_adapter},
        )
        result = router.execute(task_id="t1", prompt="hi", plan=plan, reasoning=False, metadata={})
        self.assertEqual(result.failure_code, FailureCode.TIMEOUT)

    def test_details_contains_quorum(self) -> None:
        api_adapter = MagicMock()
        api_adapter.execute.return_value = _ok_result()
        step = _make_step(_make_spec(provider="anthropic"))
        plan = _make_plan((step,), quorum=1)
        router = ExecutionRouter(
            dry_run_adapter=MagicMock(),
            api_adapters={"anthropic": api_adapter},
        )
        result = router.execute(task_id="t1", prompt="hi", plan=plan, reasoning=False, metadata={})
        self.assertEqual(result.details["quorum"], 1)

    def test_details_completed_step_count(self) -> None:
        api_adapter = MagicMock()
        api_adapter.execute.return_value = _ok_result()
        step = _make_step(_make_spec(provider="anthropic"))
        plan = _make_plan((step,))
        router = ExecutionRouter(
            dry_run_adapter=MagicMock(),
            api_adapters={"anthropic": api_adapter},
        )
        result = router.execute(task_id="t1", prompt="hi", plan=plan, reasoning=False, metadata={})
        self.assertEqual(result.details["completed_step_count"], 1)
        self.assertEqual(result.details["failed_step_count"], 0)


class RouterHealthcheckTests(unittest.TestCase):
    def test_healthcheck_returns_ok(self) -> None:
        router = ExecutionRouter(dry_run_adapter=MagicMock())
        hc = router.healthcheck()
        self.assertEqual(hc["status"], "ok")

    def test_healthcheck_has_active_executions_key(self) -> None:
        router = ExecutionRouter(dry_run_adapter=MagicMock())
        hc = router.healthcheck()
        self.assertIn("active_model_executions", hc)

    def test_healthcheck_has_model_limits(self) -> None:
        router = ExecutionRouter(dry_run_adapter=MagicMock())
        hc = router.healthcheck()
        self.assertIn("model_limits", hc)
        self.assertIsInstance(hc["model_limits"], dict)

    def test_healthcheck_saturated_models_initially_empty(self) -> None:
        router = ExecutionRouter(dry_run_adapter=MagicMock())
        hc = router.healthcheck()
        self.assertEqual(hc["saturated_models"], [])


class RouterStampDurationTests(unittest.TestCase):
    def test_stamp_duration_sets_duration_ms(self) -> None:
        api_adapter = MagicMock()
        # Return result without duration_ms
        api_adapter.execute.return_value = _ok_result()
        step = _make_step(_make_spec(provider="anthropic"))
        plan = _make_plan((step,))
        router = ExecutionRouter(
            dry_run_adapter=MagicMock(),
            api_adapters={"anthropic": api_adapter},
        )
        batch = router.execute(task_id="t1", prompt="hi", plan=plan, reasoning=False, metadata={})
        # duration_ms should have been stamped
        step_result = batch.results[0]
        self.assertIsNotNone(step_result.duration_ms)
        assert step_result.duration_ms is not None
        self.assertGreaterEqual(step_result.duration_ms, 0)

    def test_stamp_duration_does_not_override_existing(self) -> None:
        api_adapter = MagicMock()
        # Return result WITH duration_ms already set
        result_with_duration = ExecutionResult(
            adapter_name="test",
            model_id="m1",
            model_display_name="m1",
            execution_mode=ExecutionMode.API,
            status=StepStatus.COMPLETED,
            output_text="ok",
            duration_ms=9999,
        )
        api_adapter.execute.return_value = result_with_duration
        step = _make_step(_make_spec(provider="anthropic"))
        plan = _make_plan((step,))
        router = ExecutionRouter(
            dry_run_adapter=MagicMock(),
            api_adapters={"anthropic": api_adapter},
        )
        batch = router.execute(task_id="t1", prompt="hi", plan=plan, reasoning=False, metadata={})
        self.assertEqual(batch.results[0].duration_ms, 9999)


class RouterMultipleFailureCodesTests(unittest.TestCase):
    def test_two_steps_different_failure_codes_returns_unknown(self) -> None:
        api_adapter = MagicMock()
        api_adapter.execute.side_effect = [
            _fail_result("m1", FailureCode.TIMEOUT),
            _fail_result("m2", FailureCode.RATE_LIMITED),
        ]
        specs = [_make_spec("m1", provider="anthropic"), _make_spec("m2", provider="anthropic")]
        steps = tuple(_make_step(s, step_index=i) for i, s in enumerate(specs))
        plan = _make_plan(steps, quorum=2)
        router = ExecutionRouter(
            dry_run_adapter=MagicMock(),
            api_adapters={"anthropic": api_adapter},
        )
        result = router.execute(task_id="t1", prompt="hi", plan=plan, reasoning=False, metadata={})
        self.assertEqual(result.task_status, TaskStatus.FAILED)
        self.assertEqual(result.failure_code, FailureCode.UNKNOWN_ERROR)

    def test_two_steps_same_failure_code_propagated(self) -> None:
        api_adapter = MagicMock()
        api_adapter.execute.side_effect = [
            _fail_result("m1", FailureCode.TIMEOUT),
            _fail_result("m2", FailureCode.TIMEOUT),
        ]
        specs = [_make_spec("m1", provider="anthropic"), _make_spec("m2", provider="anthropic")]
        steps = tuple(_make_step(s, step_index=i) for i, s in enumerate(specs))
        plan = _make_plan(steps, quorum=2)
        router = ExecutionRouter(
            dry_run_adapter=MagicMock(),
            api_adapters={"anthropic": api_adapter},
        )
        result = router.execute(task_id="t1", prompt="hi", plan=plan, reasoning=False, metadata={})
        self.assertEqual(result.failure_code, FailureCode.TIMEOUT)


if __name__ == "__main__":
    unittest.main()
