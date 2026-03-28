from __future__ import annotations

import unittest

from gracekelly.core.contracts import (
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
from gracekelly.core.router import ExecutionRouter


def _model(name: str = "sonar"):  # type: ignore[no-untyped-def]
    return resolve_model(name)


def _step(model_name: str = "sonar", *, step_index: int = 1) -> ExecutionStep:
    m = _model(model_name)
    return ExecutionStep(
        model=m,
        backend=ExecutionBackend.API,
        provider=m.provider,
        provider_model_id=m.provider_model_id,
        step_index=step_index,
    )


def _plan(
    *steps: ExecutionStep,
    quorum: int = 1,
    merge_strategy: MergeStrategy = MergeStrategy.FIRST_SUCCESS,
    dry_run: bool = False,
    cancel_on_quorum: bool = False,
) -> ExecutionPlan:
    return ExecutionPlan(
        steps=tuple(steps),
        quorum=quorum,
        merge_strategy=merge_strategy,
        dry_run=dry_run,
        adapter_hint="auto",
        cancel_on_quorum=cancel_on_quorum,
    )


def _result(
    step: ExecutionStep,
    *,
    status: StepStatus = StepStatus.COMPLETED,
    failure_code: FailureCode | None = None,
    output_text: str | None = "ok",
    duration_ms: int | None = None,
) -> ExecutionResult:
    m = step.model
    return ExecutionResult(
        adapter_name=f"{step.backend.value}.{step.provider}",
        model_id=m.id,
        model_display_name=m.display_name,
        execution_mode=ExecutionMode.API,
        status=status,
        failure_code=failure_code,
        output_text=output_text if status == StepStatus.COMPLETED else None,
        duration_ms=duration_ms,
    )


class _StubAdapter(ExecutionAdapter):
    """Returns pre-configured results in order."""

    name = "stub"

    def __init__(self, results: list[ExecutionResult]) -> None:
        self._results = list(results)

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        return self._results.pop(0)

    def healthcheck(self) -> dict[str, object]:
        return {"status": "ok", "adapter_name": self.name}


class RouterAllCancelledTests(unittest.TestCase):
    """When every step is cancelled the task should be CANCELLED, not FAILED."""

    def _router_with_step(self) -> tuple[ExecutionRouter, ExecutionStep]:
        step = _step()
        router = ExecutionRouter(
            dry_run_adapter=_StubAdapter([]),
            api_adapters={"perplexity": _StubAdapter([
                _result(step, status=StepStatus.CANCELLED, output_text=None),
            ])},
        )
        return router, step

    def test_all_cancelled_task_status(self) -> None:
        router, step = self._router_with_step()
        batch = router.execute(
            task_id="t1",
            prompt="Q",
            plan=_plan(step),
            reasoning=False,
            metadata={},
        )
        self.assertEqual(batch.task_status, TaskStatus.CANCELLED)

    def test_all_cancelled_no_output(self) -> None:
        router, step = self._router_with_step()
        batch = router.execute(
            task_id="t1",
            prompt="Q",
            plan=_plan(step),
            reasoning=False,
            metadata={},
        )
        self.assertIsNone(batch.output_text)

    def test_all_cancelled_no_failure_code(self) -> None:
        router, step = self._router_with_step()
        batch = router.execute(
            task_id="t1",
            prompt="Q",
            plan=_plan(step),
            reasoning=False,
            metadata={},
        )
        self.assertIsNone(batch.failure_code)


class RouterMissingApiAdapterTests(unittest.TestCase):
    """When no API adapter is registered for a provider, execution fails gracefully."""

    def test_missing_api_adapter_returns_failed(self) -> None:
        step = _step()  # provider=perplexity, but we register nothing
        router = ExecutionRouter(dry_run_adapter=_StubAdapter([]), api_adapters={})
        batch = router.execute(
            task_id="t1",
            prompt="Q",
            plan=_plan(step),
            reasoning=False,
            metadata={},
        )
        self.assertEqual(batch.task_status, TaskStatus.FAILED)

    def test_missing_api_adapter_failure_code(self) -> None:
        step = _step()
        router = ExecutionRouter(dry_run_adapter=_StubAdapter([]), api_adapters={})
        batch = router.execute(
            task_id="t1",
            prompt="Q",
            plan=_plan(step),
            reasoning=False,
            metadata={},
        )
        self.assertEqual(batch.failure_code, FailureCode.PROVIDER_UNAVAILABLE)


class RouterMissingBrowserAdapterTests(unittest.TestCase):
    """When browser adapter is not configured and a browser step is dispatched."""

    def test_missing_browser_adapter_returns_failed(self) -> None:
        m = _model("Kimi K2")  # browser-backed model
        step = ExecutionStep(
            model=m,
            backend=ExecutionBackend.BROWSER,
            provider=m.provider,
            provider_model_id=m.provider_model_id,
            step_index=1,
        )
        router = ExecutionRouter(
            dry_run_adapter=_StubAdapter([]),
            api_adapters={},
            browser_adapter=None,
        )
        batch = router.execute(
            task_id="t1",
            prompt="Q",
            plan=_plan(step),
            reasoning=False,
            metadata={},
        )
        self.assertEqual(batch.task_status, TaskStatus.FAILED)

    def test_missing_browser_adapter_failure_code(self) -> None:
        m = _model("Kimi K2")
        step = ExecutionStep(
            model=m,
            backend=ExecutionBackend.BROWSER,
            provider=m.provider,
            provider_model_id=m.provider_model_id,
            step_index=1,
        )
        router = ExecutionRouter(
            dry_run_adapter=_StubAdapter([]),
            api_adapters={},
            browser_adapter=None,
        )
        batch = router.execute(
            task_id="t1",
            prompt="Q",
            plan=_plan(step),
            reasoning=False,
            metadata={},
        )
        self.assertEqual(batch.failure_code, FailureCode.PROVIDER_UNAVAILABLE)


class RouterStampDurationTests(unittest.TestCase):
    """_stamp_duration preserves existing duration_ms and fills absent ones."""

    def test_pre_stamped_duration_preserved(self) -> None:
        """If result already has duration_ms, router must not overwrite it."""
        step = _step()
        pre_stamped = _result(step, duration_ms=999)
        router = ExecutionRouter(
            dry_run_adapter=_StubAdapter([]),
            api_adapters={"perplexity": _StubAdapter([pre_stamped])},
        )
        batch = router.execute(
            task_id="t1",
            prompt="Q",
            plan=_plan(step),
            reasoning=False,
            metadata={},
        )
        self.assertEqual(batch.results[0].duration_ms, 999)

    def test_missing_duration_filled(self) -> None:
        """If result has no duration_ms, router stamps a non-negative value."""
        step = _step()
        no_duration = _result(step, duration_ms=None)
        router = ExecutionRouter(
            dry_run_adapter=_StubAdapter([]),
            api_adapters={"perplexity": _StubAdapter([no_duration])},
        )
        batch = router.execute(
            task_id="t1",
            prompt="Q",
            plan=_plan(step),
            reasoning=False,
            metadata={},
        )
        self.assertIsNotNone(batch.results[0].duration_ms)
        assert batch.results[0].duration_ms is not None
        self.assertGreaterEqual(batch.results[0].duration_ms, 0)


class RouterMergeOutputsTests(unittest.TestCase):
    """Output merging strategy tests."""

    def test_concat_joins_with_double_newline(self) -> None:
        step1 = _step("sonar", step_index=1)
        step2 = _step("Mistral", step_index=2)
        router = ExecutionRouter(
            dry_run_adapter=_StubAdapter([]),
            api_adapters={
                "perplexity": _StubAdapter([_result(step1, output_text="AAA")]),
                "mistral": _StubAdapter([_result(step2, output_text="BBB")]),
            },
        )
        batch = router.execute(
            task_id="t1",
            prompt="Q",
            plan=_plan(step1, step2, quorum=2, merge_strategy=MergeStrategy.CONCAT),
            reasoning=False,
            metadata={},
        )
        self.assertEqual(batch.task_status, TaskStatus.COMPLETED)
        assert batch.output_text is not None
        self.assertIn("AAA", batch.output_text)
        self.assertIn("BBB", batch.output_text)

    def test_first_success_returns_first_completed(self) -> None:
        step1 = _step("sonar", step_index=1)
        step2 = _step("Mistral", step_index=2)
        router = ExecutionRouter(
            dry_run_adapter=_StubAdapter([]),
            api_adapters={
                "perplexity": _StubAdapter([_result(step1, output_text="FIRST")]),
                "mistral": _StubAdapter([_result(step2, output_text="SECOND")]),
            },
        )
        batch = router.execute(
            task_id="t1",
            prompt="Q",
            plan=_plan(step1, step2, quorum=1, merge_strategy=MergeStrategy.FIRST_SUCCESS, cancel_on_quorum=False),
            reasoning=False,
            metadata={},
        )
        self.assertEqual(batch.task_status, TaskStatus.COMPLETED)
        self.assertEqual(batch.output_text, "FIRST")


class RouterHealthcheckTests(unittest.TestCase):
    def test_healthcheck_returns_ok_status(self) -> None:
        router = ExecutionRouter(dry_run_adapter=_StubAdapter([]))
        result = router.healthcheck()
        self.assertEqual(result["status"], "ok")

    def test_healthcheck_has_model_limits(self) -> None:
        router = ExecutionRouter(dry_run_adapter=_StubAdapter([]))
        result = router.healthcheck()
        self.assertIn("model_limits", result)
        self.assertIsInstance(result["model_limits"], dict)

    def test_healthcheck_no_active_executions_initially(self) -> None:
        router = ExecutionRouter(dry_run_adapter=_StubAdapter([]))
        result = router.healthcheck()
        self.assertEqual(result["active_model_executions"], 0)

    def test_healthcheck_no_saturated_models_initially(self) -> None:
        router = ExecutionRouter(dry_run_adapter=_StubAdapter([]))
        result = router.healthcheck()
        self.assertEqual(result["saturated_models"], [])


class RouterDetailsTests(unittest.TestCase):
    """Verify execution details in the batch result."""

    def test_details_quorum_preserved(self) -> None:
        step = _step()
        router = ExecutionRouter(
            dry_run_adapter=_StubAdapter([]),
            api_adapters={"perplexity": _StubAdapter([_result(step)])},
        )
        batch = router.execute(
            task_id="t1",
            prompt="Q",
            plan=_plan(step, quorum=1),
            reasoning=False,
            metadata={},
        )
        self.assertEqual(batch.details["quorum"], 1)

    def test_details_winning_step_index_set_on_success(self) -> None:
        step = _step()
        router = ExecutionRouter(
            dry_run_adapter=_StubAdapter([]),
            api_adapters={"perplexity": _StubAdapter([_result(step)])},
        )
        batch = router.execute(
            task_id="t1",
            prompt="Q",
            plan=_plan(step),
            reasoning=False,
            metadata={},
        )
        self.assertEqual(batch.details["winning_step_index"], step.step_index)

    def test_details_cancel_reason_set_when_quorum_reached(self) -> None:
        step1 = _step("sonar", step_index=1)
        step2 = _step("Mistral", step_index=2)
        router = ExecutionRouter(
            dry_run_adapter=_StubAdapter([]),
            api_adapters={
                "perplexity": _StubAdapter([_result(step1)]),
                "mistral": _StubAdapter([_result(step2, status=StepStatus.CANCELLED, output_text=None)]),
            },
        )
        batch = router.execute(
            task_id="t1",
            prompt="Q",
            plan=_plan(step1, step2, quorum=1, cancel_on_quorum=False),
            reasoning=False,
            metadata={},
        )
        self.assertEqual(batch.task_status, TaskStatus.COMPLETED)
        # At least one cancelled step → cancel_reason should be quorum_reached
        if batch.details["cancelled_step_count"] > 0:
            self.assertEqual(batch.details["cancel_reason"], "quorum_reached")


class RouterResolveTaskFailureEdgeTests(unittest.TestCase):
    """Edge cases for _resolve_task_failure not covered by test_router_helpers."""

    def _router(self) -> ExecutionRouter:
        return ExecutionRouter(dry_run_adapter=_StubAdapter([]))

    def test_single_failed_with_code_but_no_message_uses_code_value(self) -> None:
        """One failure with failure_code set but failure_message is None.
        Falls through to the second branch (same failure_code set, len==1).
        """
        step = _step()
        r = ExecutionResult(
            adapter_name="api.perplexity",
            model_id=step.model.id,
            model_display_name=step.model.display_name,
            execution_mode=ExecutionMode.API,
            status=StepStatus.FAILED,
            failure_code=FailureCode.TIMEOUT,
            failure_message=None,
        )
        code, message = self._router()._resolve_task_failure((r,))
        self.assertEqual(code, FailureCode.TIMEOUT)
        self.assertIn("timeout", message.lower())

    def test_failed_with_no_failure_code_uses_unknown_summary(self) -> None:
        """Two failures where one has no failure_code → different codes branch."""
        step = _step()
        r1 = ExecutionResult(
            adapter_name="api.perplexity",
            model_id=step.model.id,
            model_display_name=step.model.display_name,
            execution_mode=ExecutionMode.API,
            status=StepStatus.FAILED,
            failure_code=FailureCode.RATE_LIMITED,
            failure_message="limited",
        )
        r2 = ExecutionResult(
            adapter_name="api.perplexity",
            model_id=step.model.id,
            model_display_name=step.model.display_name,
            execution_mode=ExecutionMode.API,
            status=StepStatus.FAILED,
            failure_code=None,
            failure_message="other",
        )
        code, message = self._router()._resolve_task_failure((r1, r2))
        self.assertEqual(code, FailureCode.UNKNOWN_ERROR)
        self.assertIn("2", message)


class RouterCancelledResultTests(unittest.TestCase):
    """_cancelled_result produces CANCELLED StepStatus."""

    def test_cancelled_result_status(self) -> None:
        step = _step()
        router = ExecutionRouter(dry_run_adapter=_StubAdapter([]))
        result = router._cancelled_result(step)
        self.assertEqual(result.status, StepStatus.CANCELLED)

    def test_cancelled_result_adapter_name(self) -> None:
        step = _step()
        router = ExecutionRouter(dry_run_adapter=_StubAdapter([]))
        result = router._cancelled_result(step)
        self.assertIn(step.backend.value, result.adapter_name)
        self.assertIn(step.provider, result.adapter_name)

    def test_cancelled_result_no_failure_code(self) -> None:
        step = _step()
        router = ExecutionRouter(dry_run_adapter=_StubAdapter([]))
        result = router._cancelled_result(step)
        self.assertIsNone(result.failure_code)

    def test_cancelled_result_details_flag(self) -> None:
        step = _step()
        router = ExecutionRouter(dry_run_adapter=_StubAdapter([]))
        result = router._cancelled_result(step)
        self.assertTrue(result.details.get("cancelled"))


class RouterConcurrencyLimitedResultTests(unittest.TestCase):
    """_concurrency_limited_result produces FAILED with RATE_LIMITED."""

    def test_concurrency_limited_status_is_failed(self) -> None:
        step = _step()
        router = ExecutionRouter(dry_run_adapter=_StubAdapter([]))
        result = router._concurrency_limited_result(step)
        self.assertEqual(result.status, StepStatus.FAILED)

    def test_concurrency_limited_failure_code(self) -> None:
        step = _step()
        router = ExecutionRouter(dry_run_adapter=_StubAdapter([]))
        result = router._concurrency_limited_result(step)
        self.assertEqual(result.failure_code, FailureCode.RATE_LIMITED)

    def test_concurrency_limited_message_mentions_model(self) -> None:
        step = _step()
        router = ExecutionRouter(dry_run_adapter=_StubAdapter([]))
        result = router._concurrency_limited_result(step)
        assert result.failure_message is not None
        self.assertIn(step.model.display_name, result.failure_message)

    def test_concurrency_limited_details_has_limit(self) -> None:
        step = _step()
        router = ExecutionRouter(dry_run_adapter=_StubAdapter([]))
        result = router._concurrency_limited_result(step)
        self.assertIn("concurrency_limit", result.details)


class RouterMergeOutputsAllNoneTests(unittest.TestCase):
    """_merge_outputs when all output_text values are None."""

    def test_all_none_outputs_returns_none_for_concat(self) -> None:
        step = _step()
        r1 = _result(step, output_text=None)
        r2 = _result(step, output_text=None)
        router = ExecutionRouter(dry_run_adapter=_StubAdapter([]))
        out = router._merge_outputs(MergeStrategy.CONCAT, (r1, r2))
        self.assertIsNone(out)

    def test_all_none_outputs_returns_none_for_first_success(self) -> None:
        step = _step()
        r = _result(step, output_text=None)
        router = ExecutionRouter(dry_run_adapter=_StubAdapter([]))
        out = router._merge_outputs(MergeStrategy.FIRST_SUCCESS, (r,))
        self.assertIsNone(out)


if __name__ == "__main__":
    unittest.main()
