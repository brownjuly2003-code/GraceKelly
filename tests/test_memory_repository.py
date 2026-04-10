from __future__ import annotations

import threading
import unittest
from datetime import UTC, datetime, timedelta

from gracekelly.core.contracts import (
    AdapterHint,
    EventType,
    ExecutionMode,
    FailureCode,
    MergeStrategy,
    StepStatus,
    TaskStatus,
)
from gracekelly.storage.base import TaskEventRecord, TaskRecord, TaskStepRecord
from gracekelly.storage.memory import InMemoryTaskRepository

_NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _make_task(
    task_id: str = "t1",
    *,
    accepted_at: datetime = _NOW,
    prompt: str = "Q",
    status: TaskStatus = TaskStatus.COMPLETED,
    dry_run: bool = False,
    execution_mode: ExecutionMode = ExecutionMode.API,
    failure_code: FailureCode | None = None,
) -> TaskRecord:
    return TaskRecord(
        task_id=task_id,
        status=status,
        accepted_at=accepted_at,
        completed_at=_NOW,
        duration_ms=100,
        prompt=prompt,
        reasoning=False,
        execution_mode=execution_mode,
        dry_run=dry_run,
        model_count=1,
        quorum=1,
        merge_strategy=MergeStrategy.FIRST_SUCCESS,
        adapter_hint=AdapterHint.AUTO,
        cancel_on_quorum=True,
        failure_code=failure_code,
    )


def _make_step(task_id: str = "t1", step_index: int = 1) -> TaskStepRecord:
    return TaskStepRecord(
        task_id=task_id,
        step_index=step_index,
        model_id="mistral-small",
        model_display_name="Mistral Small",
        backend="api",
        provider="mistral",
        status=StepStatus.COMPLETED,
    )


def _make_event(task_id: str = "t1", seq: int = 1) -> TaskEventRecord:
    return TaskEventRecord(
        event_id=f"ev-{seq}",
        task_id=task_id,
        sequence_no=seq,
        event_type=EventType.TASK_COMPLETED,
        created_at=_NOW,
    )


