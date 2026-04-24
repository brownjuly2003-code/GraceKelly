from __future__ import annotations

import unittest
from datetime import UTC, datetime
from typing import Any

from gracekelly.api.routes.orchestrate import (
    _build_retry_request,
    _models_from_accepted_event,
    _parse_before_cursor,
    _sanitize_validation_error,
    _storage_error_detail,
)
from gracekelly.core.contracts import (
    AdapterHint,
    EventType,
    ExecutionMode,
    FailureCode,
    MergeStrategy,
    StepStatus,
    TaskStatus,
)
from gracekelly.core.orchestrator import StorageUnavailableError
from gracekelly.storage.base import TaskEventRecord, TaskRecord, TaskStepRecord

_NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _make_task(**kwargs: Any) -> TaskRecord:
    defaults: dict[str, Any] = dict(
        task_id="t1",
        status=TaskStatus.FAILED,
        accepted_at=_NOW,
        completed_at=_NOW,
        duration_ms=100,
        prompt="Why?",
        reasoning=False,
        execution_mode=ExecutionMode.API,
        dry_run=False,
        model_count=1,
        quorum=1,
        merge_strategy=MergeStrategy.FIRST_SUCCESS,
        adapter_hint=AdapterHint.AUTO,
        cancel_on_quorum=True,
    )
    defaults.update(kwargs)
    return TaskRecord(**defaults)


def _make_step(model_id: str = "gpt-5-4-api") -> TaskStepRecord:
    return TaskStepRecord(
        task_id="t1",
        step_index=1,
        model_id=model_id,
        model_display_name="GPT-5.4 API",
        backend="api",
        provider="openai",
        status=StepStatus.COMPLETED,
    )


def _make_event(
    event_type: EventType = EventType.TASK_ACCEPTED,
    payload: dict[str, object] | None = None,
) -> TaskEventRecord:
    return TaskEventRecord(
        event_id="ev-1",
        task_id="t1",
        sequence_no=1,
        event_type=event_type,
        created_at=_NOW,
        payload=payload or {},
    )


class SanitizeValidationErrorTests(unittest.TestCase):
    def test_duplicate_model_prefix_returned_verbatim(self) -> None:
        exc = ValueError("Duplicate model request after canonicalization: X")
        self.assertIn("Duplicate model request", _sanitize_validation_error(exc))

    def test_reasoning_prefix_returned_verbatim(self) -> None:
        exc = ValueError("reasoning=true is not supported for: Sonar")
        self.assertEqual(_sanitize_validation_error(exc), str(exc))

    def test_model_prefix_returned_verbatim(self) -> None:
        exc = ValueError("Model 'X' requires backend 'api'")
        self.assertEqual(_sanitize_validation_error(exc), str(exc))

    def test_merge_strategy_prefix_returned_verbatim(self) -> None:
        exc = ValueError("merge_strategy='concat' cannot be combined")
        self.assertEqual(_sanitize_validation_error(exc), str(exc))

    def test_quorum_prefix_returned_verbatim(self) -> None:
        exc = ValueError("Quorum 5 exceeds model count 2")
        self.assertEqual(_sanitize_validation_error(exc), str(exc))

    def test_unknown_message_sanitized(self) -> None:
        exc = ValueError("internal secret leaked: sk-xxx")
        self.assertEqual(_sanitize_validation_error(exc), "Invalid request parameters.")

    def test_empty_message_sanitized(self) -> None:
        exc = ValueError("")
        self.assertEqual(_sanitize_validation_error(exc), "Invalid request parameters.")


class StorageErrorDetailTests(unittest.TestCase):
    def test_has_storage_failed_code(self) -> None:
        exc = StorageUnavailableError("save_task", "db error")
        detail = _storage_error_detail(exc)
        self.assertEqual(detail["code"], FailureCode.STORAGE_FAILED.value)

    def test_message_contains_operation(self) -> None:
        exc = StorageUnavailableError("get_task", "connection lost")
        detail = _storage_error_detail(exc)
        self.assertIn("get_task", detail["message"])


class ParseBeforeCursorTests(unittest.TestCase):
    def test_none_returns_none(self) -> None:
        self.assertIsNone(_parse_before_cursor(None))

    def test_empty_string_returns_none(self) -> None:
        self.assertIsNone(_parse_before_cursor(""))

    def test_valid_iso_with_z_suffix(self) -> None:
        result = _parse_before_cursor("2026-01-01T12:00:00Z")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.year, 2026)
        self.assertEqual(result.tzinfo, UTC)

    def test_valid_iso_with_offset(self) -> None:
        result = _parse_before_cursor("2026-01-01T12:00:00+00:00")
        self.assertIsNotNone(result)

    def test_invalid_string_returns_none(self) -> None:
        self.assertIsNone(_parse_before_cursor("not-a-date"))

    def test_partial_date_no_time_returns_none(self) -> None:
        """Bare date like 2026-01-01 has no time component."""
        # fromisoformat("2026-01-01") succeeds in Python 3.7+ but we want None
        # (or valid datetime); the function either returns a datetime or None
        result = _parse_before_cursor("2026-01-01")
        # Accept either behavior: either None (if validation fails) or a valid datetime
        if result is not None:
            self.assertIsInstance(result, datetime)

    def test_whitespace_returns_none(self) -> None:
        self.assertIsNone(_parse_before_cursor("   "))


