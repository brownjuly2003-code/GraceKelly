from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
from time import monotonic
from typing import Any

_HOUR_SECONDS = 3600.0


@dataclass(frozen=True, slots=True)
class BudgetAcquireResult:
    acquired: bool
    reason: str | None
    usage: dict[str, int]


class RequestBudgetTracker:
    def __init__(
        self,
        *,
        per_task_limit: int | None = None,
        per_hour_limit: int | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._per_task_limit = per_task_limit
        self._per_hour_limit = per_hour_limit
        self._clock = clock or monotonic
        self._lock = Lock()
        self._task_counts: dict[str, int] = {}
        self._hourly_submits: deque[float] = deque()

    def try_acquire(self, *, task_id: str) -> BudgetAcquireResult:
        if self._per_task_limit is None and self._per_hour_limit is None:
            return BudgetAcquireResult(
                acquired=True,
                reason=None,
                usage={"task_submits": 0, "hourly_submits": 0},
            )
        with self._lock:
            now = self._clock()
            self._evict_expired(now)
            task_submits = self._task_counts.get(task_id, 0)
            hourly_submits = len(self._hourly_submits)
            if self._per_task_limit is not None and task_submits >= self._per_task_limit:
                return BudgetAcquireResult(
                    acquired=False,
                    reason="per_task",
                    usage={
                        "task_submits": task_submits,
                        "hourly_submits": hourly_submits,
                    },
                )
            if self._per_hour_limit is not None and hourly_submits >= self._per_hour_limit:
                return BudgetAcquireResult(
                    acquired=False,
                    reason="per_hour",
                    usage={
                        "task_submits": task_submits,
                        "hourly_submits": hourly_submits,
                    },
                )
            task_submits += 1
            self._task_counts[task_id] = task_submits
            self._hourly_submits.append(now)
            return BudgetAcquireResult(
                acquired=True,
                reason=None,
                usage={
                    "task_submits": task_submits,
                    "hourly_submits": len(self._hourly_submits),
                },
            )

    def snapshot(self) -> dict[str, Any]:
        if self._per_task_limit is None and self._per_hour_limit is None:
            return {
                "per_task_limit": None,
                "per_hour_limit": None,
                "active_task_counts": {},
                "hourly_submits": 0,
            }
        with self._lock:
            self._evict_expired(self._clock())
            return {
                "per_task_limit": self._per_task_limit,
                "per_hour_limit": self._per_hour_limit,
                "active_task_counts": dict(self._task_counts),
                "hourly_submits": len(self._hourly_submits),
            }

    def _evict_expired(self, now: float) -> None:
        cutoff = now - _HOUR_SECONDS
        while self._hourly_submits and self._hourly_submits[0] < cutoff:
            self._hourly_submits.popleft()
