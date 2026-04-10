from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from gracekelly.core.adaptive_selector import ModelRecommendation, _build_reason, select_models
from gracekelly.core.model_stats import ModelPerformance
from gracekelly.core.task_classifier import TaskType


def _make_perf(
    model_id: str = "m",
    total: int = 10,
    successful: int = 9,
    failed: int = 1,
    success_rate: float = 0.9,
    avg_duration_ms: float = 150.0,
    total_duration_ms: int = 1500,
) -> ModelPerformance:
    return ModelPerformance(
        model_id=model_id,
        total_executions=total,
        successful=successful,
        failed=failed,
        success_rate=success_rate,
        avg_duration_ms=avg_duration_ms,
        total_duration_ms=total_duration_ms,
    )


class BuildReasonTests(unittest.TestCase):
    def test_includes_success_rate_as_percentage(self) -> None:
        reason = _build_reason(_make_perf(success_rate=0.9), TaskType.GENERAL)
        self.assertIn("90% success rate", reason)

    def test_includes_total_executions(self) -> None:
        reason = _build_reason(_make_perf(total=42), TaskType.GENERAL)
        self.assertIn("42 executions", reason)

    def test_includes_avg_duration_when_positive(self) -> None:
        reason = _build_reason(_make_perf(avg_duration_ms=250.0), TaskType.CODING)
        self.assertIn("250ms avg", reason)

    def test_omits_avg_duration_when_zero(self) -> None:
        reason = _build_reason(_make_perf(avg_duration_ms=0.0), TaskType.GENERAL)
        self.assertNotIn("ms avg", reason)

    def test_includes_task_type(self) -> None:
        reason = _build_reason(_make_perf(), TaskType.MATH)
        self.assertIn("task type: math", reason)

    def test_parts_joined_by_comma(self) -> None:
        reason = _build_reason(_make_perf(), TaskType.GENERAL)
        self.assertIn(", ", reason)


def _record(
    model_id: str,
    status: str,
    task_type: str | None = None,
    duration_ms: int = 100,
) -> dict[str, object]:
    record: dict[str, object] = {
        "model_id": model_id,
        "status": status,
        "duration_ms": duration_ms,
    }
    if task_type is not None:
        record["task_type"] = task_type
    return record


class AdaptiveSelectorTests(unittest.TestCase):
    def test_empty_records_returns_empty(self) -> None:
        self.assertEqual([], select_models("hello", []))

    def test_returns_top_models(self) -> None:
        records = [
            _record("model-a", "completed", "general"),
            _record("model-a", "completed", "general"),
            _record("model-a", "completed", "general"),
            _record("model-b", "completed", "general"),
            _record("model-b", "completed", "general"),
            _record("model-b", "failed", "general"),
            _record("model-c", "completed", "general"),
            _record("model-c", "failed", "general"),
            _record("model-c", "failed", "general"),
        ]

        result = select_models("hello", records)

        self.assertEqual("model-a", result[0].model_id)

    def test_max_models_limits_output(self) -> None:
        records = []
        for index in range(5):
            records.extend(
                [
                    _record(f"model-{index}", "completed", "general"),
                    _record(f"model-{index}", "completed", "general"),
                    _record(f"model-{index}", "completed", "general"),
                ]
            )

        result = select_models("hello", records, max_models=2)

        self.assertEqual(2, len(result))

    def test_min_executions_filters(self) -> None:
        records = [
            _record("model-a", "completed", "general"),
            _record("model-a", "completed", "general"),
            _record("model-a", "completed", "general"),
            _record("model-b", "completed", "general"),
        ]

        result = select_models("hello", records, min_executions=3)

        self.assertEqual(["model-a"], [item.model_id for item in result])

    def test_task_type_filters_records(self) -> None:
        records = [
            _record("coding-best", "completed", "coding"),
            _record("coding-best", "completed", "coding"),
            _record("coding-best", "completed", "coding"),
            _record("general-best", "completed", "general"),
            _record("general-best", "failed", "general"),
            _record("general-best", "failed", "general"),
        ]

        result = select_models("Write Python code", records)

        self.assertEqual("coding-best", result[0].model_id)

    def test_fallback_to_all_records(self) -> None:
        records = [
            _record("model-a", "completed", "analysis"),
            _record("model-a", "completed", "analysis"),
            _record("model-a", "completed", "analysis"),
            _record("model-b", "completed", "analysis"),
            _record("model-b", "failed", "analysis"),
            _record("model-b", "failed", "analysis"),
        ]

        result = select_models("hello", records)

        self.assertEqual("model-a", result[0].model_id)

    def test_recommendation_has_reason(self) -> None:
        records = [
            _record("model-a", "completed", "general"),
            _record("model-a", "completed", "general"),
            _record("model-a", "completed", "general"),
        ]

        result = select_models("hello", records)

        self.assertIn("success rate", result[0].reason)
        self.assertIn("executions", result[0].reason)

    def test_recommendation_is_frozen(self) -> None:
        recommendation = ModelRecommendation(
            model_id="model-a",
            score=1.0,
            reason="reason",
        )

        with self.assertRaises(FrozenInstanceError):
            setattr(recommendation, "score", 0.5)

    def test_score_is_success_rate(self) -> None:
        records = [
            _record("model-a", "completed", "general"),
            _record("model-a", "completed", "general"),
            _record("model-a", "failed", "general"),
        ]

        result = select_models("hello", records)

        self.assertEqual(0.667, result[0].score)

    def test_general_prompt_uses_all(self) -> None:
        records = [
            _record("model-a", "completed"),
            _record("model-a", "completed"),
            _record("model-a", "completed"),
        ]

        result = select_models("Hello", records)

        self.assertEqual("model-a", result[0].model_id)

    def test_coding_prompt_prefers_coding_records(self) -> None:
        records = [
            _record("coding-best", "completed", "coding"),
            _record("coding-best", "completed", "coding"),
            _record("coding-best", "completed", "coding"),
            _record("analysis-best", "completed", "analysis"),
            _record("analysis-best", "failed", "analysis"),
            _record("analysis-best", "failed", "analysis"),
        ]

        result = select_models("Write Python code", records)

        self.assertEqual("coding-best", result[0].model_id)

    def test_multiple_task_types_mixed(self) -> None:
        records = [
            _record("coding-best", "completed", "coding"),
            _record("coding-best", "completed", "coding"),
            _record("coding-best", "completed", "coding"),
            _record("math-best", "completed", "math"),
            _record("math-best", "failed", "math"),
            _record("math-best", "failed", "math"),
            _record("general-best", "completed", "general"),
            _record("general-best", "failed", "general"),
            _record("general-best", "failed", "general"),
        ]

        result = select_models("Write Python code", records)

        self.assertEqual(["coding-best"], [item.model_id for item in result])


if __name__ == "__main__":
    unittest.main()
