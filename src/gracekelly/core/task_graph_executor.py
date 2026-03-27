from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from gracekelly.core.task_graph import SubTaskStatus, TaskGraph


@dataclass(frozen=True, slots=True)
class GraphExecutionResult:
    completed: int
    failed: int
    skipped: int
    total: int
    results: dict[str, str]
    is_complete: bool


def execute_graph(
    graph: TaskGraph,
    execute_fn: Callable[[str], str],
    skip_on_dependency_failure: bool = True,
) -> GraphExecutionResult:
    results: dict[str, str] = {}

    for task_id in graph.topological_order():
        task = graph.get_task(task_id)
        if task is None:
            continue

        if skip_on_dependency_failure:
            dep_blocked = any(
                graph.get_task(dep) is not None
                and graph.get_task(dep).status in (SubTaskStatus.FAILED, SubTaskStatus.SKIPPED)
                for dep in task.dependencies
            )
            if dep_blocked:
                task.status = SubTaskStatus.SKIPPED
                continue

        task.status = SubTaskStatus.RUNNING
        try:
            result = execute_fn(task.prompt)
            graph.mark_completed(task.id, result)
            results[task.id] = result
        except Exception:
            graph.mark_failed(task.id)

    completed = sum(1 for t in graph.all_tasks() if t.status == SubTaskStatus.COMPLETED)
    failed = sum(1 for t in graph.all_tasks() if t.status == SubTaskStatus.FAILED)
    skipped = sum(1 for t in graph.all_tasks() if t.status == SubTaskStatus.SKIPPED)

    return GraphExecutionResult(
        completed=completed,
        failed=failed,
        skipped=skipped,
        total=graph.task_count(),
        results=results,
        is_complete=graph.is_complete(),
    )
