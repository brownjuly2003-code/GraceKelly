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
from gracekelly.schemas import OrchestrateResponse, TaskEventView, TaskListItem, TaskView
from gracekelly.storage.base import TaskEventRecord, TaskRecord, TaskStepRecord

_NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _task(
    *,
    task_id: str = "t1",
    status: TaskStatus = TaskStatus.COMPLETED,
    dry_run: bool = False,
    model_count: int = 1,
    merge_strategy: MergeStrategy = MergeStrategy.FIRST_SUCCESS,
    failure_code: FailureCode | None = None,
    failure_message: str | None = None,
    output_text: str | None = "answer",
    prompt: str = "Q",
    quorum: int = 1,
    cancel_on_quorum: bool = True,
    retry_of_task_id: str | None = None,
    metadata: dict | None = None,
) -> TaskRecord:
    return TaskRecord(
        task_id=task_id,
        status=status,
        accepted_at=_NOW,
        completed_at=_NOW,
        duration_ms=100,
        prompt=prompt,
        reasoning=False,
        execution_mode=ExecutionMode.API,
        dry_run=dry_run,
        model_count=model_count,
        quorum=quorum,
        merge_strategy=merge_strategy,
        adapter_hint=AdapterHint.AUTO,
        cancel_on_quorum=cancel_on_quorum,
        failure_code=failure_code,
        failure_message=failure_message,
        output_text=output_text,
        metadata=metadata or {},
        retry_of_task_id=retry_of_task_id,
    )


def _step(
    *,
    task_id: str = "t1",
    step_index: int = 1,
    model_id: str = "sonar",
    display: str = "Sonar",
    status: StepStatus = StepStatus.COMPLETED,
    output_text: str | None = "answer",
    duration_ms: int | None = 50,
) -> TaskStepRecord:
    return TaskStepRecord(
        task_id=task_id,
        step_index=step_index,
        model_id=model_id,
        model_display_name=display,
        backend="api",
        provider="perplexity",
        status=status,
        output_text=output_text,
        duration_ms=duration_ms,
    )


def _event(
    *,
    task_id: str = "t1",
    seq: int = 1,
    event_type: EventType = EventType.TASK_COMPLETED,
    payload: dict | None = None,
) -> TaskEventRecord:
    return TaskEventRecord(
        event_id=f"ev-{seq}",
        task_id=task_id,
        sequence_no=seq,
        event_type=event_type,
        created_at=_NOW,
        payload=payload or {},
    )