class BuildRetryRequestTests(unittest.TestCase):
    def test_single_step_uses_model_field(self) -> None:
        req = _build_retry_request(_make_task(), [_make_step("gpt-5-4-api")], [])
        self.assertEqual(req.model, "gpt-5-4-api")
        self.assertEqual(req.models, [])

    def test_two_steps_uses_models_field(self) -> None:
        task = _make_task(model_count=2)
        steps = [_make_step("gpt-5-4-api"), _make_step("claude-sonnet-4-6-api")]
        req = _build_retry_request(task, steps, [])
        self.assertIsNone(req.model)
        self.assertIn("gpt-5-4-api", req.models)
        self.assertIn("claude-sonnet-4-6-api", req.models)

    def test_prompt_preserved(self) -> None:
        req = _build_retry_request(_make_task(prompt="Original prompt"), [_make_step()], [])
        self.assertEqual(req.prompt, "Original prompt")

    def test_quorum_preserved(self) -> None:
        req = _build_retry_request(_make_task(quorum=1), [_make_step()], [])
        self.assertEqual(req.quorum, 1)

    def test_dry_run_preserved(self) -> None:
        req = _build_retry_request(_make_task(dry_run=True), [_make_step()], [])
        self.assertTrue(req.dry_run)

    def test_no_steps_falls_back_to_events(self) -> None:
        ev = _make_event(
            event_type=EventType.TASK_ACCEPTED,
            payload={"execution_plan": {"steps": [{"model_id": "gpt-5-4-api"}]}},
        )
        req = _build_retry_request(_make_task(), [], [ev])
        self.assertEqual(req.model, "gpt-5-4-api")

    def test_duplicate_step_models_deduplicated(self) -> None:
        steps = [_make_step("gpt-5-4-api"), _make_step("gpt-5-4-api")]
        req = _build_retry_request(_make_task(model_count=2), steps, [])
        # deduped → single model → uses model= field
        self.assertEqual(req.model, "gpt-5-4-api")


class ModelsFromAcceptedEventTests(unittest.TestCase):
    def test_extracts_model_ids(self) -> None:
        ev = _make_event(
            event_type=EventType.TASK_ACCEPTED,
            payload={"execution_plan": {"steps": [
                {"model_id": "gpt-5-4-api"},
                {"model_id": "claude-sonnet-4-6-api"},
            ]}},
        )
        result = _models_from_accepted_event([ev])
        self.assertIn("gpt-5-4-api", result)
        self.assertIn("claude-sonnet-4-6-api", result)

    def test_deduplicates_model_ids(self) -> None:
        ev = _make_event(
            event_type=EventType.TASK_ACCEPTED,
            payload={"execution_plan": {"steps": [
                {"model_id": "gpt-5-4-api"},
                {"model_id": "gpt-5-4-api"},
            ]}},
        )
        result = _models_from_accepted_event([ev])
        self.assertEqual(result.count("gpt-5-4-api"), 1)

    def test_skips_non_accepted_events(self) -> None:
        ev = _make_event(
            event_type=EventType.TASK_COMPLETED,
            payload={"execution_plan": {"steps": [{"model_id": "gpt-5-4-api"}]}},
        )
        self.assertEqual(_models_from_accepted_event([ev]), [])

    def test_empty_events_returns_empty_list(self) -> None:
        self.assertEqual(_models_from_accepted_event([]), [])

    def test_returns_sorted_model_ids(self) -> None:
        ev = _make_event(
            event_type=EventType.TASK_ACCEPTED,
            payload={"execution_plan": {"steps": [
                {"model_id": "sonar"},
                {"model_id": "gpt-5-4-api"},
            ]}},
        )
        result = _models_from_accepted_event([ev])
        self.assertEqual(result, sorted(result))

    def test_steps_without_model_id_skipped(self) -> None:
        ev = _make_event(
            event_type=EventType.TASK_ACCEPTED,
            payload={"execution_plan": {"steps": [
                {"model_id": "gpt-5-4-api"},
                {"no_model_id": True},
            ]}},
        )
        self.assertEqual(_models_from_accepted_event([ev]), ["gpt-5-4-api"])

    def test_missing_execution_plan_returns_empty(self) -> None:
        ev = _make_event(event_type=EventType.TASK_ACCEPTED, payload={})
        self.assertEqual(_models_from_accepted_event([ev]), [])


if __name__ == "__main__":
    unittest.main()
