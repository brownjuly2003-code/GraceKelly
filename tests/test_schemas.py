from __future__ import annotations

import unittest

from pydantic import ValidationError

from gracekelly.core.contracts import MergeStrategy, StepStatus
from gracekelly.schemas import OrchestrateRequest, TaskStepView
from gracekelly.storage.base import TaskStepRecord


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
