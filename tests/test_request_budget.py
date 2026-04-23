from __future__ import annotations

import os
import unittest
from dataclasses import replace
from unittest.mock import MagicMock, patch

from gracekelly.config import Settings
from gracekelly.config import settings as _config_settings
from gracekelly.core.budget import BudgetAcquireResult, RequestBudgetTracker
from gracekelly.core.contracts import (
    AdapterHint,
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
from gracekelly.core.models import ModelSpec
from gracekelly.core.router import ExecutionRouter


def _make_spec(
    model_id: str,
    *,
    adapter_kind: str,
    provider: str,
    provider_model_id: str | None = None,
    concurrency_limit: int | None = None,
    fallback_model_id: str | None = None,
) -> ModelSpec:
    return ModelSpec(
        id=model_id,
        display_name=model_id,
        aliases=(model_id,),
        adapter_kind=adapter_kind,
        provider=provider,
        provider_model_id=provider_model_id or model_id,
        timeout_seconds=60,
        expected_latency_class="slow",
        concurrency_limit=concurrency_limit if concurrency_limit is not None else (1 if adapter_kind == "browser" else 4),
        reasoning_capable=True,
        fallback_model_id=fallback_model_id,
    )


def _make_step(spec: ModelSpec, *, step_index: int = 0) -> ExecutionStep:
    return ExecutionStep(
        model=spec,
        backend=ExecutionBackend(spec.adapter_kind),
        provider=spec.provider,
        provider_model_id=spec.provider_model_id,
        step_index=step_index,
    )


def _make_plan(step: ExecutionStep) -> ExecutionPlan:
    return ExecutionPlan(
        steps=(step,),
        quorum=1,
        merge_strategy=MergeStrategy.FIRST_SUCCESS,
        dry_run=False,
        adapter_hint=AdapterHint.AUTO,
        cancel_on_quorum=False,
    )


def _result(
    step: ExecutionStep,
    *,
    status: StepStatus,
    failure_code: FailureCode | None = None,
    failure_message: str | None = None,
    output_text: str | None = None,
) -> ExecutionResult:
    return ExecutionResult(
        adapter_name=f"{step.backend.value}.{step.provider}",
        model_id=step.model.id,
        model_display_name=step.model.display_name,
        execution_mode=ExecutionMode(step.backend.value),
        status=status,
        failure_code=failure_code,
        failure_message=failure_message,
        output_text=output_text,
    )


class _FakeClock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class _FakeAdapter(ExecutionAdapter):
    name = "fake"

    def __init__(self, results: list[ExecutionResult]) -> None:
        self._results = list(results)
        self.calls: list[str] = []

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        self.calls.append(request.step.model.id)
        return self._results.pop(0)


class RequestBudgetTrackerTests(unittest.TestCase):
    def test_tracker_allows_all_when_limits_none(self) -> None:
        tracker = RequestBudgetTracker()

        results = [tracker.try_acquire(task_id="task-1") for _ in range(100)]

        self.assertTrue(all(result.acquired for result in results))
        self.assertEqual(
            tracker.snapshot(),
            {
                "per_task_limit": None,
                "per_hour_limit": None,
                "active_task_counts": {},
                "hourly_submits": 0,
            },
        )

    def test_tracker_enforces_per_task_limit(self) -> None:
        tracker = RequestBudgetTracker(per_task_limit=3)

        results = [tracker.try_acquire(task_id="task-1") for _ in range(4)]

        self.assertEqual([result.acquired for result in results], [True, True, True, False])
        self.assertEqual(results[-1].reason, "per_task")
        self.assertEqual(results[-1].usage, {"task_submits": 3, "hourly_submits": 3})

    def test_tracker_per_task_limit_is_per_task_not_global(self) -> None:
        tracker = RequestBudgetTracker(per_task_limit=2)

        results = [
            tracker.try_acquire(task_id="task-A"),
            tracker.try_acquire(task_id="task-A"),
            tracker.try_acquire(task_id="task-B"),
            tracker.try_acquire(task_id="task-B"),
        ]

        self.assertEqual([result.acquired for result in results], [True, True, True, True])
        self.assertEqual(
            tracker.snapshot()["active_task_counts"],
            {"task-A": 2, "task-B": 2},
        )

    def test_tracker_enforces_per_hour_limit(self) -> None:
        clock = _FakeClock()
        tracker = RequestBudgetTracker(per_hour_limit=5, clock=clock)

        results = [tracker.try_acquire(task_id=f"task-{idx}") for idx in range(6)]

        self.assertEqual([result.acquired for result in results], [True, True, True, True, True, False])
        self.assertEqual(results[-1].reason, "per_hour")
        self.assertEqual(results[-1].usage, {"task_submits": 0, "hourly_submits": 5})

    def test_tracker_hourly_window_expires(self) -> None:
        clock = _FakeClock()
        tracker = RequestBudgetTracker(per_hour_limit=2, clock=clock)

        self.assertTrue(tracker.try_acquire(task_id="task-1").acquired)
        self.assertTrue(tracker.try_acquire(task_id="task-2").acquired)
        clock.advance(3601.0)
        result = tracker.try_acquire(task_id="task-3")

        self.assertTrue(result.acquired)
        self.assertEqual(result.usage, {"task_submits": 1, "hourly_submits": 1})

    def test_tracker_both_limits_earliest_reason_wins(self) -> None:
        tracker = RequestBudgetTracker(per_task_limit=3, per_hour_limit=5)

        for _ in range(3):
            self.assertTrue(tracker.try_acquire(task_id="task-A").acquired)
        result = tracker.try_acquire(task_id="task-A")

        self.assertFalse(result.acquired)
        self.assertEqual(result.reason, "per_task")
        self.assertEqual(result.usage, {"task_submits": 3, "hourly_submits": 3})


class RequestBudgetConfigTests(unittest.TestCase):
    def test_budget_env_defaults_to_none(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings.from_env()

        self.assertIsNone(settings.max_browser_submits_per_task)
        self.assertIsNone(settings.max_browser_submits_per_hour)

    def test_budget_env_reads_positive_ints(self) -> None:
        with patch.dict(
            os.environ,
            {
                "GRACEKELLY_MAX_BROWSER_SUBMITS_PER_TASK": "3",
                "GRACEKELLY_MAX_BROWSER_SUBMITS_PER_HOUR": "15",
            },
            clear=True,
        ):
            settings = Settings.from_env()

        self.assertEqual(settings.max_browser_submits_per_task, 3)
        self.assertEqual(settings.max_browser_submits_per_hour, 15)

    def test_budget_env_non_int_falls_back_to_none_and_logs_warning(self) -> None:
        with patch.dict(os.environ, {"GRACEKELLY_MAX_BROWSER_SUBMITS_PER_TASK": "oops"}, clear=True):
            with self.assertLogs("gracekelly.config", level="WARNING") as captured:
                settings = Settings.from_env()

        self.assertIsNone(settings.max_browser_submits_per_task)
        self.assertEqual(len(captured.output), 1)
        self.assertIn("GRACEKELLY_MAX_BROWSER_SUBMITS_PER_TASK", captured.output[0])

    def test_budget_env_non_positive_falls_back_to_none_and_logs_warning(self) -> None:
        with patch.dict(
            os.environ,
            {
                "GRACEKELLY_MAX_BROWSER_SUBMITS_PER_TASK": "0",
                "GRACEKELLY_MAX_BROWSER_SUBMITS_PER_HOUR": "-1",
            },
            clear=True,
        ):
            with self.assertLogs("gracekelly.config", level="WARNING") as captured:
                settings = Settings.from_env()

        self.assertIsNone(settings.max_browser_submits_per_task)
        self.assertIsNone(settings.max_browser_submits_per_hour)
        self.assertEqual(len(captured.output), 2)


class RequestBudgetRouterTests(unittest.TestCase):
    def test_router_budget_exceeded_returns_rate_limited(self) -> None:
        primary = _make_spec(
            "claude-sonnet-4-6",
            adapter_kind="browser",
            provider="perplexity",
        )
        step = _make_step(primary)
        browser_adapter = MagicMock()
        budget_tracker = MagicMock()
        budget_tracker.try_acquire.return_value = BudgetAcquireResult(
            acquired=False,
            reason="per_task",
            usage={"task_submits": 3, "hourly_submits": 3},
        )
        budget_tracker.snapshot.return_value = {
            "per_task_limit": 3,
            "per_hour_limit": None,
            "active_task_counts": {"t1": 3},
            "hourly_submits": 3,
        }
        router = ExecutionRouter(
            dry_run_adapter=MagicMock(),
            browser_adapter=browser_adapter,
            budget_tracker=budget_tracker,
        )

        batch = router.execute(
            task_id="t1",
            prompt="Q",
            plan=_make_plan(step),
            reasoning=False,
            metadata={},
        )

        budget_tracker.try_acquire.assert_called_once_with(task_id="t1")
        browser_adapter.execute.assert_not_called()
        self.assertEqual(batch.task_status, TaskStatus.FAILED)
        self.assertEqual(batch.failure_code, FailureCode.RATE_LIMITED)
        self.assertEqual(batch.results[0].details["budget_exceeded_kind"], "per_task")
        self.assertEqual(batch.results[0].details["budget_usage"], {"task_submits": 3, "hourly_submits": 3})
        assert batch.failure_message is not None
        self.assertIn("Request budget exceeded (per_task)", batch.failure_message)

    def test_router_budget_not_applied_to_api_backend(self) -> None:
        spec = _make_spec("claude-sonnet-4-6-api", adapter_kind="api", provider="anthropic")
        step = _make_step(spec)
        api_adapter = MagicMock()
        api_adapter.execute.return_value = _result(step, status=StepStatus.COMPLETED, output_text="ok")
        budget_tracker = MagicMock()
        budget_tracker.snapshot.return_value = {
            "per_task_limit": 1,
            "per_hour_limit": 1,
            "active_task_counts": {},
            "hourly_submits": 0,
        }
        router = ExecutionRouter(
            dry_run_adapter=MagicMock(),
            api_adapters={"anthropic": api_adapter},
            budget_tracker=budget_tracker,
        )

        batch = router.execute(
            task_id="t1",
            prompt="Q",
            plan=_make_plan(step),
            reasoning=False,
            metadata={},
        )

        budget_tracker.try_acquire.assert_not_called()
        api_adapter.execute.assert_called_once()
        self.assertEqual(batch.task_status, TaskStatus.COMPLETED)

    def test_router_budget_rate_limited_does_not_trigger_fallback(self) -> None:
        primary = _make_spec(
            "claude-sonnet-4-6",
            adapter_kind="browser",
            provider="perplexity",
            fallback_model_id="claude-sonnet-4-6-api",
        )
        fallback = _make_spec(
            "claude-sonnet-4-6-api",
            adapter_kind="api",
            provider="anthropic",
        )
        step = _make_step(primary)
        browser_adapter = MagicMock()
        api_adapter = _FakeAdapter([
            _result(_make_step(fallback), status=StepStatus.COMPLETED, output_text="fallback output"),
        ])
        budget_tracker = MagicMock()
        budget_tracker.try_acquire.return_value = BudgetAcquireResult(
            acquired=False,
            reason="per_task",
            usage={"task_submits": 3, "hourly_submits": 3},
        )
        budget_tracker.snapshot.return_value = {
            "per_task_limit": 3,
            "per_hour_limit": None,
            "active_task_counts": {"t1": 3},
            "hourly_submits": 3,
        }

        with (
            patch("gracekelly.core.router.list_models", return_value=(primary, fallback)),
            patch(
                "gracekelly.core.router._default_settings",
                replace(_config_settings, enable_model_fallback=True),
            ),
        ):
            router = ExecutionRouter(
                dry_run_adapter=_FakeAdapter([]),
                api_adapters={"anthropic": api_adapter},
                browser_adapter=browser_adapter,
                budget_tracker=budget_tracker,
            )
            batch = router.execute(
                task_id="t1",
                prompt="Q",
                plan=_make_plan(step),
                reasoning=False,
                metadata={},
            )

        browser_adapter.execute.assert_not_called()
        self.assertEqual(api_adapter.calls, [])
        self.assertEqual(batch.task_status, TaskStatus.FAILED)
        self.assertEqual(batch.failure_code, FailureCode.RATE_LIMITED)
        self.assertFalse(batch.results[0].details.get("fallback_used", False))

    def test_router_healthcheck_includes_budget_snapshot(self) -> None:
        with patch(
            "gracekelly.core.router._default_settings",
            replace(
                _config_settings,
                max_browser_submits_per_task=2,
                max_browser_submits_per_hour=5,
            ),
        ):
            router = ExecutionRouter(dry_run_adapter=MagicMock())

        healthcheck = router.healthcheck()

        self.assertIn("budget", healthcheck)
        self.assertEqual(healthcheck["budget"]["per_task_limit"], 2)
        self.assertEqual(healthcheck["budget"]["per_hour_limit"], 5)
        self.assertEqual(healthcheck["budget"]["hourly_submits"], 0)


if __name__ == "__main__":
    unittest.main()
