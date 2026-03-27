from __future__ import annotations

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

_T0 = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _task(
    task_id: str,
    *,
    accepted_at: datetime = _T0,
    status: TaskStatus = TaskStatus.COMPLETED,
    execution_mode: ExecutionMode = ExecutionMode.API,
    dry_run: bool = False,
    failure_code: FailureCode | None = None,
) -> TaskRecord:
    return TaskRecord(
        task_id=task_id,
        status=status,
        accepted_at=accepted_at,
        completed_at=accepted_at,
        duration_ms=100,
        prompt="Q",
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


def _step(task_id: str, *, step_index: int = 0) -> TaskStepRecord:
    return TaskStepRecord(
        task_id=task_id,
        step_index=step_index,
        model_id="sonar",
        model_display_name="Sonar",
        backend="api",
        provider="perplexity",
        status=StepStatus.COMPLETED,
    )


def _event(task_id: str, seq: int = 1) -> TaskEventRecord:
    return TaskEventRecord(
        event_id=f"ev-{seq}",
        task_id=task_id,
        sequence_no=seq,
        event_type=EventType.TASK_COMPLETED,
        created_at=_T0,
    )


class InMemoryRepositoryGetTests(unittest.TestCase):
    def test_get_returns_none_for_unknown_task(self) -> None:
        repo = InMemoryTaskRepository()
        self.assertIsNone(repo.get("no-such-task"))

    def test_get_returns_saved_task(self) -> None:
        repo = InMemoryTaskRepository()
        task = _task("t1")
        repo.save_task_with_steps(task, [])
        self.assertIsNotNone(repo.get("t1"))

    def test_list_steps_returns_empty_for_unknown_task(self) -> None:
        repo = InMemoryTaskRepository()
        self.assertEqual(repo.list_steps("no-such"), [])

    def test_list_events_returns_empty_for_unknown_task(self) -> None:
        repo = InMemoryTaskRepository()
        self.assertEqual(repo.list_events("no-such"), [])


class InMemoryRepositoryListRecentFiltersTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = InMemoryTaskRepository()
        self.repo.save_task_with_steps(_task("t1", status=TaskStatus.COMPLETED), [])
        self.repo.save_task_with_steps(_task("t2", status=TaskStatus.FAILED), [])
        self.repo.save_task_with_steps(_task("t3", dry_run=True), [])
        self.repo.save_task_with_steps(
            _task("t4", execution_mode=ExecutionMode.DRY_RUN), []
        )
        self.repo.save_task_with_steps(
            _task("t5", failure_code=FailureCode.TIMEOUT), []
        )

    def test_filter_by_status_completed(self) -> None:
        results = self.repo.list_recent(100, status=TaskStatus.COMPLETED)
        ids = {r.task_id for r in results}
        self.assertIn("t1", ids)
        self.assertNotIn("t2", ids)

    def test_filter_by_dry_run_true(self) -> None:
        results = self.repo.list_recent(100, dry_run=True)
        ids = {r.task_id for r in results}
        self.assertIn("t3", ids)
        self.assertNotIn("t1", ids)

    def test_filter_by_execution_mode(self) -> None:
        results = self.repo.list_recent(100, execution_mode=ExecutionMode.DRY_RUN)
        ids = {r.task_id for r in results}
        self.assertIn("t4", ids)
        self.assertNotIn("t1", ids)

    def test_filter_by_failure_code(self) -> None:
        results = self.repo.list_recent(100, failure_code=FailureCode.TIMEOUT)
        ids = {r.task_id for r in results}
        self.assertIn("t5", ids)
        self.assertNotIn("t1", ids)

    def test_filter_by_before_excludes_later_tasks(self) -> None:
        later = _T0 + timedelta(hours=1)
        repo = InMemoryTaskRepository()
        repo.save_task_with_steps(_task("early", accepted_at=_T0), [])
        repo.save_task_with_steps(_task("late", accepted_at=later), [])
        results = repo.list_recent(100, before=later)
        ids = {r.task_id for r in results}
        self.assertIn("early", ids)
        self.assertNotIn("late", ids)

    def test_limit_respected(self) -> None:
        results = self.repo.list_recent(2)
        self.assertEqual(len(results), 2)

    def test_no_filters_returns_all(self) -> None:
        results = self.repo.list_recent(100)
        self.assertEqual(len(results), 5)


class InMemoryRepositoryEvictTests(unittest.TestCase):
    def test_evict_oldest_when_max_exceeded(self) -> None:
        repo = InMemoryTaskRepository(max_tasks=3)
        t0 = _T0
        for i in range(5):
            task = _task(f"t{i}", accepted_at=t0 + timedelta(minutes=i))
            repo.save_task_with_steps(task, [_step(f"t{i}")])

        # Only 3 most recent should survive
        results = repo.list_recent(10)
        self.assertEqual(len(results), 3)
        remaining_ids = {r.task_id for r in results}
        # t0 and t1 (oldest) should have been evicted
        self.assertNotIn("t0", remaining_ids)
        self.assertNotIn("t1", remaining_ids)
        self.assertIn("t4", remaining_ids)

    def test_evict_removes_steps_too(self) -> None:
        repo = InMemoryTaskRepository(max_tasks=1)
        repo.save_task_with_steps(_task("old"), [_step("old")])
        repo.save_task_with_steps(
            _task("new", accepted_at=_T0 + timedelta(minutes=1)),
            [],
        )
        # Steps for "old" should be gone
        self.assertEqual(repo.list_steps("old"), [])


class InMemoryRepositoryHealthcheckTests(unittest.TestCase):
    def test_healthcheck_returns_ok(self) -> None:
        repo = InMemoryTaskRepository()
        result = repo.healthcheck()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["backend"], "memory")

    def test_healthcheck_task_count(self) -> None:
        repo = InMemoryTaskRepository()
        for i in range(3):
            repo.save_task_with_steps(_task(f"t{i}"), [])
        self.assertEqual(repo.healthcheck()["task_count"], 3)

    def test_healthcheck_step_count(self) -> None:
        repo = InMemoryTaskRepository()
        repo.save_task_with_steps(_task("t1"), [_step("t1", step_index=0), _step("t1", step_index=1)])
        self.assertEqual(repo.healthcheck()["step_count"], 2)

    def test_healthcheck_event_count(self) -> None:
        repo = InMemoryTaskRepository()
        repo.save_task_with_steps(_task("t1"), [])
        repo.append_event(_event("t1", seq=1))
        repo.append_event(_event("t1", seq=2))
        self.assertEqual(repo.healthcheck()["event_count"], 2)


class InMemoryRepositoryBatchTests(unittest.TestCase):
    def test_list_steps_batch(self) -> None:
        repo = InMemoryTaskRepository()
        repo.save_task_with_steps(_task("t1"), [_step("t1")])
        repo.save_task_with_steps(_task("t2"), [_step("t2"), _step("t2", step_index=1)])
        batch = repo.list_steps_batch(["t1", "t2"])
        self.assertEqual(len(batch["t1"]), 1)
        self.assertEqual(len(batch["t2"]), 2)

    def test_list_events_batch(self) -> None:
        repo = InMemoryTaskRepository()
        repo.save_task_with_steps(_task("t1"), [])
        repo.save_task_with_steps(_task("t2"), [])
        repo.append_event(_event("t1", seq=1))
        repo.append_event(_event("t2", seq=1))
        batch = repo.list_events_batch(["t1", "t2"])
        self.assertEqual(len(batch["t1"]), 1)
        self.assertEqual(len(batch["t2"]), 1)


if __name__ == "__main__":
    unittest.main()