class OrchestrateResponseFromTaskTests(unittest.TestCase):
    """Tests for OrchestrateResponse.from_task factory."""

    def test_basic_fields_from_task(self) -> None:
        task = _task(task_id="abc")
        response = OrchestrateResponse.from_task(task)
        self.assertEqual(response.task_id, "abc")
        self.assertEqual(response.status, TaskStatus.COMPLETED.value)
        self.assertEqual(response.accepted_at, _NOW)

    def test_output_text_carried_through(self) -> None:
        task = _task(output_text="the result")
        response = OrchestrateResponse.from_task(task)
        self.assertEqual(response.output_text, "the result")

    def test_failure_code_carried_through(self) -> None:
        task = _task(
            status=TaskStatus.FAILED,
            output_text=None,
            failure_code=FailureCode.TIMEOUT,
            failure_message="timed out",
        )
        response = OrchestrateResponse.from_task(task)
        self.assertEqual(response.failure_code, FailureCode.TIMEOUT.value)
        self.assertEqual(response.failure_message, "timed out")

    def test_dry_run_adapter_name(self) -> None:
        task = _task(dry_run=True)
        response = OrchestrateResponse.from_task(task)
        self.assertEqual(response.adapter_name, "dry-run")

    def test_no_steps_adapter_name_unknown(self) -> None:
        task = _task(dry_run=False)
        response = OrchestrateResponse.from_task(task, steps=[])
        self.assertEqual(response.adapter_name, "unknown")

    def test_step_adapter_name_resolved(self) -> None:
        task = _task()
        response = OrchestrateResponse.from_task(task, steps=[_step()])
        self.assertEqual(response.adapter_name, "api.perplexity")

    def test_winning_model_set_for_first_success(self) -> None:
        task = _task()
        response = OrchestrateResponse.from_task(task, steps=[_step()])
        self.assertIsNotNone(response.model)
        assert response.model is not None
        self.assertEqual(response.model.id, "sonar")

    def test_winning_model_none_for_failed_task(self) -> None:
        task = _task(status=TaskStatus.FAILED, output_text=None)
        response = OrchestrateResponse.from_task(task, steps=[_step()])
        self.assertIsNone(response.model)

    def test_requested_models_from_steps(self) -> None:
        task = _task()
        response = OrchestrateResponse.from_task(task, steps=[_step(model_id="sonar")])
        ids = [m.id for m in response.requested_models]
        self.assertIn("sonar", ids)

    def test_requested_models_override_respected(self) -> None:
        from gracekelly.schemas import ModelView

        task = _task()
        override = [ModelView(id="gpt-5", display_name="GPT-5")]
        response = OrchestrateResponse.from_task(task, requested_models_override=override)
        self.assertEqual(len(response.requested_models), 1)
        self.assertEqual(response.requested_models[0].id, "gpt-5")

    def test_none_steps_treated_as_empty(self) -> None:
        task = _task()
        response = OrchestrateResponse.from_task(task, steps=None)
        self.assertEqual(response.requested_models, [])

    def test_none_events_treated_as_empty(self) -> None:
        task = _task()
        # Should not raise
        response = OrchestrateResponse.from_task(task, events=None)
        self.assertIsNotNone(response)


class TaskListItemFromTaskTests(unittest.TestCase):
    """Tests for TaskListItem.from_task factory."""

    def test_basic_fields(self) -> None:
        task = _task(task_id="t42")
        item = TaskListItem.from_task(task)
        self.assertEqual(item.task_id, "t42")
        self.assertEqual(item.status, TaskStatus.COMPLETED.value)
        self.assertFalse(item.dry_run)
        self.assertEqual(item.model_count, 1)

    def test_cancelled_step_count_from_event_payload(self) -> None:
        task = _task(status=TaskStatus.COMPLETED)
        ev = _event(
            event_type=EventType.TASK_COMPLETED,
            payload={"cancelled_steps": [2, 3], "cancel_reason": "quorum_reached"},
        )
        item = TaskListItem.from_task(task, events=[ev])
        self.assertEqual(item.cancelled_step_count, 2)
        self.assertEqual(item.cancel_reason, "quorum_reached")

    def test_cancelled_step_count_zero_when_none_cancelled(self) -> None:
        task = _task()
        item = TaskListItem.from_task(task, steps=[_step()])
        self.assertEqual(item.cancelled_step_count, 0)
        self.assertIsNone(item.cancel_reason)

    def test_failure_fields_propagated(self) -> None:
        task = _task(
            status=TaskStatus.FAILED,
            output_text=None,
            failure_code=FailureCode.AUTH_FAILED,
            failure_message="bad auth",
        )
        item = TaskListItem.from_task(task)
        self.assertEqual(item.failure_code, FailureCode.AUTH_FAILED.value)
        self.assertEqual(item.failure_message, "bad auth")

    def test_none_steps_and_events_handled(self) -> None:
        task = _task()
        item = TaskListItem.from_task(task, steps=None, events=None)
        self.assertEqual(item.cancelled_step_count, 0)
        self.assertEqual(item.requested_models, [])


