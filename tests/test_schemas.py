from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pydantic import ValidationError

from gracekelly.core.contracts import (
    AdapterHint,
    EventType,
    ExecutionMode,
    FailureCode,
    MergeStrategy,
    StepStatus,
    TaskStatus,
)
from gracekelly.schemas import (
    OrchestrateRequest,
    OrchestrateResponse,
    TaskEventView,
    TaskListItem,
    TaskStepView,
    TaskView,
    _resolve_adapter_name,
    _resolve_cancel_summary,
    _resolve_requested_models,
    _resolve_terminal_summary,
    _resolve_winning_model,
)
from gracekelly.storage.base import TaskEventRecord, TaskRecord, TaskStepRecord


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _task(
    task_id: str = "t1",
    status: TaskStatus = TaskStatus.COMPLETED,
    dry_run: bool = False,
    merge_strategy: MergeStrategy = MergeStrategy.FIRST_SUCCESS,
    model_count: int = 1,
    failure_code: FailureCode | None = None,
    output_text: str | None = "output",
) -> TaskRecord:
    return TaskRecord(
        task_id=task_id,
        status=status,
        accepted_at=_now(),
        completed_at=_now(),
        duration_ms=100,
        prompt="test prompt",
        reasoning=False,
        execution_mode=ExecutionMode.API,
        dry_run=dry_run,
        model_count=model_count,
        quorum=1,
        merge_strategy=merge_strategy,
        adapter_hint=AdapterHint.API,
        cancel_on_quorum=False,
        failure_code=failure_code,
        output_text=output_text,
    )


def _step(
    task_id: str = "t1",
    step_index: int = 1,
    model_id: str = "mistral-small",
    display_name: str = "Mistral Small",
    backend: str = "api",
    provider: str = "mistral",
    status: StepStatus = StepStatus.COMPLETED,
) -> TaskStepRecord:
    return TaskStepRecord(
        task_id=task_id,
        step_index=step_index,
        model_id=model_id,
        model_display_name=display_name,
        backend=backend,
        provider=provider,
        status=status,
    )


def _event(
    task_id: str = "t1",
    event_type: EventType = EventType.TASK_ACCEPTED,
    seq: int = 1,
    payload: dict | None = None,
) -> TaskEventRecord:
    return TaskEventRecord(
        event_id=f"e-{seq}",
        task_id=task_id,
        sequence_no=seq,
        event_type=event_type,
        created_at=_now(),
        payload=payload or {},
    )


