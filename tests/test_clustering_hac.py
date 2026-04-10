from __future__ import annotations

import unittest

from gracekelly.core.clustering_hac import _avg_linkage, hac_cluster


class TestHacCluster(unittest.TestCase):
    def test_empty_matrix(self) -> None:
        result = hac_cluster([])
        self.assertEqual(result.num_clusters, 0)
        self.assertEqual(result.clusters, ())
        self.assertEqual(result.merge_history, ())

    def test_single_item(self) -> None:
        result = hac_cluster([[1.0]])
        self.assertEqual(result.num_clusters, 1)
        self.assertEqual(result.clusters, ((0,),))
        self.assertEqual(result.merge_history, ())

    def test_two_identical_merge(self) -> None:
        sim = [[1.0, 1.0], [1.0, 1.0]]
        result = hac_cluster(sim, threshold=0.85)
        self.assertEqual(result.num_clusters, 1)
        self.assertIn(0, result.clusters[0])
        self.assertIn(1, result.clusters[0])

    def test_two_orthogonal_no_merge(self) -> None:
        sim = [[1.0, 0.0], [0.0, 1.0]]
        result = hac_cluster(sim, threshold=0.85)
        self.assertEqual(result.num_clusters, 2)

    def test_three_items_two_similar(self) -> None:
        sim = [
            [1.0, 0.95, 0.1],
            [0.95, 1.0, 0.1],
            [0.1, 0.1, 1.0],
        ]
        result = hac_cluster(sim, threshold=0.85)
        self.assertEqual(result.num_clusters, 2)
        sizes = sorted([len(c) for c in result.clusters])
        self.assertEqual(sizes, [1, 2])

    def test_threshold_zero_all_merge(self) -> None:
        sim = [
            [1.0, 0.5, 0.3],
            [0.5, 1.0, 0.4],
            [0.3, 0.4, 1.0],
        ]
        result = hac_cluster(sim, threshold=0.0)
        self.assertEqual(result.num_clusters, 1)
        self.assertEqual(len(result.clusters[0]), 3)

    def test_threshold_one_no_merge(self) -> None:
        sim = [
            [1.0, 0.99, 0.5],
            [0.99, 1.0, 0.5],
            [0.5, 0.5, 1.0],
        ]
        result = hac_cluster(sim, threshold=1.0)
        self.assertEqual(result.num_clusters, 3)

    def test_merge_history_recorded(self) -> None:
        sim = [[1.0, 0.9], [0.9, 1.0]]
        result = hac_cluster(sim, threshold=0.85)
        self.assertEqual(len(result.merge_history), 1)
        ci, cj, s = result.merge_history[0]
        self.assertAlmostEqual(s, 0.9)

    def test_five_items(self) -> None:
        sim = [
            [1.0, 0.95, 0.9, 0.1, 0.1],
            [0.95, 1.0, 0.92, 0.1, 0.1],
            [0.9, 0.92, 1.0, 0.1, 0.1],
            [0.1, 0.1, 0.1, 1.0, 0.93],
            [0.1, 0.1, 0.1, 0.93, 1.0],
        ]
        result = hac_cluster(sim, threshold=0.85)
        self.assertEqual(result.num_clusters, 2)
        sizes = sorted([len(c) for c in result.clusters])
        self.assertEqual(sizes, [2, 3])

    def test_symmetric_invariance(self) -> None:
        sim = [
            [1.0, 0.9, 0.2],
            [0.9, 1.0, 0.2],
            [0.2, 0.2, 1.0],
        ]
        result = hac_cluster(sim, threshold=0.85)
        self.assertEqual(result.num_clusters, 2)
        cluster_with_01 = [c for c in result.clusters if 0 in c and 1 in c]
        self.assertEqual(len(cluster_with_01), 1)

    def test_result_is_frozen(self) -> None:
        result = hac_cluster([[1.0]])
        with self.assertRaises(AttributeError):
            setattr(result, "num_clusters", 5)

    def test_avg_linkage(self) -> None:
        sim = [[1.0, 0.8, 0.6], [0.8, 1.0, 0.4], [0.6, 0.4, 1.0]]
        val = _avg_linkage([0], [1, 2], sim)
        self.assertAlmostEqual(val, (0.8 + 0.6) / 2)


if __name__ == "__main__":
    unittest.main()
