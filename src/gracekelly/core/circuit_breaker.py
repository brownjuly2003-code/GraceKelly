from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any

from gracekelly.core.contracts import (
    ExecutionAdapter,
    ExecutionMode,
    ExecutionRequest,
    ExecutionResult,
    FailureCode,
    StepStatus,
)

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _serialize_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class CircuitBreakerConfig:
    enabled: bool = True
    failure_threshold: int = 3
    cooldown_seconds: int = 60


class CircuitBreakingExecutionAdapter(ExecutionAdapter):
    def __init__(
        self,
        adapter: ExecutionAdapter,
        *,
        config: CircuitBreakerConfig | None = None,
        now_factory: Callable[[], datetime] | None = None,
        counted_failure_codes: frozenset[FailureCode] | None = None,
    ) -> None:
        self._adapter = adapter
        self._config = config or CircuitBreakerConfig()
        self._now_factory = now_factory or _utcnow
        self._counted_failure_codes = counted_failure_codes or frozenset(
            {
                FailureCode.PROVIDER_UNAVAILABLE,
                FailureCode.TIMEOUT,
                FailureCode.UNKNOWN_ERROR,
            }
        )
        self._lock = Lock()
        self._consecutive_failures = 0
        self._state = "closed"
        self._opened_at: datetime | None = None
        self._probe_in_flight = False
        self._open_count = 0
        self._fail_fast_rejections = 0
        self._last_failure_code: FailureCode | None = None
        self._last_failure_message: str | None = None
        self._last_failure_at: datetime | None = None

    @property
    def name(self) -> str:
        return getattr(self._adapter, "name", "unknown")

    @property
    def automation(self) -> Any:
        return getattr(self._adapter, "automation", None)

    @automation.setter
    def automation(self, value: Any) -> None:
        if hasattr(self._adapter, "automation"):
            self._adapter.automation = value

    @property
    def session_manager(self) -> Any:
        return getattr(self._adapter, "session_manager", None)

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        if not self._config.enabled:
            return self._adapter.execute(request)

        fail_fast = self._before_execute()
        if fail_fast is not None:
            return self._open_circuit_result(request, fail_fast)

        result = self._adapter.execute(request)
        self._after_execute(result)
        return result

    def healthcheck(self) -> dict[str, Any]:
        raw = dict(self._adapter.healthcheck())
        base_status = raw.get("status", "unknown")
        breaker = self._snapshot(base_status=base_status)
        status = base_status
        if self._config.enabled and breaker["state"] in {"open", "half-open"} and status != "failed":
            status = "degraded"
        raw["status"] = status
        raw["circuit_breaker"] = breaker
        return raw

    async def close(self) -> None:
        close_method = getattr(self._adapter, "close", None)
        if not callable(close_method):
            return
        result = close_method()
        if inspect.isawaitable(result):
            await result

    def _before_execute(self) -> dict[str, object] | None:
        now = self._now_factory()
        with self._lock:
            if self._state == "closed":
                return None

            reopen_at = self._reopen_at()
            if reopen_at is not None and now >= reopen_at and not self._probe_in_flight:
                self._state = "half-open"
                self._probe_in_flight = True
                logger.info(
                    "Circuit breaker entering half-open for adapter '%s', allowing probe request",
                    self.name,
                )
                return None

            self._fail_fast_rejections += 1
            logger.debug(
                "Circuit breaker rejecting request for adapter '%s' (state=%s, rejections=%d)",
                self.name,
                self._state,
                self._fail_fast_rejections,
            )
            return {
                "state": self._state,
                "opened_at": _serialize_timestamp(self._opened_at),
                "reopen_at": _serialize_timestamp(reopen_at),
                "consecutive_failures": self._consecutive_failures,
                "failure_threshold": self._config.failure_threshold,
                "cooldown_seconds": self._config.cooldown_seconds,
                "last_failure_code": self._last_failure_code.value if self._last_failure_code else None,
                "last_failure_message": self._last_failure_message,
                "last_failure_at": _serialize_timestamp(self._last_failure_at),
            }

    def _after_execute(self, result: ExecutionResult) -> None:
        with self._lock:
            was_half_open = self._state == "half-open"
            self._probe_in_flight = False

            if result.status == StepStatus.COMPLETED:
                self._close_circuit()
                return

            if result.status == StepStatus.FAILED and result.failure_code in self._counted_failure_codes:
                now = self._now_factory()
                self._last_failure_code = result.failure_code
                self._last_failure_message = result.failure_message
                self._last_failure_at = now

                if was_half_open:
                    self._trip(now)
                    return

                self._consecutive_failures += 1
                if self._consecutive_failures >= self._config.failure_threshold:
                    self._trip(now)
                else:
                    self._state = "closed"
                return

            self._close_circuit()

    def _trip(self, opened_at: datetime) -> None:
        self._state = "open"
        self._opened_at = opened_at
        self._open_count += 1
        self._consecutive_failures = max(self._consecutive_failures, self._config.failure_threshold)
        logger.warning(
            "Circuit breaker tripped open for adapter '%s' after %d consecutive failures "
            "(last_code=%s, open_count=%d)",
            self.name,
            self._consecutive_failures,
            self._last_failure_code.value if self._last_failure_code else "unknown",
            self._open_count,
        )

    def _close_circuit(self) -> None:
        was_open = self._state != "closed"
        self._state = "closed"
        self._opened_at = None
        self._probe_in_flight = False
        self._consecutive_failures = 0
        if was_open:
            logger.info("Circuit breaker closed for adapter '%s'", self.name)

    def _reopen_at(self) -> datetime | None:
        if self._opened_at is None:
            return None
        return self._opened_at + timedelta(seconds=self._config.cooldown_seconds)

    def _snapshot(self, *, base_status: str) -> dict[str, Any]:
        with self._lock:
            return {
                "enabled": self._config.enabled,
                "state": "disabled" if not self._config.enabled else self._state,
                "adapter_status": base_status,
                "failure_threshold": self._config.failure_threshold,
                "cooldown_seconds": self._config.cooldown_seconds,
                "counted_failure_codes": sorted(code.value for code in self._counted_failure_codes),
                "consecutive_failures": self._consecutive_failures,
                "opened_at": _serialize_timestamp(self._opened_at),
                "reopen_at": _serialize_timestamp(self._reopen_at()),
                "open_count": self._open_count,
                "fail_fast_rejections": self._fail_fast_rejections,
                "last_failure_code": self._last_failure_code.value if self._last_failure_code else None,
                "last_failure_message": self._last_failure_message,
                "last_failure_at": _serialize_timestamp(self._last_failure_at),
            }

    def _open_circuit_result(
        self,
        request: ExecutionRequest,
        snapshot: dict[str, object],
    ) -> ExecutionResult:
        step = request.step
        reopen_at = snapshot.get("reopen_at")
        message = (
            f"Adapter '{self.name}' circuit breaker is open after "
            f"{self._config.failure_threshold} consecutive failures."
        )
        if reopen_at:
            message = f"{message} Retry after {reopen_at}."
        return ExecutionResult(
            adapter_name=self.name,
            model_id=step.model.id,
            model_display_name=step.model.display_name,
            execution_mode=ExecutionMode(step.backend.value),
            status=StepStatus.FAILED,
            failure_code=FailureCode.PROVIDER_UNAVAILABLE,
            failure_message=message,
            details={
                "provider": step.provider,
                "circuit_breaker_open": True,
                "circuit_breaker": snapshot,
            },
        )
