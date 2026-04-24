from __future__ import annotations

import unittest
from datetime import UTC, datetime
from typing import Any

from gracekelly.core.contracts import (
    AdapterHint,
    EventType,
    ExecutionMode,
    MergeStrategy,
    StepStatus,
    TaskStatus,
)
from gracekelly.schemas import (
    _resolve_adapter_name,
    _resolve_cancel_summary,
    _resolve_requested_models,
    _resolve_terminal_summary,
    _resolve_winning_model,
)
from gracekelly.storage.base import TaskEventRecord, TaskRecord, TaskStepRecord

_NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _task(
    *,
    dry_run: bool = False,
    status: TaskStatus = TaskStatus.COMPLETED,
    merge_strategy: MergeStrategy = MergeStrategy.FIRST_SUCCESS,
    model_count: int = 1,
) -> TaskRecord:
    return TaskRecord(
        task_id="t1",
        status=status,
        accepted_at=_NOW,
        completed_at=_NOW,
        duration_ms=100,
        prompt="Q",
        reasoning=False,
        execution_mode=ExecutionMode.API,
        dry_run=dry_run,
        model_count=model_count,
        quorum=1,
        merge_strategy=merge_strategy,
        adapter_hint=AdapterHint.AUTO,
        cancel_on_quorum=True,
    )


def _step(
    *,
    model_id: str = "sonar",
    display: str = "Sonar",
    backend: str = "api",
    provider: str = "perplexity",
    status: StepStatus = StepStatus.COMPLETED,
) -> TaskStepRecord:
    return TaskStepRecord(
        task_id="t1",
        step_index=0,
        model_id=model_id,
        model_display_name=display,
        backend=backend,
        provider=provider,
        status=status,
    )


def _event(
    event_type: EventType,
    *,
    payload: dict[str, Any] | None = None,
    seq: int = 1,
) -> TaskEventRecord:
    return TaskEventRecord(
        event_id=f"ev-{seq}",
        task_id="t1",
        sequence_no=seq,
        event_type=event_type,
        created_at=_NOW,
        payload=payload or {},
    )


class ResolveAdapterNameTests(unittest.TestCase):
    def test_dry_run_returns_dry_run_string(self) -> None:
        task = _task(dry_run=True)
        self.assertEqual(_resolve_adapter_name(task, []), "dry-run")

    def test_no_steps_returns_unknown(self) -> None:
        task = _task(dry_run=False)
        self.assertEqual(_resolve_adapter_name(task, []), "unknown")

    def test_single_completed_step_returns_backend_provider(self) -> None:
        task = _task()
        steps = [_step(backend="api", provider="openai", status=StepStatus.COMPLETED)]
        self.assertEqual(_resolve_adapter_name(task, steps), "api.openai")

    def test_multiple_steps_same_backend_returns_that_backend(self) -> None:
        task = _task()
        steps = [
            _step(backend="api", provider="perplexity", status=StepStatus.COMPLETED),
            _step(backend="api", provider="perplexity", status=StepStatus.CANCELLED),
        ]
        self.assertEqual(_resolve_adapter_name(task, steps), "api.perplexity")

    def test_mixed_backends_returns_multi(self) -> None:
        task = _task()
        steps = [
            _step(backend="api", provider="openai", status=StepStatus.COMPLETED),
            _step(backend="browser", provider="perplexity", status=StepStatus.COMPLETED),
        ]
        self.assertEqual(_resolve_adapter_name(task, steps), "multi")

    def test_no_completed_steps_falls_back_to_failed(self) -> None:
        """When no COMPLETED steps, uses FAILED steps instead."""
        task = _task()
        steps = [_step(backend="api", provider="openai", status=StepStatus.FAILED)]
        self.assertEqual(_resolve_adapter_name(task, steps), "api.openai")

    def test_no_completed_or_failed_uses_all_steps(self) -> None:
        """When only CANCELLED steps exist, uses them."""
        task = _task()
        steps = [_step(backend="api", provider="openai", status=StepStatus.CANCELLED)]
        self.assertEqual(_resolve_adapter_name(task, steps), "api.openai")


