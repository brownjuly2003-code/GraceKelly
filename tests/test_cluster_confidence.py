from __future__ import annotations

import unittest

from gracekelly.core.cluster_confidence import (
    compute_cluster_confidence,
)


class TestClusterConfidence(unittest.TestCase):
    def test_empty_clusters(self):
        result = compute_cluster_confidence((), [])
        self.assertEqual(result.confidence, 0.0)
        self.assertFalse(result.is_unanimous)
        self.assertEqual(result.top_cluster_size, 0)

    def test_single_response(self):
        clusters = ((0,),)
        sim = [[1.0]]
        result = compute_cluster_confidence(clusters, sim)
        self.assertAlmostEqual(result.confidence, 1.0)
        self.assertTrue(result.is_unanimous)
        self.assertEqual(result.top_cluster_size, 1)
        self.assertEqual(result.total_responses, 1)

    def test_all_one_cluster(self):
        clusters = ((0, 1, 2),)
        sim = [
            [1.0, 0.9, 0.95],
            [0.9, 1.0, 0.92],
            [0.95, 0.92, 1.0],
        ]
        result = compute_cluster_confidence(clusters, sim)
        self.assertTrue(result.is_unanimous)
        self.assertAlmostEqual(result.raw_ratio, 1.0)
        self.assertGreater(result.confidence, 0.9)

    def test_even_split(self):
        clusters = ((0,), (1,))
        sim = [[1.0, 0.0], [0.0, 1.0]]
        result = compute_cluster_confidence(clusters, sim)
        self.assertFalse(result.is_unanimous)
        self.assertAlmostEqual(result.raw_ratio, 0.5)
        self.assertAlmostEqual(result.confidence, 0.5)

    def test_three_clusters_top_ratio(self):
        clusters = ((0, 1, 2), (3,), (4,))
        sim = [[1.0] * 5 for _ in range(5)]
        result = compute_cluster_confidence(clusters, sim)
        self.assertEqual(result.top_cluster_size, 3)
        self.assertEqual(result.total_responses, 5)
        self.assertAlmostEqual(result.raw_ratio, 0.6)

    def test_perfect_similarity(self):
        clusters = ((0, 1),)
        sim = [[1.0, 1.0], [1.0, 1.0]]
        result = compute_cluster_confidence(clusters, sim)
        self.assertAlmostEqual(result.avg_intra_similarity, 1.0)
        self.assertAlmostEqual(result.confidence, 1.0)

    def test_zero_intra_similarity(self):
        clusters = ((0, 1),)
        sim = [[1.0, 0.0], [0.0, 1.0]]
        result = compute_cluster_confidence(clusters, sim)
        self.assertAlmostEqual(result.avg_intra_similarity, 0.0)
        self.assertAlmostEqual(result.confidence, 0.0)

    def test_confidence_equals_ratio_times_intra(self):
        clusters = ((0, 1), (2,))
        sim = [
            [1.0, 0.8, 0.1],
            [0.8, 1.0, 0.1],
            [0.1, 0.1, 1.0],
        ]
        result = compute_cluster_confidence(clusters, sim)
        expected = result.raw_ratio * result.avg_intra_similarity
        self.assertAlmostEqual(result.confidence, expected)

    def test_result_is_frozen(self):
        result = compute_cluster_confidence(((0,),), [[1.0]])
        with self.assertRaises(AttributeError):
            result.confidence = 0.5


if __name__ == "__main__":
    unittest.main()
