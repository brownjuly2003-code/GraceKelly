from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from gracekelly.core.adaptive_selector import ModelRecommendation, select_models


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
            recommendation.score = 0.5

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