class InMemoryRepositoryTests(unittest.TestCase):
    def test_list_recent_orders_tasks_by_accepted_at_desc(self) -> None:
        repository = InMemoryTaskRepository()
        older = datetime(2026, 3, 17, 10, 0, tzinfo=UTC)
        newer = datetime(2026, 3, 17, 10, 5, tzinfo=UTC)
        repository.save_task_with_steps(
            TaskRecord(
                task_id="task-older",
                status=TaskStatus.COMPLETED,
                accepted_at=older,
                completed_at=older,
                duration_ms=1,
                prompt="older",
                reasoning=False,
                execution_mode=ExecutionMode.DRY_RUN,
                dry_run=True,
                model_count=1,
                quorum=1,
                merge_strategy=MergeStrategy.FIRST_SUCCESS,
                adapter_hint=AdapterHint.AUTO,
                cancel_on_quorum=True,
            ),
            [],
        )
        repository.save_task_with_steps(
            TaskRecord(
                task_id="task-newer",
                status=TaskStatus.COMPLETED,
                accepted_at=newer,
                completed_at=newer,
                duration_ms=1,
                prompt="newer",
                reasoning=False,
                execution_mode=ExecutionMode.DRY_RUN,
                dry_run=True,
                model_count=1,
                quorum=1,
                merge_strategy=MergeStrategy.FIRST_SUCCESS,
                adapter_hint=AdapterHint.AUTO,
                cancel_on_quorum=True,
            ),
            [],
        )

        tasks = repository.list_recent(1)

        self.assertEqual([task.task_id for task in tasks], ["task-newer"])

    def test_list_recent_can_filter_by_status_and_dry_run(self) -> None:
        repository = InMemoryTaskRepository()
        accepted_at = datetime(2026, 3, 17, 10, 0, tzinfo=UTC)
        repository.save_task_with_steps(
            TaskRecord(
                task_id="task-completed",
                status=TaskStatus.COMPLETED,
                accepted_at=accepted_at,
                completed_at=accepted_at,
                duration_ms=1,
                prompt="completed",
                reasoning=False,
                execution_mode=ExecutionMode.DRY_RUN,
                dry_run=True,
                model_count=1,
                quorum=1,
                merge_strategy=MergeStrategy.FIRST_SUCCESS,
                adapter_hint=AdapterHint.AUTO,
                cancel_on_quorum=True,
            ),
            [],
        )
        repository.save_task_with_steps(
            TaskRecord(
                task_id="task-failed",
                status=TaskStatus.FAILED,
                accepted_at=accepted_at.replace(minute=1),
                completed_at=accepted_at.replace(minute=1),
                duration_ms=1,
                prompt="failed",
                reasoning=False,
                execution_mode=ExecutionMode.API,
                dry_run=False,
                model_count=1,
                quorum=1,
                merge_strategy=MergeStrategy.FIRST_SUCCESS,
                adapter_hint=AdapterHint.AUTO,
                cancel_on_quorum=True,
                failure_code=FailureCode.PROVIDER_UNAVAILABLE,
            ),
            [],
        )

        tasks = repository.list_recent(
            10,
            status=TaskStatus.FAILED,
            execution_mode=ExecutionMode.API,
            dry_run=False,
            failure_code=FailureCode.PROVIDER_UNAVAILABLE,
        )

        self.assertEqual([task.task_id for task in tasks], ["task-failed"])

    def test_list_events_orders_by_sequence_number(self) -> None:
        repository = InMemoryTaskRepository()
        created_at = datetime.now(UTC)
        repository.append_event(
            TaskEventRecord(
                event_id="event-2",
                task_id="task-1",
                sequence_no=2,
                event_type=EventType.TASK_COMPLETED,
                created_at=created_at,
                payload={},
            )
        )
        repository.append_event(
            TaskEventRecord(
                event_id="event-1",
                task_id="task-1",
                sequence_no=1,
                event_type=EventType.TASK_ACCEPTED,
                created_at=created_at,
                payload={},
            )
        )

        events = repository.list_events("task-1")

        self.assertEqual([event.sequence_no for event in events], [1, 2])
        self.assertEqual([event.event_type for event in events], ["task.accepted", "task.completed"])

    def test_append_event_rejects_duplicate_sequence_number_per_task(self) -> None:
        repository = InMemoryTaskRepository()
        created_at = datetime.now(UTC)
        repository.append_event(
            TaskEventRecord(
                event_id="event-1",
                task_id="task-1",
                sequence_no=1,
                event_type=EventType.TASK_ACCEPTED,
                created_at=created_at,
                payload={},
            )
        )

        with self.assertRaises(ValueError):
            repository.append_event(
                TaskEventRecord(
                    event_id="event-2",
                    task_id="task-1",
                    sequence_no=1,
                    event_type=EventType.TASK_COMPLETED,
                    created_at=created_at,
                    payload={},
                )
            )

    def test_replace_task_snapshot_replaces_steps_and_events_for_task(self) -> None:
        repository = InMemoryTaskRepository()
        created_at = datetime.now(UTC)
        repository.save_task_with_steps(
                TaskRecord(
                    task_id="task-1",
                    status=TaskStatus.COMPLETED,
                    accepted_at=created_at,
                    completed_at=created_at,
                    duration_ms=1,
                    prompt="before",
                    reasoning=False,
                    execution_mode=ExecutionMode.DRY_RUN,
                    dry_run=True,
                    model_count=1,
                    quorum=1,
                    merge_strategy=MergeStrategy.FIRST_SUCCESS,
                    adapter_hint=AdapterHint.AUTO,
                    cancel_on_quorum=True,
                ),
                [
                TaskStepRecord(
                    task_id="task-1",
                    step_index=1,
                        model_id="old-model",
                        model_display_name="Old Model",
                        backend="api",
                        provider="old",
                        status=StepStatus.COMPLETED,
                    )
                ],
            )
        repository.append_event(
            TaskEventRecord(
                event_id="event-1",
                task_id="task-1",
                sequence_no=1,
                event_type=EventType.TASK_ACCEPTED,
                created_at=created_at,
                payload={"before": True},
            )
        )

        repository.replace_task_snapshot(
            TaskRecord(
                task_id="task-1",
                status=TaskStatus.FAILED,
                accepted_at=created_at,
                completed_at=created_at,
                duration_ms=2,
                prompt="after",
                reasoning=False,
                execution_mode=ExecutionMode.API,
                dry_run=False,
                model_count=1,
                quorum=1,
                merge_strategy=MergeStrategy.FIRST_SUCCESS,
                adapter_hint=AdapterHint.AUTO,
                cancel_on_quorum=True,
                failure_code=FailureCode.PROVIDER_UNAVAILABLE,
            ),
            [
                TaskStepRecord(
                    task_id="task-1",
                    step_index=1,
                    model_id="new-model",
                    model_display_name="New Model",
                    backend="browser",
                    provider="perplexity",
                    status=StepStatus.FAILED,
                    failure_code=FailureCode.PROVIDER_UNAVAILABLE,
                )
            ],
            [
                TaskEventRecord(
                    event_id="event-2",
                    task_id="task-1",
                    sequence_no=1,
                    event_type=EventType.TASK_FAILED,
                    created_at=created_at,
                    payload={"after": True},
                )
            ],
        )

        task = repository.get("task-1")
        steps = repository.list_steps("task-1")
        events = repository.list_events("task-1")

        assert task is not None
        self.assertEqual(task.prompt, "after")
        self.assertEqual(task.status, TaskStatus.FAILED)
        self.assertEqual(steps[0].model_id, "new-model")
        self.assertEqual(steps[0].backend, "browser")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, EventType.TASK_FAILED)
        self.assertEqual(events[0].payload, {"after": True})


