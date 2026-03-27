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


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _task(
    task_id: str = "t1",
    status: TaskStatus = TaskStatus.COMPLETED,
    accepted_at: datetime | None = None,
    execution_mode: ExecutionMode = ExecutionMode.API,
    dry_run: bool = False,
    failure_code: FailureCode | None = None,
) -> TaskRecord:
    return TaskRecord(
        task_id=task_id,
        status=status,
        accepted_at=accepted_at or _now(),
        completed_at=None,
        duration_ms=None,
        prompt="test",
        reasoning=False,
        execution_mode=execution_mode,
        dry_run=dry_run,
        model_count=1,
        quorum=1,
        merge_strategy=MergeStrategy.FIRST_SUCCESS,
        adapter_hint=AdapterHint.API,
        cancel_on_quorum=False,
        failure_code=failure_code,
    )


def _step(task_id: str = "t1", step_index: int = 0) -> TaskStepRecord:
    return TaskStepRecord(
        task_id=task_id,
        step_index=step_index,
        model_id="m1",
        model_display_name="M1",
        backend="api",
        provider="anthropic",
        status=StepStatus.COMPLETED,
    )


def _event(task_id: str = "t1", seq: int = 0) -> TaskEventRecord:
    return TaskEventRecord(
        event_id=f"e-{task_id}-{seq}",
        task_id=task_id,
        sequence_no=seq,
        event_type=EventType.TASK_ACCEPTED,
        created_at=_now(),
    )


class SaveAndGetTests(unittest.TestCase):
    def test_save_and_get_roundtrip(self) -> None:
        repo = InMemoryTaskRepository()
        task = _task("t1")
        repo.save_task_with_steps(task, [])
        retrieved = repo.get("t1")
        self.assertIsNotNone(retrieved)
        assert retrieved is not None
        self.assertEqual(retrieved.task_id, "t1")

    def test_get_missing_returns_none(self) -> None:
        repo = InMemoryTaskRepository()
        self.assertIsNone(repo.get("nonexistent"))

    def test_save_overwrites_existing(self) -> None:
        repo = InMemoryTaskRepository()
        repo.save_task_with_steps(_task("t1", status=TaskStatus.COMPLETED), [])
        repo.save_task_with_steps(_task("t1", status=TaskStatus.FAILED), [])
        retrieved = repo.get("t1")
        assert retrieved is not None
        self.assertEqual(retrieved.status, TaskStatus.FAILED)

    def test_steps_saved_and_retrieved(self) -> None:
        repo = InMemoryTaskRepository()
        steps = [_step("t1", 0), _step("t1", 1)]
        repo.save_task_with_steps(_task("t1"), steps)
        retrieved_steps = repo.list_steps("t1")
        self.assertEqual(len(retrieved_steps), 2)

    def test_steps_missing_task_returns_empty(self) -> None:
        repo = InMemoryTaskRepository()
        self.assertEqual(repo.list_steps("nope"), [])


