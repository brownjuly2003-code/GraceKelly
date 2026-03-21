from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import StrEnum


class SubTaskStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(slots=True)
class SubTask:
    id: str
    prompt: str
    dependencies: tuple[str, ...] = ()
    status: SubTaskStatus = SubTaskStatus.PENDING
    result: str = ""


class TaskGraph:
    def __init__(self) -> None:
        self._tasks: dict[str, SubTask] = {}

    def add_task(self, task: SubTask) -> None:
        self._tasks[task.id] = task

    def get_task(self, task_id: str) -> SubTask | None:
        return self._tasks.get(task_id)

    def all_tasks(self) -> list[SubTask]:
        return list(self._tasks.values())

    def ready_tasks(self) -> list[SubTask]:
        ready = []
        for task in self._tasks.values():
            if task.status != SubTaskStatus.PENDING:
                continue
            deps_met = all(
                self._tasks[dep].status == SubTaskStatus.COMPLETED
                for dep in task.dependencies
                if dep in self._tasks
            )
            if deps_met:
                ready.append(task)
        return ready

    def mark_completed(self, task_id: str, result: str) -> None:
        task = self._tasks.get(task_id)
        if task:
            task.status = SubTaskStatus.COMPLETED
            task.result = result

    def mark_failed(self, task_id: str) -> None:
        task = self._tasks.get(task_id)
        if task:
            task.status = SubTaskStatus.FAILED

    def is_complete(self) -> bool:
        return all(
            t.status in (SubTaskStatus.COMPLETED, SubTaskStatus.FAILED, SubTaskStatus.SKIPPED)
            for t in self._tasks.values()
        )

    def topological_order(self) -> list[str]:
        adj: dict[str, list[str]] = {tid: [] for tid in self._tasks}
        in_deg: dict[str, int] = {tid: 0 for tid in self._tasks}
        for task in self._tasks.values():
            for dep in task.dependencies:
                if dep in adj:
                    adj[dep].append(task.id)
                    in_deg[task.id] += 1

        queue = deque(tid for tid, deg in in_deg.items() if deg == 0)
        order: list[str] = []
        while queue:
            tid = queue.popleft()
            order.append(tid)
            for neighbor in adj[tid]:
                in_deg[neighbor] -= 1
                if in_deg[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self._tasks):
            raise ValueError("Cycle detected in task graph")
        return order

    def task_count(self) -> int:
        return len(self._tasks)

    def completed_count(self) -> int:
        return sum(1 for t in self._tasks.values() if t.status == SubTaskStatus.COMPLETED)
