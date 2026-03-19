from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from gracekelly.core.confidence import (
    ConfidenceScore,
    extract_batch_confidence,
    extract_confidence,
    weighted_vote,
)


class ConfidenceTests(unittest.TestCase):
    def test_extract_explicit_confidence(self) -> None:
        result = extract_confidence("Confidence: 8/10")
        self.assertEqual(result.raw_score, 8.0)
        self.assertEqual(result.normalized_score, 0.8)

    def test_extract_without_slash(self) -> None:
        result = extract_confidence("confidence: 7")
        self.assertEqual(result.raw_score, 7.0)

    def test_extract_with_equals(self) -> None:
        result = extract_confidence("Confidence=9")
        self.assertEqual(result.raw_score, 9.0)

    def test_extract_russian(self) -> None:
        result = extract_confidence("уверенность: 6/10")
        self.assertEqual(result.raw_score, 6.0)

    def test_extract_no_confidence_defaults_five(self) -> None:
        result = extract_confidence("Just a regular answer")
        self.assertEqual(result.raw_score, 5.0)

    def test_extract_clamps_above_ten(self) -> None:
        result = extract_confidence("confidence: 15")
        self.assertEqual(result.raw_score, 10.0)

    def test_extract_float_score(self) -> None:
        result = extract_confidence("confidence: 7.5/10")
        self.assertEqual(result.raw_score, 7.5)

    def test_extract_batch(self) -> None:
        results = extract_batch_confidence(
            ["Confidence: 8/10", "confidence: 7", "Just a regular answer"],
        )
        self.assertEqual(len(results), 3)
        self.assertEqual([score.response_index for score in results], [0, 1, 2])

    def test_weighted_vote_equal_weights(self) -> None:
        scores = [
            ConfidenceScore(0, 5.0, 0.5),
            ConfidenceScore(1, 5.0, 0.5),
            ConfidenceScore(2, 5.0, 0.5),
            ConfidenceScore(3, 5.0, 0.5),
        ]
        result = weighted_vote([0, 1], scores, total_responses=4)
        self.assertAlmostEqual(result, 0.5)

    def test_weighted_vote_high_confidence_cluster(self) -> None:
        scores = [
            ConfidenceScore(0, 9.0, 0.9),
            ConfidenceScore(1, 8.0, 0.8),
            ConfidenceScore(2, 2.0, 0.2),
        ]
        cluster_vote = weighted_vote([0, 1], scores, total_responses=3)
        other_vote = weighted_vote([2], scores, total_responses=3)
        self.assertGreater(cluster_vote, other_vote)

    def test_weighted_vote_empty_cluster(self) -> None:
        scores = [ConfidenceScore(0, 5.0, 0.5)]
        self.assertEqual(weighted_vote([], scores, total_responses=1), 0.0)

    def test_weighted_vote_zero_total(self) -> None:
        scores = [ConfidenceScore(0, 5.0, 0.5)]
        self.assertEqual(weighted_vote([0], scores, total_responses=0), 0.0)

    def test_confidence_score_is_frozen(self) -> None:
        score = extract_confidence("Confidence: 8/10")
        with self.assertRaises(FrozenInstanceError):
            score.raw_score = 1.0  # type: ignore[misc]

    def test_response_index_preserved(self) -> None:
        result = extract_confidence("text", 5)
        self.assertEqual(result.response_index, 5)


if __name__ == "__main__":
    unittest.main()
