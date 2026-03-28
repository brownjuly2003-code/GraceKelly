from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from gracekelly.core.model_stats import aggregate_model_stats, rank_models_by_success_rate


class ModelStatsTests(unittest.TestCase):
    def test_empty_input(self) -> None:
        self.assertEqual(aggregate_model_stats([]), {})

    def test_single_success(self) -> None:
        result = aggregate_model_stats(
            [{"model_id": "m1", "status": "completed", "duration_ms": 100}],
        )
        self.assertEqual(result["m1"].success_rate, 1.0)
        self.assertEqual(result["m1"].total_executions, 1)

    def test_single_failure(self) -> None:
        result = aggregate_model_stats(
            [{"model_id": "m1", "status": "failed", "duration_ms": 100}],
        )
        self.assertEqual(result["m1"].success_rate, 0.0)
        self.assertEqual(result["m1"].failed, 1)

    def test_mixed_results(self) -> None:
        result = aggregate_model_stats(
            [
                {"model_id": "m1", "status": "completed", "duration_ms": 100},
                {"model_id": "m1", "status": "completed", "duration_ms": 200},
                {"model_id": "m1", "status": "completed", "duration_ms": 300},
                {"model_id": "m1", "status": "failed", "duration_ms": 400},
                {"model_id": "m1", "status": "failed", "duration_ms": 500},
            ],
        )
        self.assertEqual(result["m1"].success_rate, 0.6)
        self.assertEqual(result["m1"].total_executions, 5)

    def test_multiple_models(self) -> None:
        result = aggregate_model_stats(
            [
                {"model_id": "m1", "status": "completed", "duration_ms": 100},
                {"model_id": "m2", "status": "failed", "duration_ms": 200},
            ],
        )
        self.assertEqual(len(result), 2)

    def test_avg_duration_calculation(self) -> None:
        result = aggregate_model_stats(
            [
                {"model_id": "m1", "status": "completed", "duration_ms": 100},
                {"model_id": "m1", "status": "completed", "duration_ms": 200},
                {"model_id": "m1", "status": "completed", "duration_ms": 300},
            ],
        )
        self.assertEqual(result["m1"].avg_duration_ms, 200.0)

    def test_duration_none_excluded(self) -> None:
        result = aggregate_model_stats(
            [
                {"model_id": "m1", "status": "completed", "duration_ms": 100},
                {"model_id": "m1", "status": "completed", "duration_ms": None},
                {"model_id": "m1", "status": "completed", "duration_ms": 300},
            ],
        )
        self.assertEqual(result["m1"].avg_duration_ms, 200.0)
        self.assertEqual(result["m1"].total_executions, 3)

    def test_total_duration_sum(self) -> None:
        result = aggregate_model_stats(
            [
                {"model_id": "m1", "status": "completed", "duration_ms": 100},
                {"model_id": "m1", "status": "completed", "duration_ms": 200},
                {"model_id": "m1", "status": "completed", "duration_ms": 300},
            ],
        )
        self.assertEqual(result["m1"].total_duration_ms, 600)

    def test_rank_by_success_rate(self) -> None:
        stats = aggregate_model_stats(
            [
                {"model_id": "m1", "status": "completed", "duration_ms": 100},
                {"model_id": "m2", "status": "completed", "duration_ms": 200},
                {"model_id": "m2", "status": "failed", "duration_ms": 300},
            ],
        )
        ranking = rank_models_by_success_rate(stats)
        self.assertEqual(ranking[0].model_id, "m1")
        self.assertEqual(ranking[1].model_id, "m2")

    def test_rank_tiebreak_by_latency(self) -> None:
        stats = aggregate_model_stats(
            [
                {"model_id": "m1", "status": "completed", "duration_ms": 100},
                {"model_id": "m2", "status": "completed", "duration_ms": 200},
            ],
        )
        ranking = rank_models_by_success_rate(stats)
        self.assertEqual(ranking[0].model_id, "m1")

    def test_rank_min_executions_filter(self) -> None:
        stats = aggregate_model_stats(
            [
                {"model_id": "m1", "status": "completed", "duration_ms": 100},
                {"model_id": "m2", "status": "completed", "duration_ms": 100},
                {"model_id": "m2", "status": "completed", "duration_ms": 100},
                {"model_id": "m2", "status": "completed", "duration_ms": 100},
                {"model_id": "m2", "status": "completed", "duration_ms": 100},
                {"model_id": "m2", "status": "completed", "duration_ms": 100},
            ],
        )
        ranking = rank_models_by_success_rate(stats, min_executions=5)
        self.assertEqual(len(ranking), 1)
        self.assertEqual(ranking[0].model_id, "m2")

    def test_rank_empty_stats(self) -> None:
        self.assertEqual(rank_models_by_success_rate({}), [])

    def test_performance_is_frozen(self) -> None:
        perf = aggregate_model_stats(
            [{"model_id": "m1", "status": "completed", "duration_ms": 100}],
        )["m1"]
        with self.assertRaises(FrozenInstanceError):
            perf.success_rate = 1.0  # type: ignore[misc]

    def test_sorted_by_model_id(self) -> None:
        result = aggregate_model_stats(
            [
                {"model_id": "m2", "status": "completed", "duration_ms": 100},
                {"model_id": "m1", "status": "completed", "duration_ms": 100},
            ],
        )
        self.assertEqual(list(result.keys()), ["m1", "m2"])

    def test_success_rate_rounded(self) -> None:
        result = aggregate_model_stats(
            [
                {"model_id": "m1", "status": "completed", "duration_ms": 100},
                {"model_id": "m1", "status": "failed", "duration_ms": 100},
                {"model_id": "m1", "status": "failed", "duration_ms": 100},
            ],
        )
        self.assertAlmostEqual(result["m1"].success_rate, 0.333, places=3)


