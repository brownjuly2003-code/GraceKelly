from __future__ import annotations

import unittest

from gracekelly.core.round_weighting import (
    WeightedScore,
    consensus_score_weighted,
    round_weight,
    weighted_cluster_size,
)


class TestRoundWeight(unittest.TestCase):
    def test_round_zero_weight_is_one(self) -> None:
        self.assertAlmostEqual(round_weight(0), 1.0)

    def test_round_zero_greater_than_round_one(self) -> None:
        self.assertGreater(round_weight(0), round_weight(1))

    def test_decay_base_one_all_equal(self) -> None:
        self.assertAlmostEqual(round_weight(0, 1.0), 1.0)
        self.assertAlmostEqual(round_weight(5, 1.0), 1.0)
        self.assertAlmostEqual(round_weight(100, 1.0), 1.0)

    def test_decay_base_half_round_two(self) -> None:
        self.assertAlmostEqual(round_weight(2, 0.5), 0.25)

    def test_default_decay_round_one(self) -> None:
        self.assertAlmostEqual(round_weight(1), 0.8)

    def test_default_decay_round_two(self) -> None:
        self.assertAlmostEqual(round_weight(2), 0.64)


class TestWeightedClusterSize(unittest.TestCase):
    def test_single_response_round_zero(self) -> None:
        result = weighted_cluster_size((0,), (0,))
        self.assertAlmostEqual(result, 1.0)

    def test_sums_weights_across_indices(self) -> None:
        result = weighted_cluster_size((0, 1), (0, 1))
        self.assertAlmostEqual(result, 1.0 + 0.8)

    def test_custom_decay(self) -> None:
        result = weighted_cluster_size((0, 1, 2), (0, 1, 2), 0.5)
        self.assertAlmostEqual(result, 1.0 + 0.5 + 0.25)


class TestConsensusScoreWeighted(unittest.TestCase):
    def test_all_in_one_cluster(self) -> None:
        result = consensus_score_weighted(
            (0, 1, 2), (0, 1, 2), (0, 0, 0)
        )
        self.assertAlmostEqual(result.raw_score, 1.0)
        self.assertAlmostEqual(result.weighted_score, 1.0)

    def test_later_rounds_weigh_less(self) -> None:
        result_early = consensus_score_weighted(
            (0,), (0, 1), (0, 2)
        )
        result_late = consensus_score_weighted(
            (1,), (0, 1), (0, 2)
        )
        self.assertGreater(
            result_early.weighted_score, result_late.weighted_score
        )

    def test_empty_indices(self) -> None:
        result = consensus_score_weighted((), (), ())
        self.assertAlmostEqual(result.raw_score, 0.0)
        self.assertAlmostEqual(result.weighted_score, 0.0)
        self.assertAlmostEqual(result.total_weight, 0.0)

    def test_round_weights_tuple_length(self) -> None:
        result = consensus_score_weighted(
            (0, 1), (0, 1, 2), (0, 1, 2)
        )
        self.assertEqual(len(result.round_weights), 3)

    def test_raw_score_ignores_weights(self) -> None:
        result = consensus_score_weighted(
            (0,), (0, 1, 2), (0, 5, 10)
        )
        self.assertAlmostEqual(result.raw_score, 1.0 / 3.0)

    def test_weighted_score_with_known_values(self) -> None:
        result = consensus_score_weighted(
            (0,), (0, 1), (0, 0), decay_base=0.8
        )
        self.assertAlmostEqual(result.weighted_score, 0.5)
        self.assertAlmostEqual(result.total_weight, 2.0)

    def test_result_is_weighted_score_dataclass(self) -> None:
        result = consensus_score_weighted((0,), (0,), (0,))
        self.assertIsInstance(result, WeightedScore)


if __name__ == "__main__":
    unittest.main()
