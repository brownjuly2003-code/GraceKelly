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
from gracekelly.storage.postgres import PostgresTaskRepository


class TaskFromRowTests(unittest.TestCase):
    """Unit tests for PostgresTaskRepository row-mapping methods without a live DB."""

    def _repo(self) -> PostgresTaskRepository:
        repo = object.__new__(PostgresTaskRepository)
        repo._dsn = "postgresql://test:test@localhost/test"
        repo._connect_timeout_seconds = 5
        return repo

    def _task_row(self, **overrides) -> dict:
        base = {
            "task_id": "t1",
            "status": "completed",
            "accepted_at": datetime(2026, 3, 19, tzinfo=UTC),
            "completed_at": datetime(2026, 3, 19, 0, 1, tzinfo=UTC),
            "duration_ms": 500,
            "prompt": "Hello",
            "reasoning": False,
            "execution_mode": "api",
            "dry_run": False,
            "model_count": 1,
            "quorum": 1,
            "merge_strategy": "first_success",
            "adapter_hint": "auto",
            "cancel_on_quorum": True,
            "failure_code": None,
            "failure_message": None,
            "output_text": "World",
            "metadata": {},
        }
        base.update(overrides)
        return base

    def test_basic_task_mapping(self) -> None:
        repo = self._repo()
        task = repo._task_from_row(self._task_row())
        self.assertEqual(task.task_id, "t1")
        self.assertEqual(task.status, TaskStatus.COMPLETED)
        self.assertEqual(task.execution_mode, ExecutionMode.API)
        self.assertEqual(task.merge_strategy, MergeStrategy.FIRST_SUCCESS)
        self.assertEqual(task.adapter_hint, AdapterHint.AUTO)
        self.assertEqual(task.output_text, "World")
        self.assertTrue(task.cancel_on_quorum)
        self.assertIsNone(task.failure_code)

    def test_task_with_failure(self) -> None:
        repo = self._repo()
        task = repo._task_from_row(self._task_row(
            status="failed",
            failure_code="timeout",
            failure_message="timed out",
            output_text=None,
        ))
        self.assertEqual(task.status, TaskStatus.FAILED)
        self.assertEqual(task.failure_code, FailureCode.TIMEOUT)
        self.assertEqual(task.failure_message, "timed out")

    def test_task_metadata_string_parsed(self) -> None:
        repo = self._repo()
        task = repo._task_from_row(self._task_row(metadata='{"trace_id": "abc"}'))
        self.assertEqual(task.metadata, {"trace_id": "abc"})

    def test_task_metadata_dict_passthrough(self) -> None:
        repo = self._repo()
        task = repo._task_from_row(self._task_row(metadata={"key": "value"}))
        self.assertEqual(task.metadata, {"key": "value"})


class StepFromRowTests(unittest.TestCase):
    def _repo(self) -> PostgresTaskRepository:
        repo = object.__new__(PostgresTaskRepository)
        repo._dsn = "postgresql://test:test@localhost/test"
        repo._connect_timeout_seconds = 5
        return repo

    def _step_row(self, **overrides) -> dict:
        base = {
            "task_id": "t1",
            "step_index": 1,
            "model_id": "mistral-small",
            "model_display_name": "Mistral Small",
            "backend": "api",
            "provider": "mistral",
            "status": "completed",
            "failure_code": None,
            "failure_message": None,
            "output_text": "OK",
            "duration_ms": 200,
        }
        base.update(overrides)
        return base

    def test_basic_step_mapping(self) -> None:
        repo = self._repo()
        step = repo._step_from_row(self._step_row())
        self.assertEqual(step.task_id, "t1")
        self.assertEqual(step.step_index, 1)
        self.assertEqual(step.model_id, "mistral-small")
        self.assertEqual(step.status, StepStatus.COMPLETED)
        self.assertIsNone(step.failure_code)
        self.assertEqual(step.output_text, "OK")

    def test_step_with_failure(self) -> None:
        repo = self._repo()
        step = repo._step_from_row(self._step_row(
            status="failed",
            failure_code="rate_limited",
            failure_message="too fast",
            output_text=None,
        ))
        self.assertEqual(step.status, StepStatus.FAILED)
        self.assertEqual(step.failure_code, FailureCode.RATE_LIMITED)

    def test_step_cancelled(self) -> None:
        repo = self._repo()
        step = repo._step_from_row(self._step_row(status="cancelled"))
        self.assertEqual(step.status, StepStatus.CANCELLED)


class EventFromRowTests(unittest.TestCase):
    def _repo(self) -> PostgresTaskRepository:
        repo = object.__new__(PostgresTaskRepository)
        repo._dsn = "postgresql://test:test@localhost/test"
        repo._connect_timeout_seconds = 5
        return repo

    def _event_row(self, **overrides) -> dict:
        base = {
            "event_id": "e1",
            "task_id": "t1",
            "sequence_no": 1,
            "event_type": "task.accepted",
            "created_at": datetime(2026, 3, 19, tzinfo=UTC),
            "payload": {"execution_plan": {}},
        }
        base.update(overrides)
        return base

    def test_basic_event_mapping(self) -> None:
        repo = self._repo()
        event = repo._event_from_row(self._event_row())
        self.assertEqual(event.event_id, "e1")
        self.assertEqual(event.task_id, "t1")
        self.assertEqual(event.sequence_no, 1)
        self.assertEqual(event.event_type, EventType.TASK_ACCEPTED)
        self.assertEqual(event.payload, {"execution_plan": {}})

    def test_event_payload_string_parsed(self) -> None:
        repo = self._repo()
        event = repo._event_from_row(self._event_row(payload='{"key": "value"}'))
        self.assertEqual(event.payload, {"key": "value"})

    def test_event_payload_dict_passthrough(self) -> None:
        repo = self._repo()
        event = repo._event_from_row(self._event_row(payload={"foo": 42}))
        self.assertEqual(event.payload, {"foo": 42})

    def test_event_types(self) -> None:
        repo = self._repo()
        for event_type in ("task.accepted", "task.completed", "task.failed", "step.completed", "step.failed", "task.cancelled"):
            event = repo._event_from_row(self._event_row(event_type=event_type))
            self.assertEqual(event.event_type, EventType(event_type))