class InMemoryGetAndStepsTests(unittest.TestCase):
    def test_get_returns_none_for_missing_task(self) -> None:
        repo = InMemoryTaskRepository()
        self.assertIsNone(repo.get("no-such"))

    def test_saved_task_can_be_retrieved(self) -> None:
        repo = InMemoryTaskRepository()
        task = _make_task("abc")
        repo.save_task_with_steps(task, [])
        self.assertEqual(repo.get("abc"), task)

    def test_overwrite_replaces_task(self) -> None:
        repo = InMemoryTaskRepository()
        repo.save_task_with_steps(_make_task("t1", status=TaskStatus.ACCEPTED), [])
        repo.save_task_with_steps(_make_task("t1", status=TaskStatus.COMPLETED), [])
        result = repo.get("t1")
        assert result is not None
        self.assertEqual(result.status, TaskStatus.COMPLETED)

    def test_list_steps_returns_empty_for_unknown_task(self) -> None:
        repo = InMemoryTaskRepository()
        self.assertEqual(repo.list_steps("no-such"), [])

    def test_steps_are_independent_per_task(self) -> None:
        repo = InMemoryTaskRepository()
        repo.save_task_with_steps(_make_task("t1"), [_make_step("t1", 1)])
        repo.save_task_with_steps(_make_task("t2"), [_make_step("t2", 1), _make_step("t2", 2)])
        self.assertEqual(len(repo.list_steps("t1")), 1)
        self.assertEqual(len(repo.list_steps("t2")), 2)


class InMemoryListRecentEdgeCasesTests(unittest.TestCase):
    def test_filter_by_before_datetime(self) -> None:
        repo = InMemoryTaskRepository()
        cutoff = _NOW
        repo.save_task_with_steps(
            _make_task("before", accepted_at=cutoff - timedelta(hours=1)), []
        )
        repo.save_task_with_steps(
            _make_task("after", accepted_at=cutoff + timedelta(hours=1)), []
        )
        result = repo.list_recent(10, before=cutoff)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].task_id, "before")

    def test_empty_repo_returns_empty_list(self) -> None:
        self.assertEqual(InMemoryTaskRepository().list_recent(10), [])

    def test_limit_truncates_result(self) -> None:
        repo = InMemoryTaskRepository()
        for i in range(5):
            repo.save_task_with_steps(
                _make_task(f"t{i}", accepted_at=_NOW + timedelta(seconds=i)), []
            )
        self.assertEqual(len(repo.list_recent(3)), 3)

    def test_filter_by_failure_code(self) -> None:
        repo = InMemoryTaskRepository()
        repo.save_task_with_steps(
            _make_task("t1", status=TaskStatus.FAILED, failure_code=FailureCode.TIMEOUT), []
        )
        repo.save_task_with_steps(
            _make_task("t2", status=TaskStatus.FAILED, failure_code=FailureCode.AUTH_FAILED), []
        )
        result = repo.list_recent(10, failure_code=FailureCode.TIMEOUT)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].task_id, "t1")


