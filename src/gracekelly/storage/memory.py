from __future__ import annotations

from gracekelly.core.contracts import ExecutionMode, FailureCode, TaskStatus
from gracekelly.storage.base import TaskEventRecord, TaskRecord, TaskRepository, TaskStepRecord


class InMemoryTaskRepository(TaskRepository):
    backend_name = "memory"

    def __init__(self) -> None:
        self._tasks: dict[str, TaskRecord] = {}
        self._steps: dict[str, list[TaskStepRecord]] = {}
        self._events: dict[str, list[TaskEventRecord]] = {}

    def save_task_with_steps(
        self,
        task: TaskRecord,
        steps: list[TaskStepRecord],
    ) -> None:
        self._tasks[task.task_id] = task
        self._steps[task.task_id] = list(steps)

    def get(self, task_id: str) -> TaskRecord | None:
        return self._tasks.get(task_id)

    def list_recent(
        self,
        limit: int,
        *,
        status: TaskStatus | None = None,
        execution_mode: ExecutionMode | None = None,
        dry_run: bool | None = None,
        failure_code: FailureCode | None = None,
    ) -> list[TaskRecord]:
        tasks = self._tasks.values()
        if status is not None:
            tasks = [item for item in tasks if item.status == status]
        if execution_mode is not None:
            tasks = [item for item in tasks if item.execution_mode == execution_mode]
        if dry_run is not None:
            tasks = [item for item in tasks if item.dry_run == dry_run]
        if failure_code is not None:
            tasks = [item for item in tasks if item.failure_code == failure_code]
        return sorted(
            tasks,
            key=lambda item: item.accepted_at,
            reverse=True,
        )[:limit]

    def list_steps(self, task_id: str) -> list[TaskStepRecord]:
        return list(self._steps.get(task_id, []))

    def append_event(self, event: TaskEventRecord) -> None:
        task_events = self._events.setdefault(event.task_id, [])
        if any(item.sequence_no == event.sequence_no for item in task_events):
            raise ValueError(
                f"Duplicate sequence_no {event.sequence_no} for task '{event.task_id}'."
            )
        task_events.append(event)

    def list_events(self, task_id: str) -> list[TaskEventRecord]:
        return sorted(self._events.get(task_id, []), key=lambda item: item.sequence_no)

    def healthcheck(self) -> dict[str, object]:
        return {
            "status": "ok",
            "backend": self.backend_name,
            "task_count": len(self._tasks),
            "step_count": sum(len(items) for items in self._steps.values()),
            "event_count": sum(len(items) for items in self._events.values()),
        }
