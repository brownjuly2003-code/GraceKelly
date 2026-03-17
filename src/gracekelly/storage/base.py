from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from gracekelly.core.contracts import MergeStrategy


@dataclass(slots=True)
class TaskRecord:
    task_id: str
    status: str
    accepted_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
    prompt: str
    reasoning: bool
    execution_mode: str
    dry_run: bool
    model_count: int
    quorum: int
    merge_strategy: MergeStrategy
    adapter_hint: str
    cancel_on_quorum: bool
    failure_code: str | None = None
    failure_message: str | None = None
    output_text: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TaskStepRecord:
    task_id: str
    step_index: int
    model_id: str
    model_display_name: str
    backend: str
    provider: str
    status: str
    failure_code: str | None = None
    failure_message: str | None = None
    output_text: str | None = None
    duration_ms: int | None = None


@dataclass(slots=True)
class TaskEventRecord:
    event_id: str
    task_id: str
    sequence_no: int
    event_type: str
    created_at: datetime
    payload: dict[str, Any] = field(default_factory=dict)


class TaskRepository(ABC):
    backend_name = "unknown"

    @abstractmethod
    def save_task_with_steps(
        self,
        task: TaskRecord,
        steps: list[TaskStepRecord],
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(self, task_id: str) -> TaskRecord | None:
        raise NotImplementedError

    @abstractmethod
    def list_steps(self, task_id: str) -> list[TaskStepRecord]:
        raise NotImplementedError

    @abstractmethod
    def append_event(self, event: TaskEventRecord) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_events(self, task_id: str) -> list[TaskEventRecord]:
        raise NotImplementedError

    def healthcheck(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "backend": self.backend_name,
        }

    def schema_report(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "backend": self.backend_name,
            "schema_version": "not_applicable",
        }