class InMemoryPromptFilterTests(unittest.TestCase):
    def test_list_recent_prompt_contains_filters_by_substring(self) -> None:
        repo = InMemoryTaskRepository()
        repo.save_task_with_steps(
            _make_task("alpha-task", accepted_at=_NOW, prompt="Alpha request"), []
        )
        repo.save_task_with_steps(
            _make_task(
                "beta-task",
                accepted_at=_NOW + timedelta(seconds=1),
                prompt="Beta request",
            ),
            [],
        )

        result = repo.list_recent(10, prompt_contains="alpHA")

        self.assertEqual([task.task_id for task in result], ["alpha-task"])

    def test_list_recent_prompt_contains_no_match_returns_empty(self) -> None:
        repo = InMemoryTaskRepository()
        repo.save_task_with_steps(_make_task("alpha-task", prompt="Alpha request"), [])

        result = repo.list_recent(10, prompt_contains="zzznomatch")

        self.assertEqual(result, [])


class InMemoryEvictionTests(unittest.TestCase):
    def test_max_tasks_evicts_oldest(self) -> None:
        repo = InMemoryTaskRepository(max_tasks=3)
        for i in range(3):
            repo.save_task_with_steps(
                _make_task(f"t{i}", accepted_at=_NOW + timedelta(seconds=i)), []
            )
        repo.save_task_with_steps(
            _make_task("t3", accepted_at=_NOW + timedelta(seconds=3)), []
        )
        self.assertIsNone(repo.get("t0"))
        self.assertIsNotNone(repo.get("t3"))

    def test_eviction_removes_steps(self) -> None:
        repo = InMemoryTaskRepository(max_tasks=1)
        repo.save_task_with_steps(_make_task("old"), [_make_step("old")])
        repo.save_task_with_steps(
            _make_task("new", accepted_at=_NOW + timedelta(seconds=1)), []
        )
        self.assertEqual(repo.list_steps("old"), [])

    def test_eviction_removes_events(self) -> None:
        repo = InMemoryTaskRepository(max_tasks=1)
        repo.save_task_with_steps(_make_task("old"), [])
        repo.append_event(_make_event("old", seq=1))
        repo.save_task_with_steps(
            _make_task("new", accepted_at=_NOW + timedelta(seconds=1)), []
        )
        self.assertEqual(repo.list_events("old"), [])

    def test_no_eviction_when_at_capacity(self) -> None:
        repo = InMemoryTaskRepository(max_tasks=3)
        for i in range(3):
            repo.save_task_with_steps(
                _make_task(f"t{i}", accepted_at=_NOW + timedelta(seconds=i)), []
            )
        for i in range(3):
            self.assertIsNotNone(repo.get(f"t{i}"))


class InMemoryHealthcheckTests(unittest.TestCase):
    def test_status_is_ok(self) -> None:
        self.assertEqual(InMemoryTaskRepository().healthcheck()["status"], "ok")

    def test_backend_name_is_memory(self) -> None:
        self.assertEqual(InMemoryTaskRepository().healthcheck()["backend"], "memory")

    def test_counts_tasks_and_steps(self) -> None:
        repo = InMemoryTaskRepository()
        repo.save_task_with_steps(_make_task("t1"), [_make_step("t1")])
        hc = repo.healthcheck()
        self.assertEqual(hc["task_count"], 1)
        self.assertEqual(hc["step_count"], 1)

    def test_counts_events(self) -> None:
        repo = InMemoryTaskRepository()
        repo.save_task_with_steps(_make_task("t1"), [])
        repo.append_event(_make_event("t1", seq=1))
        repo.append_event(_make_event("t1", seq=2))
        self.assertEqual(repo.healthcheck()["event_count"], 2)

    def test_empty_repo_all_counts_zero(self) -> None:
        hc = InMemoryTaskRepository().healthcheck()
        self.assertEqual(hc["task_count"], 0)
        self.assertEqual(hc["step_count"], 0)
        self.assertEqual(hc["event_count"], 0)


class InMemoryThreadSafetyTests(unittest.TestCase):
    def test_concurrent_saves_do_not_corrupt(self) -> None:
        repo = InMemoryTaskRepository()
        errors: list[Exception] = []

        def worker(task_id: str) -> None:
            try:
                repo.save_task_with_steps(
                    _make_task(task_id, accepted_at=_NOW + timedelta(microseconds=int(task_id[1:]))),
                    [_make_step(task_id)],
                )
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(f"t{i}",)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        self.assertEqual(repo.healthcheck()["task_count"], 20)


if __name__ == "__main__":
    unittest.main()