class ResolveRequestedModelsTests(unittest.TestCase):
    def test_steps_present_models_from_steps(self) -> None:
        steps = [
            _step(model_id="sonar", display="Sonar"),
            _step(model_id="gpt-4o", display="GPT-4o"),
        ]
        result = _resolve_requested_models(steps, [])
        ids = [m.id for m in result]
        self.assertEqual(ids, ["sonar", "gpt-4o"])

    def test_no_steps_uses_accepted_event_plan(self) -> None:
        plan_steps = [
            {"model_id": "sonar", "display_name": "Sonar"},
            {"model_id": "gpt-4o", "display_name": "GPT-4o"},
        ]
        ev = _event(
            EventType.TASK_ACCEPTED,
            payload={"execution_plan": {"steps": plan_steps}},
        )
        result = _resolve_requested_models([], [ev])
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].id, "sonar")

    def test_no_steps_no_accepted_event_returns_empty(self) -> None:
        ev = _event(EventType.TASK_COMPLETED)
        result = _resolve_requested_models([], [ev])
        self.assertEqual(result, [])

    def test_no_steps_no_events_returns_empty(self) -> None:
        result = _resolve_requested_models([], [])
        self.assertEqual(result, [])

    def test_accepted_event_with_non_list_steps_returns_empty(self) -> None:
        ev = _event(
            EventType.TASK_ACCEPTED,
            payload={"execution_plan": {"steps": "not-a-list"}},
        )
        result = _resolve_requested_models([], [ev])
        self.assertEqual(result, [])

    def test_accepted_event_plan_step_missing_keys_skipped(self) -> None:
        """Steps missing model_id or display_name are excluded."""
        plan_steps = [
            {"model_id": "sonar", "display_name": "Sonar"},
            {"only_something_else": True},
        ]
        ev = _event(
            EventType.TASK_ACCEPTED,
            payload={"execution_plan": {"steps": plan_steps}},
        )
        result = _resolve_requested_models([], [ev])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].id, "sonar")


class ResolveWinningModelTests(unittest.TestCase):
    def test_dry_run_returns_none(self) -> None:
        task = _task(dry_run=True, status=TaskStatus.COMPLETED)
        steps = [_step(status=StepStatus.COMPLETED)]
        self.assertIsNone(_resolve_winning_model(task, steps))

    def test_not_completed_returns_none(self) -> None:
        task = _task(status=TaskStatus.FAILED)
        steps = [_step(status=StepStatus.COMPLETED)]
        self.assertIsNone(_resolve_winning_model(task, steps))

    def test_non_first_success_multi_model_returns_none(self) -> None:
        task = _task(
            status=TaskStatus.COMPLETED,
            merge_strategy=MergeStrategy.CONCAT,
            model_count=3,
        )
        steps = [_step(status=StepStatus.COMPLETED)]
        self.assertIsNone(_resolve_winning_model(task, steps))

    def test_completed_first_success_returns_first_completed_step(self) -> None:
        task = _task(
            status=TaskStatus.COMPLETED,
            merge_strategy=MergeStrategy.FIRST_SUCCESS,
        )
        steps = [_step(model_id="sonar", display="Sonar", status=StepStatus.COMPLETED)]
        result = _resolve_winning_model(task, steps)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.id, "sonar")

    def test_completed_no_completed_steps_returns_none(self) -> None:
        task = _task(status=TaskStatus.COMPLETED)
        steps = [_step(status=StepStatus.FAILED)]
        self.assertIsNone(_resolve_winning_model(task, steps))

    def test_single_model_concat_strategy_returns_winner(self) -> None:
        """model_count=1 with CONCAT strategy should still return a winner (condition is model_count > 1)."""
        task = _task(
            status=TaskStatus.COMPLETED,
            merge_strategy=MergeStrategy.CONCAT,
            model_count=1,
        )
        steps = [_step(status=StepStatus.COMPLETED)]
        self.assertIsNotNone(_resolve_winning_model(task, steps))


