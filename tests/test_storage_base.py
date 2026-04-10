from __future__ import annotations

import unittest
from datetime import UTC, datetime

from gracekelly.core.contracts import (
    AdapterHint,
    EventType,
    ExecutionMode,
    FailureCode,
    MergeStrategy,
    StepStatus,
    TaskStatus,
)
from gracekelly.storage.base import (
    TaskEventRecord,
    TaskRecord,
    TaskRepository,
    TaskStepRecord,
)

# ---------------------------------------------------------------------------
# Minimal concrete repository for testing the non-abstract methods
# ---------------------------------------------------------------------------

class _StubRepository(TaskRepository):
    backend_name = "stub"

    def __init__(self) -> None:
        self._tasks: dict[str, TaskRecord] = {}
        self._steps: dict[str, list[TaskStepRecord]] = {}
        self._events: dict[str, list[TaskEventRecord]] = {}

    def save_task_with_steps(self, task: TaskRecord, steps: list[TaskStepRecord]) -> None:
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
        before: datetime | None = None,
        prompt_contains: str | None = None,
    ) -> list[TaskRecord]:
        return list(self._tasks.values())[:limit]

    def list_steps(self, task_id: str) -> list[TaskStepRecord]:
        return self._steps.get(task_id, [])

    def append_event(self, event: TaskEventRecord) -> None:
        self._events.setdefault(event.task_id, []).append(event)

    def list_events(self, task_id: str) -> list[TaskEventRecord]:
        return self._events.get(task_id, [])

    def replace_task_snapshot(self, task: TaskRecord, steps: list[TaskStepRecord],
                               events: list[TaskEventRecord]) -> None:
        self._tasks[task.task_id] = task
        self._steps[task.task_id] = list(steps)
        self._events[task.task_id] = list(events)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _task(task_id: str = "t1") -> TaskRecord:
    return TaskRecord(
        task_id=task_id,
        status=TaskStatus.COMPLETED,
        accepted_at=_NOW,
        completed_at=_NOW,
        duration_ms=100,
        prompt="Test prompt",
        reasoning=False,
        execution_mode=ExecutionMode.API,
        dry_run=False,
        model_count=1,
        quorum=1,
        merge_strategy=MergeStrategy.FIRST_SUCCESS,
        adapter_hint=AdapterHint.AUTO,
        cancel_on_quorum=False,
    )


def _step(task_id: str = "t1", step_index: int = 0) -> TaskStepRecord:
    return TaskStepRecord(
        task_id=task_id,
        step_index=step_index,
        model_id="gpt-4o",
        model_display_name="GPT-4o",
        backend="api",
        provider="openai",
        status=StepStatus.COMPLETED,
    )


def _event(task_id: str = "t1", seq: int = 0) -> TaskEventRecord:
    return TaskEventRecord(
        event_id=f"e-{seq}",
        task_id=task_id,
        sequence_no=seq,
        event_type=EventType.TASK_COMPLETED,
        created_at=_NOW,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TaskRepositoryHealthcheckTests(unittest.TestCase):
    def test_default_healthcheck_status_ok(self) -> None:
        repo = _StubRepository()
        hc = repo.healthcheck()
        self.assertEqual(hc["status"], "ok")

    def test_default_healthcheck_backend_name(self) -> None:
        repo = _StubRepository()
        hc = repo.healthcheck()
        self.assertEqual(hc["backend"], "stub")


class TaskRepositorySchemaReportTests(unittest.TestCase):
    def test_schema_report_status_ok(self) -> None:
        report = _StubRepository().schema_report()
        self.assertEqual(report["status"], "ok")

    def test_schema_report_backend(self) -> None:
        report = _StubRepository().schema_report()
        self.assertEqual(report["backend"], "stub")

    def test_schema_report_version_not_applicable(self) -> None:
        report = _StubRepository().schema_report()
        self.assertEqual(report["schema_version"], "not_applicable")


class TaskRepositoryBatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = _StubRepository()
        for tid in ("t1", "t2", "t3"):
            task = _task(tid)
            steps = [_step(tid, 0)]
            self.repo.save_task_with_steps(task, steps)
            self.repo.append_event(_event(tid, 0))
            self.repo.append_event(_event(tid, 1))

    def test_list_steps_batch_returns_all_requested(self) -> None:
        result = self.repo.list_steps_batch(["t1", "t2"])
        self.assertIn("t1", result)
        self.assertIn("t2", result)
        self.assertNotIn("t3", result)

    def test_list_steps_batch_correct_steps(self) -> None:
        result = self.repo.list_steps_batch(["t1"])
        self.assertEqual(len(result["t1"]), 1)
        self.assertEqual(result["t1"][0].task_id, "t1")

    def test_list_events_batch_returns_all_requested(self) -> None:
        result = self.repo.list_events_batch(["t2", "t3"])
        self.assertIn("t2", result)
        self.assertIn("t3", result)

    def test_list_events_batch_correct_events(self) -> None:
        result = self.repo.list_events_batch(["t1"])
        self.assertEqual(len(result["t1"]), 2)

    def test_batch_empty_list(self) -> None:
        self.assertEqual(self.repo.list_steps_batch([]), {})
        self.assertEqual(self.repo.list_events_batch([]), {})

    def test_batch_missing_task_returns_empty_list(self) -> None:
        result = self.repo.list_steps_batch(["no-such-task"])
        self.assertEqual(result["no-such-task"], [])


class TaskRecordFieldsTests(unittest.TestCase):
    def test_optional_fields_default_to_none(self) -> None:
        task = _task()
        self.assertIsNone(task.failure_code)
        self.assertIsNone(task.failure_message)
        self.assertIsNone(task.output_text)
        self.assertIsNone(task.retry_of_task_id)

    def test_metadata_defaults_to_empty_dict(self) -> None:
        task = _task()
        self.assertEqual(task.metadata, {})

    def test_task_status_roundtrip(self) -> None:
        task = _task()
        self.assertEqual(task.status, TaskStatus.COMPLETED)

    def test_failure_code_can_be_set(self) -> None:
        task = _task()
        task.failure_code = FailureCode.TIMEOUT
        self.assertEqual(task.failure_code, FailureCode.TIMEOUT)


class TaskStepRecordFieldsTests(unittest.TestCase):
    def test_optional_fields_default_to_none(self) -> None:
        step = _step()
        self.assertIsNone(step.failure_code)
        self.assertIsNone(step.failure_message)
        self.assertIsNone(step.output_text)
        self.assertIsNone(step.duration_ms)

    def test_step_status_roundtrip(self) -> None:
        step = _step()
        self.assertEqual(step.status, StepStatus.COMPLETED)


class TaskEventRecordFieldsTests(unittest.TestCase):
    def test_payload_defaults_to_empty_dict(self) -> None:
        event = _event()
        self.assertEqual(event.payload, {})

    def test_event_type_roundtrip(self) -> None:
        event = _event()
        self.assertEqual(event.event_type, EventType.TASK_COMPLETED)


if __name__ == "__main__":
    unittest.main()