class ListRecentTests(unittest.TestCase):
    def test_returns_newest_first(self) -> None:
        repo = InMemoryTaskRepository()
        base = _now()
        for i in range(5):
            t = _task(f"t{i}", accepted_at=base + timedelta(seconds=i))
            repo.save_task_with_steps(t, [])
        recent = repo.list_recent(5)
        self.assertEqual(recent[0].task_id, "t4")
        self.assertEqual(recent[-1].task_id, "t0")

    def test_limit_respected(self) -> None:
        repo = InMemoryTaskRepository()
        for i in range(10):
            repo.save_task_with_steps(_task(f"t{i}"), [])
        self.assertEqual(len(repo.list_recent(3)), 3)

    def test_filter_by_status(self) -> None:
        repo = InMemoryTaskRepository()
        repo.save_task_with_steps(_task("t1", status=TaskStatus.COMPLETED), [])
        repo.save_task_with_steps(_task("t2", status=TaskStatus.FAILED), [])
        repo.save_task_with_steps(_task("t3", status=TaskStatus.COMPLETED), [])
        result = repo.list_recent(10, status=TaskStatus.COMPLETED)
        self.assertEqual(len(result), 2)
        self.assertTrue(all(t.status == TaskStatus.COMPLETED for t in result))

    def test_filter_by_execution_mode(self) -> None:
        repo = InMemoryTaskRepository()
        repo.save_task_with_steps(_task("t1", execution_mode=ExecutionMode.API), [])
        repo.save_task_with_steps(_task("t2", execution_mode=ExecutionMode.BROWSER), [])
        result = repo.list_recent(10, execution_mode=ExecutionMode.API)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].task_id, "t1")

    def test_filter_by_dry_run(self) -> None:
        repo = InMemoryTaskRepository()
        repo.save_task_with_steps(_task("t1", dry_run=True), [])
        repo.save_task_with_steps(_task("t2", dry_run=False), [])
        result = repo.list_recent(10, dry_run=True)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].task_id, "t1")

    def test_filter_by_failure_code(self) -> None:
        repo = InMemoryTaskRepository()
        repo.save_task_with_steps(_task("t1", failure_code=FailureCode.TIMEOUT), [])
        repo.save_task_with_steps(_task("t2", failure_code=None), [])
        result = repo.list_recent(10, failure_code=FailureCode.TIMEOUT)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].task_id, "t1")

    def test_filter_before_datetime(self) -> None:
        repo = InMemoryTaskRepository()
        base = _now()
        repo.save_task_with_steps(_task("old", accepted_at=base - timedelta(hours=2)), [])
        repo.save_task_with_steps(_task("new", accepted_at=base), [])
        cutoff = base - timedelta(hours=1)
        result = repo.list_recent(10, before=cutoff)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].task_id, "old")

    def test_empty_repo_returns_empty_list(self) -> None:
        repo = InMemoryTaskRepository()
        self.assertEqual(repo.list_recent(10), [])


class EventTests(unittest.TestCase):
    def test_append_and_list_events(self) -> None:
        repo = InMemoryTaskRepository()
        repo.append_event(_event("t1", 0))
        repo.append_event(_event("t1", 1))
        events = repo.list_events("t1")
        self.assertEqual(len(events), 2)

    def test_events_sorted_by_sequence_no(self) -> None:
        repo = InMemoryTaskRepository()
        repo.append_event(_event("t1", 2))
        repo.append_event(_event("t1", 0))
        repo.append_event(_event("t1", 1))
        events = repo.list_events("t1")
        self.assertEqual([e.sequence_no for e in events], [0, 1, 2])

    def test_duplicate_sequence_no_raises(self) -> None:
        repo = InMemoryTaskRepository()
        repo.append_event(_event("t1", 0))
        with self.assertRaises(ValueError):
            repo.append_event(_event("t1", 0))

    def test_events_for_missing_task_returns_empty(self) -> None:
        repo = InMemoryTaskRepository()
        self.assertEqual(repo.list_events("nope"), [])

    def test_events_isolated_by_task(self) -> None:
        repo = InMemoryTaskRepository()
        repo.append_event(_event("t1", 0))
        repo.append_event(_event("t2", 0))
        self.assertEqual(len(repo.list_events("t1")), 1)
        self.assertEqual(len(repo.list_events("t2")), 1)


