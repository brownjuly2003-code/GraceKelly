from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from gracekelly.core.circuit_breaker import (
    CircuitBreakerConfig,
    CircuitBreakingExecutionAdapter,
    _serialize_timestamp,
)
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
)
from gracekelly.core.models import resolve_model


def _model():  # type: ignore[no-untyped-def]
    return resolve_model("sonar")


def _step() -> ExecutionStep:
    m = _model()
    return ExecutionStep(
        model=m,
        backend=ExecutionBackend.API,
        provider=m.provider,
        provider_model_id=m.provider_model_id,
        step_index=0,
    )


def _plan(step: ExecutionStep) -> ExecutionPlan:
    return ExecutionPlan(
        steps=(step,),
        quorum=1,
        merge_strategy=MergeStrategy.FIRST_SUCCESS,
        dry_run=False,
        adapter_hint="auto",
        cancel_on_quorum=False,
    )


def _request() -> ExecutionRequest:
    step = _step()
    return ExecutionRequest(
        task_id="t1",
        prompt="Q",
        plan=_plan(step),
        step=step,
        reasoning=False,
    )


def _failure(code: FailureCode = FailureCode.PROVIDER_UNAVAILABLE) -> ExecutionResult:
    m = _model()
    return ExecutionResult(
        adapter_name="test",
        model_id=m.id,
        model_display_name=m.display_name,
        execution_mode=ExecutionMode.API,
        status=StepStatus.FAILED,
        failure_code=code,
        failure_message="fail",
    )


def _success() -> ExecutionResult:
    m = _model()
    return ExecutionResult(
        adapter_name="test",
        model_id=m.id,
        model_display_name=m.display_name,
        execution_mode=ExecutionMode.API,
        status=StepStatus.COMPLETED,
        output_text="ok",
    )


class _StubAdapter(ExecutionAdapter):
    name = "test.stub"

    def __init__(self, results: list[ExecutionResult]) -> None:
        self._results = list(results)
        self.call_count = 0

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        self.call_count += 1
        return self._results.pop(0)

    def healthcheck(self) -> dict[str, object]:
        return {"status": "ok", "adapter_name": self.name}


class _Clock:
    def __init__(self, t: datetime) -> None:
        self.t = t

    def __call__(self) -> datetime:
        return self.t


class SerializeTimestampTests(unittest.TestCase):
    def test_none_returns_none(self) -> None:
        self.assertIsNone(_serialize_timestamp(None))

    def test_utc_datetime_formats_with_z(self) -> None:
        dt = datetime(2026, 3, 18, 15, 0, 0, tzinfo=UTC)
        result = _serialize_timestamp(dt)
        assert result is not None
        self.assertTrue(result.endswith("Z"), f"expected 'Z' suffix, got {result!r}")

    def test_utc_datetime_no_plus_offset(self) -> None:
        dt = datetime(2026, 1, 1, tzinfo=UTC)
        result = _serialize_timestamp(dt)
        assert result is not None
        self.assertNotIn("+00:00", result)


class CircuitBreakerConfigTests(unittest.TestCase):
    def test_default_enabled(self) -> None:
        self.assertTrue(CircuitBreakerConfig().enabled)

    def test_default_failure_threshold(self) -> None:
        self.assertEqual(CircuitBreakerConfig().failure_threshold, 3)

    def test_default_cooldown_seconds(self) -> None:
        self.assertEqual(CircuitBreakerConfig().cooldown_seconds, 60)

    def test_is_frozen(self) -> None:
        config = CircuitBreakerConfig()
        with self.assertRaises((AttributeError, TypeError)):
            config.enabled = False  # type: ignore[misc]


class CircuitBreakerDisabledTests(unittest.TestCase):
    def test_disabled_bypasses_all_logic(self) -> None:
        """enabled=False must forward every call to the inner adapter unconditionally."""
        inner = _StubAdapter([_failure(), _failure(), _failure()])
        breaker = CircuitBreakingExecutionAdapter(
            inner,
            config=CircuitBreakerConfig(enabled=False, failure_threshold=1, cooldown_seconds=60),
        )
        req = _request()
        for _ in range(3):
            breaker.execute(req)
        self.assertEqual(inner.call_count, 3)

    def test_disabled_healthcheck_shows_disabled_state(self) -> None:
        inner = _StubAdapter([])
        breaker = CircuitBreakingExecutionAdapter(
            inner,
            config=CircuitBreakerConfig(enabled=False),
        )
        result = breaker.healthcheck()
        self.assertEqual(result["circuit_breaker"]["state"], "disabled")

    def test_disabled_healthcheck_does_not_degrade_ok_status(self) -> None:
        inner = _StubAdapter([])
        breaker = CircuitBreakingExecutionAdapter(
            inner,
            config=CircuitBreakerConfig(enabled=False),
        )
        result = breaker.healthcheck()
        self.assertEqual(result["status"], "ok")


class CircuitBreakerNameTests(unittest.TestCase):
    def test_name_proxied_from_inner_adapter(self) -> None:
        inner = _StubAdapter([])
        breaker = CircuitBreakingExecutionAdapter(inner)
        self.assertEqual(breaker.name, "test.stub")