class TaskViewFromTaskTests(unittest.TestCase):
    """Tests for TaskView.from_task factory (extends OrchestrateResponse)."""

    def test_prompt_preserved(self) -> None:
        task = _task(prompt="What is 2+2?")
        view = TaskView.from_task(task)
        self.assertEqual(view.prompt, "What is 2+2?")

    def test_metadata_preserved(self) -> None:
        task = _task(metadata={"trace_id": "abc"})
        view = TaskView.from_task(task)
        self.assertEqual(view.metadata["trace_id"], "abc")

    def test_quorum_preserved(self) -> None:
        task = _task(quorum=3)
        view = TaskView.from_task(task)
        self.assertEqual(view.quorum, 3)

    def test_cancel_on_quorum_preserved(self) -> None:
        task = _task(cancel_on_quorum=False)
        view = TaskView.from_task(task)
        self.assertFalse(view.cancel_on_quorum)

    def test_retry_of_task_id_preserved(self) -> None:
        task = _task(retry_of_task_id="parent-task")
        view = TaskView.from_task(task)
        self.assertEqual(view.retry_of_task_id, "parent-task")

    def test_retry_of_task_id_none_by_default(self) -> None:
        task = _task()
        view = TaskView.from_task(task)
        self.assertIsNone(view.retry_of_task_id)

    def test_steps_serialized_from_records(self) -> None:
        task = _task()
        step = _step(step_index=1, output_text="out")
        view = TaskView.from_task(task, steps=[step])
        self.assertEqual(len(view.steps), 1)
        self.assertEqual(view.steps[0].step_index, 1)
        self.assertEqual(view.steps[0].output_text, "out")

    def test_events_serialized_from_records(self) -> None:
        task = _task()
        ev = _event(seq=1, payload={"x": 1})
        view = TaskView.from_task(task, events=[ev])
        self.assertEqual(len(view.events), 1)
        self.assertEqual(view.events[0].sequence_no, 1)
        self.assertEqual(view.events[0].payload["x"], 1)

    def test_winning_step_index_from_terminal_event(self) -> None:
        task = _task()
        ev = _event(
            event_type=EventType.TASK_COMPLETED,
            payload={"winning_step_index": 3},
        )
        view = TaskView.from_task(task, events=[ev])
        self.assertEqual(view.winning_step_index, 3)

    def test_cancelled_steps_from_terminal_event(self) -> None:
        task = _task()
        ev = _event(
            event_type=EventType.TASK_COMPLETED,
            payload={"cancelled_steps": [2, 4]},
        )
        view = TaskView.from_task(task, events=[ev])
        self.assertEqual(view.cancelled_steps, [2, 4])

    def test_execution_details_from_terminal_event(self) -> None:
        task = _task()
        ev = _event(
            event_type=EventType.TASK_COMPLETED,
            payload={"details": {"quorum": 2}},
        )
        view = TaskView.from_task(task, events=[ev])
        self.assertEqual(view.execution_details["quorum"], 2)

    def test_empty_steps_and_events(self) -> None:
        task = _task()
        view = TaskView.from_task(task, steps=[], events=[])
        self.assertEqual(view.steps, [])
        self.assertEqual(view.events, [])

    def test_none_steps_and_events_handled(self) -> None:
        task = _task()
        view = TaskView.from_task(task, steps=None, events=None)
        self.assertEqual(view.steps, [])
        self.assertEqual(view.events, [])


class TaskEventViewFromRecordTests(unittest.TestCase):
    def test_event_id_preserved(self) -> None:
        rec = _event(seq=5)
        view = TaskEventView.from_record(rec)
        self.assertEqual(view.event_id, "ev-5")

    def test_sequence_no_preserved(self) -> None:
        rec = _event(seq=7)
        view = TaskEventView.from_record(rec)
        self.assertEqual(view.sequence_no, 7)

    def test_event_type_preserved(self) -> None:
        rec = _event(event_type=EventType.TASK_ACCEPTED)
        view = TaskEventView.from_record(rec)
        self.assertEqual(view.event_type, EventType.TASK_ACCEPTED.value)

    def test_payload_preserved(self) -> None:
        rec = _event(payload={"key": "value"})
        view = TaskEventView.from_record(rec)
        self.assertEqual(view.payload["key"], "value")

    def test_created_at_preserved(self) -> None:
        rec = _event()
        view = TaskEventView.from_record(rec)
        self.assertEqual(view.created_at, _NOW)


if __name__ == "__main__":
    unittest.main()