class ResolveCancelSummaryTests(unittest.TestCase):
    def test_dry_run_returns_zero_none(self) -> None:
        task = _task(dry_run=True, status=TaskStatus.COMPLETED)
        count, reason = _resolve_cancel_summary(task, [], [])
        self.assertEqual(count, 0)
        self.assertIsNone(reason)

    def test_final_event_with_cancelled_steps(self) -> None:
        task = _task(status=TaskStatus.COMPLETED)
        ev = _event(
            EventType.TASK_COMPLETED,
            payload={"cancelled_steps": [1, 2], "cancel_reason": "quorum_reached"},
        )
        count, reason = _resolve_cancel_summary(task, [], [ev])
        self.assertEqual(count, 2)
        self.assertEqual(reason, "quorum_reached")

    def test_final_event_missing_returns_step_count_fallback(self) -> None:
        task = _task(status=TaskStatus.COMPLETED)
        steps = [
            _step(status=StepStatus.CANCELLED),
            _step(status=StepStatus.COMPLETED),
        ]
        count, reason = _resolve_cancel_summary(task, steps, [])
        self.assertEqual(count, 1)
        # completed task with cancelled steps → quorum_reached
        self.assertEqual(reason, "quorum_reached")

    def test_no_cancelled_steps_returns_zero_none(self) -> None:
        task = _task(status=TaskStatus.COMPLETED)
        steps = [_step(status=StepStatus.COMPLETED)]
        count, reason = _resolve_cancel_summary(task, steps, [])
        self.assertEqual(count, 0)
        self.assertIsNone(reason)

    def test_failed_task_no_cancel_reason(self) -> None:
        task = _task(status=TaskStatus.FAILED)
        steps = [_step(status=StepStatus.CANCELLED)]
        count, reason = _resolve_cancel_summary(task, steps, [])
        self.assertEqual(count, 1)
        # failed task with cancelled steps: cancel_reason stays None
        self.assertIsNone(reason)

    def test_event_cancel_reason_non_string_returns_none(self) -> None:
        task = _task(status=TaskStatus.COMPLETED)
        ev = _event(
            EventType.TASK_COMPLETED,
            payload={"cancelled_steps": [], "cancel_reason": 42},
        )
        _, reason = _resolve_cancel_summary(task, [], [ev])
        self.assertIsNone(reason)


class ResolveTerminalSummaryTests(unittest.TestCase):
    def test_no_terminal_event_returns_defaults(self) -> None:
        ev = _event(EventType.TASK_ACCEPTED)
        result = _resolve_terminal_summary([ev])
        self.assertIsNone(result["winning_step_index"])
        self.assertEqual(result["cancelled_steps"], [])
        self.assertIsNone(result["cancel_reason"])
        self.assertEqual(result["execution_details"], {})

    def test_empty_events_returns_defaults(self) -> None:
        result = _resolve_terminal_summary([])
        self.assertIsNone(result["winning_step_index"])
        self.assertEqual(result["cancelled_steps"], [])

    def test_completed_event_extracts_winning_step_index(self) -> None:
        ev = _event(
            EventType.TASK_COMPLETED,
            payload={"winning_step_index": 2, "cancelled_steps": [], "details": {}},
        )
        result = _resolve_terminal_summary([ev])
        self.assertEqual(result["winning_step_index"], 2)

    def test_non_list_cancelled_steps_returns_empty_list(self) -> None:
        ev = _event(
            EventType.TASK_COMPLETED,
            payload={"cancelled_steps": "not-a-list"},
        )
        result = _resolve_terminal_summary([ev])
        self.assertEqual(result["cancelled_steps"], [])

    def test_non_dict_details_returns_empty_dict(self) -> None:
        ev = _event(
            EventType.TASK_COMPLETED,
            payload={"details": "not-a-dict"},
        )
        result = _resolve_terminal_summary([ev])
        self.assertEqual(result["execution_details"], {})

    def test_non_string_cancel_reason_returns_none(self) -> None:
        ev = _event(
            EventType.TASK_COMPLETED,
            payload={"cancel_reason": 999},
        )
        result = _resolve_terminal_summary([ev])
        self.assertIsNone(result["cancel_reason"])

    def test_uses_last_terminal_event(self) -> None:
        """If multiple terminal events exist, the last one wins."""
        ev1 = _event(
            EventType.TASK_COMPLETED,
            payload={"winning_step_index": 1},
            seq=1,
        )
        ev2 = _event(
            EventType.TASK_CANCELLED,
            payload={"winning_step_index": 5},
            seq=2,
        )
        result = _resolve_terminal_summary([ev1, ev2])
        self.assertEqual(result["winning_step_index"], 5)


if __name__ == "__main__":
    unittest.main()