class ModelStatsEdgeCasesTests(unittest.TestCase):
    """Cover uncovered branches in aggregate_model_stats and rank_models_by_success_rate."""

    def test_record_without_duration_key_excluded_from_avg(self) -> None:
        # record has no "duration_ms" key at all
        result = aggregate_model_stats(
            [
                {"model_id": "m1", "status": "completed"},
                {"model_id": "m1", "status": "completed", "duration_ms": 200},
            ],
        )
        self.assertEqual(result["m1"].avg_duration_ms, 200.0)
        self.assertEqual(result["m1"].total_executions, 2)

    def test_float_duration_accepted(self) -> None:
        result = aggregate_model_stats(
            [
                {"model_id": "m1", "status": "completed", "duration_ms": 100.5},
                {"model_id": "m1", "status": "completed", "duration_ms": 199.5},
            ],
        )
        self.assertEqual(result["m1"].total_duration_ms, 299)

    def test_string_duration_excluded(self) -> None:
        # non-numeric duration_ms must be excluded from averages
        result = aggregate_model_stats(
            [
                {"model_id": "m1", "status": "completed", "duration_ms": "slow"},
                {"model_id": "m1", "status": "completed", "duration_ms": 100},
            ],
        )
        self.assertEqual(result["m1"].avg_duration_ms, 100.0)

    def test_no_durations_at_all_gives_zero_avg(self) -> None:
        result = aggregate_model_stats(
            [
                {"model_id": "m1", "status": "completed", "duration_ms": None},
                {"model_id": "m1", "status": "failed", "duration_ms": None},
            ],
        )
        self.assertEqual(result["m1"].avg_duration_ms, 0.0)
        self.assertEqual(result["m1"].total_duration_ms, 0)

    def test_rank_with_min_executions_exactly_at_threshold(self) -> None:
        stats = aggregate_model_stats(
            [
                {"model_id": "m1", "status": "completed", "duration_ms": 100},
                {"model_id": "m2", "status": "completed", "duration_ms": 100},
                {"model_id": "m2", "status": "completed", "duration_ms": 100},
            ],
        )
        # m1 has exactly 1 execution — included when min_executions=1
        ranking = rank_models_by_success_rate(stats, min_executions=1)
        self.assertEqual(len(ranking), 2)

    def test_rank_with_min_executions_excludes_below_threshold(self) -> None:
        stats = aggregate_model_stats(
            [
                {"model_id": "m1", "status": "completed", "duration_ms": 100},
                {"model_id": "m2", "status": "completed", "duration_ms": 100},
                {"model_id": "m2", "status": "completed", "duration_ms": 100},
            ],
        )
        # m1 has 1 execution — excluded when min_executions=2
        ranking = rank_models_by_success_rate(stats, min_executions=2)
        self.assertEqual(len(ranking), 1)
        self.assertEqual(ranking[0].model_id, "m2")

    def test_rank_all_excluded_by_min_executions(self) -> None:
        stats = aggregate_model_stats(
            [{"model_id": "m1", "status": "completed", "duration_ms": 100}],
        )
        ranking = rank_models_by_success_rate(stats, min_executions=10)
        self.assertEqual(ranking, [])

    def test_mixed_success_failure_success_rate_field(self) -> None:
        result = aggregate_model_stats(
            [
                {"model_id": "m1", "status": "completed", "duration_ms": 50},
                {"model_id": "m1", "status": "failed", "duration_ms": 50},
            ],
        )
        self.assertAlmostEqual(result["m1"].success_rate, 0.5)
        self.assertEqual(result["m1"].successful, 1)
        self.assertEqual(result["m1"].failed, 1)

    def test_unknown_status_not_counted_as_success_or_failure(self) -> None:
        result = aggregate_model_stats(
            [{"model_id": "m1", "status": "running", "duration_ms": 100}],
        )
        self.assertEqual(result["m1"].successful, 0)
        self.assertEqual(result["m1"].failed, 0)
        self.assertEqual(result["m1"].success_rate, 0.0)


if __name__ == "__main__":
    unittest.main()
