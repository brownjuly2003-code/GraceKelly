from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from gracekelly.core.task_classifier import TaskType


@dataclass(frozen=True, slots=True)
class ExecutionRecord:
    model_id: str
    task_type: TaskType
    status: str
    duration_ms: int
    timestamp: float


class ExecutionHistory:
    def __init__(self) -> None:
        self._records: list[ExecutionRecord] = []
        self._lock = threading.Lock()

    def record(
        self,
        model_id: str,
        task_type: TaskType,
        status: str,
        duration_ms: int,
    ) -> None:
        rec = ExecutionRecord(model_id, task_type, status, duration_ms, time.time())
        with self._lock:
            self._records.append(rec)

    def list_recent(self, limit: int = 50) -> list[ExecutionRecord]:
        with self._lock:
            return list(reversed(self._records[-limit:]))

    def list_by_model(
        self, model_id: str, limit: int = 50
    ) -> list[ExecutionRecord]:
        with self._lock:
            filtered = [r for r in self._records if r.model_id == model_id]
            return list(reversed(filtered[-limit:]))

    def list_by_task_type(
        self, task_type: TaskType, limit: int = 50
    ) -> list[ExecutionRecord]:
        with self._lock:
            filtered = [r for r in self._records if r.task_type == task_type]
            return list(reversed(filtered[-limit:]))

    def count(self) -> int:
        with self._lock:
            return len(self._records)

    def success_rate(self, model_id: str | None = None) -> float:
        with self._lock:
            records = (
                self._records
                if model_id is None
                else [r for r in self._records if r.model_id == model_id]
            )
        if not records:
            return 0.0
        return sum(1 for r in records if r.status == "completed") / len(records)

    def avg_duration_ms(self, model_id: str | None = None) -> float:
        with self._lock:
            records = (
                self._records
                if model_id is None
                else [r for r in self._records if r.model_id == model_id]
            )
        if not records:
            return 0.0
        return sum(r.duration_ms for r in records) / len(records)

    def clear(self) -> None:
        with self._lock:
            self._records.clear()