class OrchestrateRequestValidationTests(unittest.TestCase):
    def _valid_payload(self, **overrides) -> dict:
        base = {"prompt": "Hello", "model": "Mistral", "dry_run": True}
        base.update(overrides)
        return base

    def test_valid_single_model(self) -> None:
        req = OrchestrateRequest(**self._valid_payload())
        self.assertEqual(req.requested_model_names(), ["Mistral"])

    def test_valid_multiple_models(self) -> None:
        req = OrchestrateRequest(**self._valid_payload(model=None, models=["Mistral", "GPT-5.4"]))
        self.assertEqual(req.requested_model_names(), ["Mistral", "GPT-5.4"])

    def test_neither_model_nor_models_raises(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            OrchestrateRequest(**self._valid_payload(model=None, models=[]))
        self.assertIn("Either", str(ctx.exception))

    def test_both_model_and_models_raises(self) -> None:
        with self.assertRaises(ValidationError):
            OrchestrateRequest(**self._valid_payload(model="Mistral", models=["GPT-5.4"]))

    def test_empty_prompt_raises(self) -> None:
        with self.assertRaises(ValidationError):
            OrchestrateRequest(**self._valid_payload(prompt=""))

    def test_prompt_max_length(self) -> None:
        with self.assertRaises(ValidationError):
            OrchestrateRequest(**self._valid_payload(prompt="x" * 40001))

    def test_prompt_at_max_length_ok(self) -> None:
        req = OrchestrateRequest(**self._valid_payload(prompt="x" * 40000))
        self.assertEqual(len(req.prompt), 40000)

    def test_model_name_max_length(self) -> None:
        with self.assertRaises(ValidationError):
            OrchestrateRequest(**self._valid_payload(model="x" * 121))

    def test_models_max_count(self) -> None:
        with self.assertRaises(ValidationError):
            OrchestrateRequest(**self._valid_payload(model=None, models=["m"] * 9))

    def test_models_at_max_count_ok(self) -> None:
        req = OrchestrateRequest(**self._valid_payload(model=None, models=["m"] * 8))
        self.assertEqual(len(req.requested_model_names()), 8)

    def test_quorum_below_range(self) -> None:
        with self.assertRaises(ValidationError):
            OrchestrateRequest(**self._valid_payload(quorum=0))

    def test_quorum_above_range(self) -> None:
        with self.assertRaises(ValidationError):
            OrchestrateRequest(**self._valid_payload(quorum=9))

    def test_quorum_boundaries_ok(self) -> None:
        for q in (1, 8):
            req = OrchestrateRequest(**self._valid_payload(quorum=q))
            self.assertEqual(req.quorum, q)

    def test_non_serializable_metadata_raises(self) -> None:
        with self.assertRaises(ValidationError) as ctx:
            OrchestrateRequest(**self._valid_payload(metadata={"bad": object()}))
        self.assertIn("metadata", str(ctx.exception).lower())

    def test_serializable_metadata_ok(self) -> None:
        req = OrchestrateRequest(**self._valid_payload(metadata={"trace_id": "abc-123", "count": 42}))
        self.assertEqual(req.metadata["trace_id"], "abc-123")

    def test_invalid_merge_strategy_raises(self) -> None:
        with self.assertRaises(ValidationError):
            OrchestrateRequest(**self._valid_payload(merge_strategy="unknown"))

    def test_defaults(self) -> None:
        req = OrchestrateRequest(**self._valid_payload())
        self.assertEqual(req.quorum, 1)
        self.assertEqual(req.merge_strategy, MergeStrategy.FIRST_SUCCESS)
        self.assertTrue(req.cancel_on_quorum)
        self.assertFalse(req.reasoning)
        self.assertTrue(req.dry_run)

    def test_orchestrate_request_context_task_id_defaults_to_none(self) -> None:
        req = OrchestrateRequest(prompt="hello", model="dry-run")
        self.assertIsNone(req.context_task_id)

    def test_orchestrate_request_context_task_id_accepted(self) -> None:
        req = OrchestrateRequest(prompt="hello", model="dry-run", context_task_id="abc-123")
        self.assertEqual(req.context_task_id, "abc-123")

    def test_orchestrate_request_context_task_id_max_length_enforced(self) -> None:
        with self.assertRaises(ValidationError):
            OrchestrateRequest(prompt="hello", model="dry-run", context_task_id="x" * 37)


class TaskStepViewTruncationTests(unittest.TestCase):
    def _step_record(self, output_text: str | None = None) -> TaskStepRecord:
        return TaskStepRecord(
            task_id="t1",
            step_index=1,
            model_id="m1",
            model_display_name="Model 1",
            backend="api",
            provider="test",
            status=StepStatus.COMPLETED,
            output_text=output_text,
        )

    def test_short_output_not_truncated(self) -> None:
        view = TaskStepView.from_record(self._step_record("short"))
        self.assertEqual(view.output_text, "short")
        self.assertFalse(view.output_truncated)

    def test_none_output(self) -> None:
        view = TaskStepView.from_record(self._step_record(None))
        self.assertIsNone(view.output_text)
        self.assertFalse(view.output_truncated)

    def test_long_output_truncated(self) -> None:
        view = TaskStepView.from_record(self._step_record("x" * 25000))
        self.assertEqual(len(view.output_text), 20000)
        self.assertTrue(view.output_truncated)

    def test_exact_boundary_not_truncated(self) -> None:
        view = TaskStepView.from_record(self._step_record("x" * 20000))
        self.assertEqual(len(view.output_text), 20000)
        self.assertFalse(view.output_truncated)

    def test_custom_max_length(self) -> None:
        view = TaskStepView.from_record(self._step_record("x" * 100), max_output_length=50)
        self.assertEqual(len(view.output_text), 50)
        self.assertTrue(view.output_truncated)


class OrchestrateResponseFromTaskTests(unittest.TestCase):
    def test_dry_run_adapter_name_is_dry_run(self) -> None:
        task = _task(dry_run=True, output_text=None)
        resp = OrchestrateResponse.from_task(task, [], [])
        self.assertEqual(resp.adapter_name, "dry-run")

    def test_no_steps_adapter_name_is_unknown(self) -> None:
        task = _task(dry_run=False)
        resp = OrchestrateResponse.from_task(task, [], [])
        self.assertEqual(resp.adapter_name, "unknown")

    def test_single_completed_step_adapter_name(self) -> None:
        task = _task()
        resp = OrchestrateResponse.from_task(task, [_step()], [])
        self.assertEqual(resp.adapter_name, "api.mistral")

    def test_multiple_backends_returns_multi(self) -> None:
        task = _task(model_count=2)
        steps = [
            _step(step_index=1, backend="api", provider="mistral"),
            _step(step_index=2, backend="browser", provider="perplexity"),
        ]
        resp = OrchestrateResponse.from_task(task, steps, [])
        self.assertEqual(resp.adapter_name, "multi")

    def test_winning_model_first_success_completed(self) -> None:
        task = _task()
        resp = OrchestrateResponse.from_task(task, [_step()], [])
        assert resp.model is not None
        self.assertEqual(resp.model.id, "mistral-small")

    def test_winning_model_none_on_dry_run(self) -> None:
        task = _task(dry_run=True, output_text=None)
        resp = OrchestrateResponse.from_task(task, [_step()], [])
        self.assertIsNone(resp.model)

    def test_winning_model_none_on_failed_task(self) -> None:
        task = _task(status=TaskStatus.FAILED, output_text=None,
                     failure_code=FailureCode.TIMEOUT)
        resp = OrchestrateResponse.from_task(task, [_step(status=StepStatus.FAILED)], [])
        self.assertIsNone(resp.model)

    def test_requested_models_from_steps(self) -> None:
        task = _task()
        resp = OrchestrateResponse.from_task(task, [_step()], [])
        self.assertEqual(len(resp.requested_models), 1)
        self.assertEqual(resp.requested_models[0].id, "mistral-small")

    def test_requested_models_from_events_when_no_steps(self) -> None:
        task = _task(dry_run=True, output_text=None)
        accepted = _event(event_type=EventType.TASK_ACCEPTED, payload={
            "execution_plan": {
                "steps": [
                    {"model_id": "m1", "display_name": "Model 1"},
                ]
            }
        })
        resp = OrchestrateResponse.from_task(task, [], [accepted])
        self.assertEqual(len(resp.requested_models), 1)
        self.assertEqual(resp.requested_models[0].id, "m1")

    def test_requested_models_override(self) -> None:
        from gracekelly.schemas import ModelView
        task = _task()
        override = [ModelView(id="override-id", display_name="Override")]
        resp = OrchestrateResponse.from_task(task, [_step()], [], requested_models_override=override)
        self.assertEqual(resp.requested_models[0].id, "override-id")


class TaskListItemFromTaskTests(unittest.TestCase):
    def test_dry_run_cancelled_count_zero(self) -> None:
        task = _task(dry_run=True, output_text=None)
        item = TaskListItem.from_task(task, [], [])
        self.assertEqual(item.cancelled_step_count, 0)
        self.assertIsNone(item.cancel_reason)

    def test_cancelled_steps_from_terminal_event(self) -> None:
        task = _task(status=TaskStatus.COMPLETED)
        terminal = _event(
            event_type=EventType.TASK_COMPLETED,
            seq=3,
            payload={"cancelled_steps": [2], "cancel_reason": "quorum_reached"},
        )
        item = TaskListItem.from_task(task, [_step()], [terminal])
        self.assertEqual(item.cancelled_step_count, 1)
        self.assertEqual(item.cancel_reason, "quorum_reached")

    def test_cancelled_steps_fallback_to_step_count(self) -> None:
        task = _task(status=TaskStatus.COMPLETED, model_count=2)
        steps = [
            _step(step_index=1, status=StepStatus.COMPLETED),
            _step(step_index=2, status=StepStatus.CANCELLED),
        ]
        item = TaskListItem.from_task(task, steps, [])
        self.assertEqual(item.cancelled_step_count, 1)

    def test_task_list_item_failure_fields(self) -> None:
        task = _task(status=TaskStatus.FAILED, output_text=None,
                     failure_code=FailureCode.TIMEOUT)
        item = TaskListItem.from_task(task, [], [])
        self.assertEqual(item.failure_code, "timeout")
        self.assertIsNone(item.failure_message)


class TaskViewFromTaskTests(unittest.TestCase):
    def test_task_view_includes_prompt(self) -> None:
        task = _task()
        view = TaskView.from_task(task, [_step()], [])
        self.assertEqual(view.prompt, "test prompt")

    def test_task_view_steps_populated(self) -> None:
        task = _task()
        view = TaskView.from_task(task, [_step()], [])
        self.assertEqual(len(view.steps), 1)
        self.assertEqual(view.steps[0].model_id, "mistral-small")

    def test_task_view_events_populated(self) -> None:
        task = _task()
        events = [
            _event(event_type=EventType.TASK_ACCEPTED, seq=1),
            _event(event_type=EventType.TASK_COMPLETED, seq=2, payload={}),
        ]
        view = TaskView.from_task(task, [], events)
        self.assertEqual(len(view.events), 2)

    def test_task_view_winning_step_from_terminal_event(self) -> None:
        task = _task()
        terminal = _event(
            event_type=EventType.TASK_COMPLETED,
            seq=2,
            payload={"winning_step_index": 1, "cancelled_steps": [], "cancel_reason": None},
        )
        view = TaskView.from_task(task, [_step()], [terminal])
        self.assertEqual(view.winning_step_index, 1)

    def test_task_view_no_terminal_event_defaults(self) -> None:
        task = _task()
        view = TaskView.from_task(task, [], [])
        self.assertIsNone(view.winning_step_index)
        self.assertEqual(view.cancelled_steps, [])
        self.assertIsNone(view.cancel_reason)
        self.assertEqual(view.execution_details, {})


class TaskEventViewFromRecordTests(unittest.TestCase):
    def test_event_view_fields_match_record(self) -> None:
        ts = _now()
        record = TaskEventRecord(
            event_id="ev-1",
            task_id="t1",
            sequence_no=1,
            event_type=EventType.TASK_ACCEPTED,
            created_at=ts,
            payload={"key": "value"},
        )
        view = TaskEventView.from_record(record)
        self.assertEqual(view.event_id, "ev-1")
        self.assertEqual(view.sequence_no, 1)
        self.assertEqual(view.event_type, EventType.TASK_ACCEPTED)

    def test_event_view_payload_preserved(self) -> None:
        record = TaskEventRecord(
            event_id="ev-2",
            task_id="t1",
            sequence_no=2,
            event_type=EventType.TASK_COMPLETED,
            created_at=_now(),
            payload={"winning_step_index": 1},
        )
        view = TaskEventView.from_record(record)
        self.assertEqual(view.payload["winning_step_index"], 1)


class ResolveAdapterNameTests(unittest.TestCase):
    def test_dry_run_returns_dry_run(self) -> None:
        task = _task(dry_run=True, output_text=None)
        result = _resolve_adapter_name(task, [])
        self.assertEqual(result, "dry-run")

    def test_no_steps_returns_unknown(self) -> None:
        task = _task(dry_run=False)
        self.assertEqual(_resolve_adapter_name(task, []), "unknown")

    def test_single_completed_step_uses_backend_provider(self) -> None:
        task = _task()
        result = _resolve_adapter_name(task, [_step(backend="api", provider="mistral")])
        self.assertEqual(result, "api.mistral")

    def test_all_failed_steps_uses_failed_for_candidate(self) -> None:
        task = _task(status=TaskStatus.FAILED, output_text=None)
        step = _step(status=StepStatus.FAILED, backend="browser", provider="perplexity")
        result = _resolve_adapter_name(task, [step])
        self.assertEqual(result, "browser.perplexity")

    def test_mixed_backends_returns_multi(self) -> None:
        task = _task(model_count=2)
        steps = [
            _step(step_index=1, backend="api", provider="mistral", status=StepStatus.COMPLETED),
            _step(step_index=2, backend="browser", provider="perplexity", status=StepStatus.COMPLETED),
        ]
        self.assertEqual(_resolve_adapter_name(task, steps), "multi")


class ResolveTerminalSummaryTests(unittest.TestCase):
    def test_no_events_returns_defaults(self) -> None:
        result = _resolve_terminal_summary([])
        self.assertIsNone(result["winning_step_index"])
        self.assertEqual(result["cancelled_steps"], [])
        self.assertIsNone(result["cancel_reason"])
        self.assertEqual(result["execution_details"], {})

    def test_completed_event_extracts_fields(self) -> None:
        event = _event(
            event_type=EventType.TASK_COMPLETED,
            seq=1,
            payload={"winning_step_index": 2, "cancelled_steps": [3], "cancel_reason": "quorum_reached"},
        )
        result = _resolve_terminal_summary([event])
        self.assertEqual(result["winning_step_index"], 2)
        self.assertEqual(result["cancelled_steps"], [3])
        self.assertEqual(result["cancel_reason"], "quorum_reached")

    def test_failed_event_is_terminal(self) -> None:
        event = _event(event_type=EventType.TASK_FAILED, seq=1, payload={})
        result = _resolve_terminal_summary([event])
        self.assertIsNone(result["winning_step_index"])

    def test_non_list_cancelled_steps_normalized_to_empty(self) -> None:
        event = _event(
            event_type=EventType.TASK_COMPLETED,
            seq=1,
            payload={"cancelled_steps": "not-a-list"},
        )
        result = _resolve_terminal_summary([event])
        self.assertEqual(result["cancelled_steps"], [])

    def test_non_string_cancel_reason_normalized_to_none(self) -> None:
        event = _event(
            event_type=EventType.TASK_COMPLETED,
            seq=1,
            payload={"cancel_reason": 42},
        )
        result = _resolve_terminal_summary([event])
        self.assertIsNone(result["cancel_reason"])

    def test_non_dict_execution_details_normalized_to_empty(self) -> None:
        event = _event(
            event_type=EventType.TASK_COMPLETED,
            seq=1,
            payload={"details": ["not", "a", "dict"]},
        )
        result = _resolve_terminal_summary([event])
        self.assertEqual(result["execution_details"], {})


class ResolveCancelSummaryTests(unittest.TestCase):
    def test_dry_run_returns_zero_and_none(self) -> None:
        task = _task(dry_run=True, output_text=None)
        count, reason = _resolve_cancel_summary(task, [], [])
        self.assertEqual(count, 0)
        self.assertIsNone(reason)

    def test_terminal_event_provides_cancel_info(self) -> None:
        task = _task(status=TaskStatus.COMPLETED)
        event = _event(
            event_type=EventType.TASK_COMPLETED,
            seq=1,
            payload={"cancelled_steps": [2, 3], "cancel_reason": "quorum_reached"},
        )
        count, reason = _resolve_cancel_summary(task, [], [event])
        self.assertEqual(count, 2)
        self.assertEqual(reason, "quorum_reached")

    def test_fallback_counts_cancelled_steps_directly(self) -> None:
        task = _task(status=TaskStatus.COMPLETED, model_count=2)
        steps = [
            _step(step_index=1, status=StepStatus.COMPLETED),
            _step(step_index=2, status=StepStatus.CANCELLED),
        ]
        count, reason = _resolve_cancel_summary(task, steps, [])
        self.assertEqual(count, 1)
        self.assertEqual(reason, "quorum_reached")

    def test_cancelled_task_uses_cancelled_event_type(self) -> None:
        task = _task(status=TaskStatus.CANCELLED, output_text=None)
        event = _event(
            event_type=EventType.TASK_CANCELLED,
            seq=1,
            payload={"cancelled_steps": [1, 2], "cancel_reason": "user_cancel"},
        )
        count, reason = _resolve_cancel_summary(task, [], [event])
        self.assertEqual(count, 2)
        self.assertEqual(reason, "user_cancel")


class ResolveRequestedModelsTests(unittest.TestCase):
    def test_steps_take_priority_over_events(self) -> None:
        models = _resolve_requested_models([_step()], [])
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0].id, "mistral-small")

    def test_no_steps_falls_back_to_accepted_event(self) -> None:
        event = _event(
            event_type=EventType.TASK_ACCEPTED,
            seq=1,
            payload={"execution_plan": {"steps": [{"model_id": "m1", "display_name": "Model 1"}]}},
        )
        models = _resolve_requested_models([], [event])
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0].id, "m1")

    def test_no_steps_no_events_returns_empty(self) -> None:
        self.assertEqual(_resolve_requested_models([], []), [])

    def test_malformed_steps_in_plan_skipped(self) -> None:
        event = _event(
            event_type=EventType.TASK_ACCEPTED,
            seq=1,
            payload={"execution_plan": {"steps": [{"model_id": "m1"}, "not-a-dict"]}},
        )
        models = _resolve_requested_models([], [event])
        # only item with both model_id and display_name is valid
        self.assertEqual(len(models), 0)

    def test_non_list_steps_in_plan_returns_empty(self) -> None:
        event = _event(
            event_type=EventType.TASK_ACCEPTED,
            seq=1,
            payload={"execution_plan": {"steps": "not-a-list"}},
        )
        models = _resolve_requested_models([], [event])
        self.assertEqual(models, [])


class ResolveWinningModelTests(unittest.TestCase):
    def test_dry_run_returns_none(self) -> None:
        task = _task(dry_run=True, output_text=None)
        self.assertIsNone(_resolve_winning_model(task, [_step()]))

    def test_failed_task_returns_none(self) -> None:
        task = _task(status=TaskStatus.FAILED, output_text=None, failure_code=FailureCode.TIMEOUT)
        self.assertIsNone(_resolve_winning_model(task, [_step(status=StepStatus.FAILED)]))

    def test_concat_multi_model_returns_none(self) -> None:
        task = _task(merge_strategy=MergeStrategy.CONCAT, model_count=2)
        self.assertIsNone(_resolve_winning_model(task, [_step(), _step(step_index=2)]))

    def test_first_success_single_model_returns_winner(self) -> None:
        task = _task()
        model = _resolve_winning_model(task, [_step()])
        self.assertIsNotNone(model)
        assert model is not None
        self.assertEqual(model.id, "mistral-small")