class CircuitBreakerHalfOpenTests(unittest.TestCase):
    def test_probe_fails_in_half_open_reopens_circuit(self) -> None:
        """A failed probe after cooldown must immediately re-open the circuit."""
        clock = _Clock(datetime(2026, 3, 1, 12, 0, tzinfo=UTC))
        inner = _StubAdapter([
            _failure(),  # trip #1
            _failure(),  # trip #2 (probe fails → re-opens)
        ])
        breaker = CircuitBreakingExecutionAdapter(
            inner,
            config=CircuitBreakerConfig(enabled=True, failure_threshold=1, cooldown_seconds=30),
            now_factory=clock,
        )
        req = _request()

        # First call trips the circuit
        breaker.execute(req)
        self.assertEqual(breaker.healthcheck()["circuit_breaker"]["state"], "open")

        # Advance past cooldown → probe allowed
        clock.t = clock.t + timedelta(seconds=31)
        probe_result = breaker.execute(req)
        self.assertEqual(probe_result.status, StepStatus.FAILED)

        # Circuit should be open again (probe failed)
        snap = breaker.healthcheck()["circuit_breaker"]
        self.assertEqual(snap["state"], "open")

    def test_probe_success_closes_circuit(self) -> None:
        clock = _Clock(datetime(2026, 3, 1, 12, 0, tzinfo=UTC))
        inner = _StubAdapter([
            _failure(),  # trip
            _success(),  # probe succeeds
        ])
        breaker = CircuitBreakingExecutionAdapter(
            inner,
            config=CircuitBreakerConfig(enabled=True, failure_threshold=1, cooldown_seconds=30),
            now_factory=clock,
        )
        req = _request()

        breaker.execute(req)
        clock.t = clock.t + timedelta(seconds=31)
        breaker.execute(req)

        self.assertEqual(breaker.healthcheck()["circuit_breaker"]["state"], "closed")

    def test_open_circuit_before_cooldown_rejects_without_probe(self) -> None:
        """During cooldown, no second probe is allowed."""
        clock = _Clock(datetime(2026, 3, 1, 12, 0, tzinfo=UTC))
        inner = _StubAdapter([_failure()])
        breaker = CircuitBreakingExecutionAdapter(
            inner,
            config=CircuitBreakerConfig(enabled=True, failure_threshold=1, cooldown_seconds=60),
            now_factory=clock,
        )
        req = _request()

        breaker.execute(req)

        # Still within cooldown — must be rejected without forwarding
        clock.t = clock.t + timedelta(seconds=10)
        blocked = breaker.execute(req)
        self.assertEqual(inner.call_count, 1)
        self.assertEqual(blocked.failure_code, FailureCode.PROVIDER_UNAVAILABLE)
        self.assertTrue(blocked.details["circuit_breaker_open"])


class CircuitBreakerOpenCountTests(unittest.TestCase):
    def test_open_count_increments_each_trip(self) -> None:
        clock = _Clock(datetime(2026, 3, 1, 12, 0, tzinfo=UTC))
        inner = _StubAdapter([
            _failure(),  # trip 1
            _failure(),  # probe fails → trip 2
        ])
        breaker = CircuitBreakingExecutionAdapter(
            inner,
            config=CircuitBreakerConfig(enabled=True, failure_threshold=1, cooldown_seconds=10),
            now_factory=clock,
        )
        req = _request()

        breaker.execute(req)
        clock.t = clock.t + timedelta(seconds=11)
        breaker.execute(req)

        snap = breaker.healthcheck()["circuit_breaker"]
        self.assertEqual(snap["open_count"], 2)


class CircuitBreakerCustomCodesTests(unittest.TestCase):
    def test_custom_failure_codes_only_counted_when_matched(self) -> None:
        """Only RATE_LIMITED triggers the circuit when custom codes are provided."""
        inner = _StubAdapter([
            _failure(FailureCode.PROVIDER_UNAVAILABLE),  # not in custom set → ignored
            _failure(FailureCode.RATE_LIMITED),          # in custom set → trips
            _success(),
        ])
        breaker = CircuitBreakingExecutionAdapter(
            inner,
            config=CircuitBreakerConfig(enabled=True, failure_threshold=1, cooldown_seconds=60),
            counted_failure_codes=frozenset({FailureCode.RATE_LIMITED}),
        )
        req = _request()

        # First failure (PROVIDER_UNAVAILABLE) should NOT trip
        first = breaker.execute(req)
        self.assertEqual(first.failure_code, FailureCode.PROVIDER_UNAVAILABLE)
        self.assertEqual(breaker.healthcheck()["circuit_breaker"]["state"], "closed")

        # Second failure (RATE_LIMITED) trips the circuit
        breaker.execute(req)
        self.assertEqual(breaker.healthcheck()["circuit_breaker"]["state"], "open")

    def test_snapshot_lists_custom_failure_codes(self) -> None:
        inner = _StubAdapter([])
        breaker = CircuitBreakingExecutionAdapter(
            inner,
            config=CircuitBreakerConfig(enabled=True),
            counted_failure_codes=frozenset({FailureCode.RATE_LIMITED}),
        )
        snap = breaker.healthcheck()["circuit_breaker"]
        self.assertIn("rate_limited", snap["counted_failure_codes"])


class CircuitBreakerHealthcheckClosedTests(unittest.TestCase):
    def test_closed_circuit_does_not_degrade_adapter_ok_status(self) -> None:
        inner = _StubAdapter([])
        breaker = CircuitBreakingExecutionAdapter(inner)
        result = breaker.healthcheck()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["circuit_breaker"]["state"], "closed")


if __name__ == "__main__":
    unittest.main()