class TaskParamsTests(unittest.TestCase):
    def _repo(self) -> PostgresTaskRepository:
        repo = object.__new__(PostgresTaskRepository)
        repo._dsn = "postgresql://test:test@localhost/test"
        repo._connect_timeout_seconds = 5
        return repo

    def _base_task(self, **overrides):  # type: ignore[return]
        from gracekelly.storage.base import TaskRecord
        base = dict(
            task_id="t1",
            status=TaskStatus.COMPLETED,
            accepted_at=datetime(2026, 3, 19, tzinfo=UTC),
            completed_at=datetime(2026, 3, 19, 0, 1, tzinfo=UTC),
            duration_ms=500,
            prompt="Hi",
            reasoning=False,
            execution_mode=ExecutionMode.API,
            dry_run=False,
            model_count=1,
            quorum=1,
            merge_strategy=MergeStrategy.FIRST_SUCCESS,
            adapter_hint=AdapterHint.AUTO,
            cancel_on_quorum=True,
        )
        base.update(overrides)
        return TaskRecord(**base)

    def test_task_params_serializes_metadata(self) -> None:
        repo = self._repo()
        task = self._base_task(metadata={"trace_id": "abc"})
        params = repo._task_params(task)
        self.assertEqual(params["task_id"], "t1")
        self.assertEqual(params["metadata"], '{"trace_id": "abc"}')
        self.assertIsInstance(params["metadata"], str)

    def test_task_params_failure_fields_passed_through(self) -> None:
        repo = self._repo()
        task = self._base_task(
            status=TaskStatus.FAILED,
            failure_code=FailureCode.TIMEOUT,
            failure_message="timed out",
        )
        params = repo._task_params(task)
        self.assertEqual(params["failure_code"], FailureCode.TIMEOUT)
        self.assertEqual(params["failure_message"], "timed out")

    def test_task_params_retry_of_task_id_included(self) -> None:
        repo = self._repo()
        task = self._base_task(retry_of_task_id="original-task")
        params = repo._task_params(task)
        self.assertEqual(params["retry_of_task_id"], "original-task")

    def test_task_params_retry_of_task_id_none_by_default(self) -> None:
        repo = self._repo()
        task = self._base_task()
        params = repo._task_params(task)
        self.assertIsNone(params["retry_of_task_id"])

    def test_task_from_row_retry_of_task_id_populated(self) -> None:
        repo = self._repo()
        row = {
            "task_id": "t2",
            "status": "completed",
            "accepted_at": datetime(2026, 3, 19, tzinfo=UTC),
            "completed_at": datetime(2026, 3, 19, 0, 1, tzinfo=UTC),
            "duration_ms": 100,
            "prompt": "retry",
            "reasoning": False,
            "execution_mode": "api",
            "dry_run": False,
            "model_count": 1,
            "quorum": 1,
            "merge_strategy": "first_success",
            "adapter_hint": "auto",
            "cancel_on_quorum": False,
            "failure_code": None,
            "failure_message": None,
            "output_text": None,
            "metadata": {},
            "retry_of_task_id": "orig-task-id",
        }
        task = repo._task_from_row(row)
        self.assertEqual(task.retry_of_task_id, "orig-task-id")


class StepParamsTests(unittest.TestCase):
    def _repo(self) -> PostgresTaskRepository:
        repo = object.__new__(PostgresTaskRepository)
        repo._dsn = "postgresql://test:test@localhost/test"
        repo._connect_timeout_seconds = 5
        return repo

    def test_step_params_basic_fields(self) -> None:
        from gracekelly.storage.base import TaskStepRecord
        repo = self._repo()
        step = TaskStepRecord(
            task_id="t1",
            step_index=2,
            model_id="mistral-small",
            model_display_name="Mistral Small",
            backend="api",
            provider="mistral",
            status="completed",
            output_text="result",
            duration_ms=300,
        )
        params = repo._step_params(step)
        self.assertEqual(params["task_id"], "t1")
        self.assertEqual(params["step_index"], 2)
        self.assertEqual(params["model_id"], "mistral-small")
        self.assertEqual(params["backend"], "api")
        self.assertEqual(params["status"], "completed")
        self.assertEqual(params["output_text"], "result")
        self.assertEqual(params["duration_ms"], 300)

    def test_step_params_failure_fields(self) -> None:
        from gracekelly.storage.base import TaskStepRecord
        repo = self._repo()
        step = TaskStepRecord(
            task_id="t1",
            step_index=1,
            model_id="kimi-k2-5",
            model_display_name="Kimi K2.5",
            backend="browser",
            provider="perplexity",
            status="failed",
            failure_code=FailureCode.AUTH_FAILED,
            failure_message="login failed",
        )
        params = repo._step_params(step)
        self.assertEqual(params["failure_code"], FailureCode.AUTH_FAILED)
        self.assertEqual(params["failure_message"], "login failed")