class ReplaceSnapshotTests(unittest.TestCase):
    def test_replace_snapshot_updates_task(self) -> None:
        repo = InMemoryTaskRepository()
        repo.save_task_with_steps(_task("t1", status=TaskStatus.COMPLETED), [])
        updated = _task("t1", status=TaskStatus.FAILED)
        repo.replace_task_snapshot(updated, [], [])
        retrieved = repo.get("t1")
        assert retrieved is not None
        self.assertEqual(retrieved.status, TaskStatus.FAILED)

    def test_replace_snapshot_replaces_steps(self) -> None:
        repo = InMemoryTaskRepository()
        repo.save_task_with_steps(_task("t1"), [_step("t1", 0)])
        repo.replace_task_snapshot(_task("t1"), [_step("t1", 0), _step("t1", 1)], [])
        self.assertEqual(len(repo.list_steps("t1")), 2)

    def test_replace_snapshot_replaces_events_sorted(self) -> None:
        repo = InMemoryTaskRepository()
        repo.save_task_with_steps(_task("t1"), [])
        events = [_event("t1", 2), _event("t1", 0), _event("t1", 1)]
        repo.replace_task_snapshot(_task("t1"), [], events)
        retrieved = repo.list_events("t1")
        self.assertEqual([e.sequence_no for e in retrieved], [0, 1, 2])


class HealthcheckTests(unittest.TestCase):
    def test_healthcheck_status_ok(self) -> None:
        repo = InMemoryTaskRepository()
        hc = repo.healthcheck()
        self.assertEqual(hc["status"], "ok")

    def test_healthcheck_backend_name(self) -> None:
        repo = InMemoryTaskRepository()
        self.assertEqual(repo.healthcheck()["backend"], "memory")

    def test_healthcheck_task_count(self) -> None:
        repo = InMemoryTaskRepository()
        repo.save_task_with_steps(_task("t1"), [])
        repo.save_task_with_steps(_task("t2"), [])
        self.assertEqual(repo.healthcheck()["task_count"], 2)

    def test_healthcheck_step_count(self) -> None:
        repo = InMemoryTaskRepository()
        repo.save_task_with_steps(_task("t1"), [_step("t1", 0), _step("t1", 1)])
        self.assertEqual(repo.healthcheck()["step_count"], 2)

    def test_healthcheck_event_count(self) -> None:
        repo = InMemoryTaskRepository()
        repo.append_event(_event("t1", 0))
        repo.append_event(_event("t1", 1))
        self.assertEqual(repo.healthcheck()["event_count"], 2)


class EvictionTests(unittest.TestCase):
    def test_evicts_oldest_when_over_max(self) -> None:
        repo = InMemoryTaskRepository(max_tasks=3)
        base = _now()
        for i in range(4):
            t = _task(f"t{i}", accepted_at=base + timedelta(seconds=i))
            repo.save_task_with_steps(t, [])
        # oldest "t0" should be evicted
        self.assertIsNone(repo.get("t0"))
        self.assertIsNotNone(repo.get("t3"))

    def test_evicts_steps_with_task(self) -> None:
        repo = InMemoryTaskRepository(max_tasks=2)
        base = _now()
        for i in range(3):
            t = _task(f"t{i}", accepted_at=base + timedelta(seconds=i))
            repo.save_task_with_steps(t, [_step(f"t{i}", 0)])
        # t0 evicted — its steps should be gone too
        self.assertEqual(repo.list_steps("t0"), [])


class BatchTests(unittest.TestCase):
    def test_list_steps_batch(self) -> None:
        repo = InMemoryTaskRepository()
        repo.save_task_with_steps(_task("t1"), [_step("t1", 0)])
        repo.save_task_with_steps(_task("t2"), [_step("t2", 0), _step("t2", 1)])
        batch = repo.list_steps_batch(["t1", "t2"])
        self.assertEqual(len(batch["t1"]), 1)
        self.assertEqual(len(batch["t2"]), 2)

    def test_list_events_batch(self) -> None:
        repo = InMemoryTaskRepository()
        repo.append_event(_event("t1", 0))
        repo.append_event(_event("t2", 0))
        repo.append_event(_event("t2", 1))
        batch = repo.list_events_batch(["t1", "t2"])
        self.assertEqual(len(batch["t1"]), 1)
        self.assertEqual(len(batch["t2"]), 2)


if __name__ == "__main__":
    unittest.main()
