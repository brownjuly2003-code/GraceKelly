from __future__ import annotations

from datetime import UTC, datetime, timedelta
import unittest

from gracekelly.core.circuit_breaker import CircuitBreakerConfig, CircuitBreakingExecutionAdapter
from gracekelly.core.contracts import (
    ExecutionAdapter,
    ExecutionBackend,
    ExecutionPlan,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStep,
    FailureCode,
    MergeStrategy,
    StepStatus,
)
from gracekelly.core.models import resolve_model


class _SequencedAdapter(ExecutionAdapter):
    name = "browser.perplexity"

    def __init__(self, results: list[ExecutionResult]) -> None:
        self._results = list(results)
        self.call_count = 0

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        self.call_count += 1
        return self._results.pop(0)

    def healthcheck(self) -> dict[str, object]:
        return {
            "status": "ok",
            "adapter_name": self.name,
        }


class _Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class CircuitBreakingExecutionAdapterTests(unittest.TestCase):
    def build_request(self) -> ExecutionRequest:
        model = resolve_model("Kimi K2")
        step = ExecutionStep(
            model=model,
            backend=ExecutionBackend.BROWSER,
            provider=model.provider,
            provider_model_id=model.provider_model_id,
            step_index=1,
        )
        return ExecutionRequest(
            task_id="task-circuit-1",
            prompt="hello",
            plan=ExecutionPlan(
                steps=(step,),
                quorum=1,
                merge_strategy=MergeStrategy.FIRST_SUCCESS,
                dry_run=False,
                adapter_hint="auto",
                cancel_on_quorum=True,
            ),
            step=step,
            reasoning=False,
        )

    def build_failure_result(self, *, code: FailureCode, message: str) -> ExecutionResult:
        model = resolve_model("Kimi K2")
        return ExecutionResult(
            adapter_name="browser.perplexity",
            model_id=model.id,
            model_display_name=model.display_name,
            execution_mode="browser",
            status=StepStatus.FAILED,
            failure_code=code,
            failure_message=message,
        )

    def build_success_result(self) -> ExecutionResult:
        model = resolve_model("Kimi K2")
        return ExecutionResult(
            adapter_name="browser.perplexity",
            model_id=model.id,
            model_display_name=model.display_name,
            execution_mode="browser",
            status=StepStatus.COMPLETED,
            output_text="ok",
        )

    def test_breaker_opens_after_repeated_counted_failures_and_fails_fast(self) -> None:
        adapter = _SequencedAdapter(
            [
                self.build_failure_result(code=FailureCode.PROVIDER_UNAVAILABLE, message="offline"),
                self.build_failure_result(code=FailureCode.TIMEOUT, message="slow"),
                self.build_failure_result(code=FailureCode.UNKNOWN_ERROR, message="crash"),
            ]
        )
        clock = _Clock(datetime(2026, 3, 18, 15, 0, tzinfo=UTC))
        breaker = CircuitBreakingExecutionAdapter(
            adapter,
            config=CircuitBreakerConfig(enabled=True, failure_threshold=3, cooldown_seconds=60),
            now_factory=clock,
        )
        request = self.build_request()

        for _ in range(3):
            result = breaker.execute(request)
            self.assertEqual(result.status, StepStatus.FAILED)

        self.assertEqual(adapter.call_count, 3)

        blocked = breaker.execute(request)
        self.assertEqual(adapter.call_count, 3)
        self.assertEqual(blocked.failure_code, FailureCode.PROVIDER_UNAVAILABLE)
        self.assertTrue(blocked.details["circuit_breaker_open"])
        self.assertEqual(blocked.details["circuit_breaker"]["state"], "open")

        health = breaker.healthcheck()
        self.assertEqual(health["status"], "degraded")
        self.assertEqual(health["circuit_breaker"]["state"], "open")
        self.assertEqual(health["circuit_breaker"]["fail_fast_rejections"], 1)

    def test_breaker_re_allows_requests_after_cooldown_and_closes_on_success(self) -> None:
        adapter = _SequencedAdapter(
            [
                self.build_failure_result(code=FailureCode.PROVIDER_UNAVAILABLE, message="offline"),
                self.build_failure_result(code=FailureCode.PROVIDER_UNAVAILABLE, message="still offline"),
                self.build_success_result(),
            ]
        )
        clock = _Clock(datetime(2026, 3, 18, 15, 0, tzinfo=UTC))
        breaker = CircuitBreakingExecutionAdapter(
            adapter,
            config=CircuitBreakerConfig(enabled=True, failure_threshold=2, cooldown_seconds=60),
            now_factory=clock,
        )
        request = self.build_request()

        breaker.execute(request)
        breaker.execute(request)

        blocked = breaker.execute(request)
        self.assertEqual(blocked.failure_code, FailureCode.PROVIDER_UNAVAILABLE)
        self.assertEqual(adapter.call_count, 2)

        clock.now = clock.now + timedelta(seconds=61)
        recovered = breaker.execute(request)

        self.assertEqual(adapter.call_count, 3)
        self.assertEqual(recovered.status, StepStatus.COMPLETED)
        self.assertEqual(breaker.healthcheck()["circuit_breaker"]["state"], "closed")

    def test_breaker_ignores_request_specific_failures(self) -> None:
        adapter = _SequencedAdapter(
            [
                self.build_failure_result(code=FailureCode.AUTH_FAILED, message="login required"),
                self.build_failure_result(code=FailureCode.MODEL_MISMATCH, message="wrong label"),
                self.build_success_result(),
            ]
        )
        breaker = CircuitBreakingExecutionAdapter(
            adapter,
            config=CircuitBreakerConfig(enabled=True, failure_threshold=2, cooldown_seconds=60),
        )
        request = self.build_request()

        first = breaker.execute(request)
        second = breaker.execute(request)
        third = breaker.execute(request)

        self.assertEqual(first.failure_code, FailureCode.AUTH_FAILED)
        self.assertEqual(second.failure_code, FailureCode.MODEL_MISMATCH)
        self.assertEqual(third.status, StepStatus.COMPLETED)
        self.assertEqual(adapter.call_count, 3)
        self.assertEqual(breaker.healthcheck()["circuit_breaker"]["state"], "closed")


if __name__ == "__main__":
    unittest.main()
