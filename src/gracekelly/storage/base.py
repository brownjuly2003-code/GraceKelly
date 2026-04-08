from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from gracekelly.core.contracts import (
    AdapterHint,
    EventType,
    ExecutionMode,
    FailureCode,
    MergeStrategy,
    StepStatus,
    TaskStatus,
)


@dataclass(slots=True)
class TaskRecord:
    task_id: str
    status: TaskStatus
    accepted_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
    prompt: str
    reasoning: bool
    execution_mode: ExecutionMode
    dry_run: bool
    model_count: int
    quorum: int
    merge_strategy: MergeStrategy
    adapter_hint: AdapterHint
    cancel_on_quorum: bool
    failure_code: FailureCode | None = None
    failure_message: str | None = None
    output_text: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    retry_of_task_id: str | None = None


@dataclass(slots=True)
class TaskStepRecord:
    task_id: str
    step_index: int
    model_id: str
    model_display_name: str
    backend: str
    provider: str
    status: StepStatus
    failure_code: FailureCode | None = None
    failure_message: str | None = None
    output_text: str | None = None
    duration_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(slots=True)
class TaskEventRecord:
    event_id: str
    task_id: str
    sequence_no: int
    event_type: EventType
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
    def list_recent(
        self,
        limit: int,
        *,
        status: TaskStatus | None = None,
        execution_mode: ExecutionMode | None = None,
        dry_run: bool | None = None,
        failure_code: FailureCode | None = None,
        before: datetime | None = None,
    ) -> list[TaskRecord]:
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

    def list_steps_batch(self, task_ids: list[str]) -> dict[str, list[TaskStepRecord]]:
        return {tid: self.list_steps(tid) for tid in task_ids}

    def list_events_batch(self, task_ids: list[str]) -> dict[str, list[TaskEventRecord]]:
        return {tid: self.list_events(tid) for tid in task_ids}

    def list_events_paginated(
        self,
        task_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[list[TaskEventRecord], int]:
        """Return (page, total_count). Default impl loads all then slices."""
        all_events = self.list_events(task_id)
        total = len(all_events)
        if limit is None:
            return all_events[offset:], total
        return all_events[offset : offset + limit], total

    @abstractmethod
    def replace_task_snapshot(
        self,
        task: TaskRecord,
        steps: list[TaskStepRecord],
        events: list[TaskEventRecord],
    ) -> None:
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
