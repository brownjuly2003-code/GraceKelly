from __future__ import annotations

import unittest

from gracekelly.core.consensus import ConsensusConfig
from gracekelly.core.consensus_analyzer import ConsensusAnalyzer
from gracekelly.core.embeddings import EmbeddingsClient


def _make_mock_client(embeddings_map: dict[str, list[float]]) -> EmbeddingsClient:
    client = unittest.mock.MagicMock(spec=EmbeddingsClient)
    client.embed.side_effect = lambda text: embeddings_map[text]
    client.embed_batch.side_effect = lambda texts: [embeddings_map[t] for t in texts]
    return client


class ConsensusAnalyzerTests(unittest.TestCase):
    def test_single_response(self) -> None:
        client = _make_mock_client({"a": [1.0, 0.0]})
        analyzer = ConsensusAnalyzer(client)
        result = analyzer.analyze(["a"])
        self.assertEqual(result.consensus_score, 1.0)
        self.assertEqual(result.num_clusters, 1)

    def test_identical_responses(self) -> None:
        client = _make_mock_client(
            {"a": [1.0, 0.0], "b": [1.0, 0.0], "c": [1.0, 0.0]},
        )
        analyzer = ConsensusAnalyzer(client)
        result = analyzer.analyze(["a", "b", "c"])
        self.assertEqual(result.num_clusters, 1)
        self.assertEqual(result.consensus_score, 1.0)

    def test_distinct_responses(self) -> None:
        client = _make_mock_client(
            {"a": [1.0, 0.0, 0.0], "b": [0.0, 1.0, 0.0], "c": [0.0, 0.0, 1.0]},
        )
        analyzer = ConsensusAnalyzer(client)
        result = analyzer.analyze(["a", "b", "c"])
        self.assertEqual(result.num_clusters, 3)
        self.assertAlmostEqual(result.consensus_score, 0.3333, places=2)

    def test_two_similar_one_different(self) -> None:
        client = _make_mock_client(
            {"a": [1.0, 0.0], "b": [0.9, 0.435889894], "c": [0.0, 1.0]},
        )
        analyzer = ConsensusAnalyzer(client)
        result = analyzer.analyze(["a", "b", "c"])
        self.assertEqual(result.num_clusters, 2)
        self.assertEqual(result.top_cluster.size, 2)

    def test_needs_debate_true(self) -> None:
        client = _make_mock_client(
            {"a": [1.0, 0.0], "b": [0.9, 0.435889894], "c": [0.0, 1.0]},
        )
        analyzer = ConsensusAnalyzer(client)
        result = analyzer.analyze(["a", "b", "c"])
        self.assertTrue(result.needs_debate)

    def test_needs_debate_false(self) -> None:
        client = _make_mock_client(
            {"a": [1.0, 0.0], "b": [1.0, 0.0], "c": [1.0, 0.0]},
        )
        analyzer = ConsensusAnalyzer(client)
        result = analyzer.analyze(["a", "b", "c"])
        self.assertFalse(result.needs_debate)

    def test_round_number_passed_through(self) -> None:
        client = _make_mock_client({"a": [1.0, 0.0]})
        analyzer = ConsensusAnalyzer(client)
        result = analyzer.analyze(["a"], round_number=3)
        self.assertEqual(result.round_number, 3)

    def test_centroid_is_most_central(self) -> None:
        client = _make_mock_client(
            {"a": [1.0, 0.0], "b": [0.95, 0.3122499], "c": [0.0, 1.0]},
        )
        analyzer = ConsensusAnalyzer(client)
        result = analyzer.analyze(["a", "b", "c"])
        self.assertIn(result.top_cluster.centroid_index, result.top_cluster.member_indices)

    def test_empty_responses_raises(self) -> None:
        client = _make_mock_client({})
        analyzer = ConsensusAnalyzer(client)
        with self.assertRaises(ValueError):
            analyzer.analyze([])

    def test_custom_config_threshold(self) -> None:
        client = _make_mock_client(
            {"a": [1.0, 0.0], "b": [0.9, 0.435889894], "c": [0.0, 1.0]},
        )
        default_result = ConsensusAnalyzer(client).analyze(["a", "b", "c"])
        strict_result = ConsensusAnalyzer(
            client,
            ConsensusConfig(similarity_threshold=0.99),
        ).analyze(["a", "b", "c"])
        self.assertGreater(strict_result.num_clusters, default_result.num_clusters)

    def test_avg_similarity_single_member(self) -> None:
        client = _make_mock_client(
            {"a": [1.0, 0.0, 0.0], "b": [0.0, 1.0, 0.0], "c": [0.0, 0.0, 1.0]},
        )
        analyzer = ConsensusAnalyzer(client)
        result = analyzer.analyze(["a", "b", "c"])
        self.assertTrue(all(cluster.avg_similarity == 1.0 for cluster in result.all_clusters))

    def test_cluster_infos_have_correct_ids(self) -> None:
        client = _make_mock_client(
            {"a": [1.0, 0.0, 0.0], "b": [0.0, 1.0, 0.0], "c": [0.0, 0.0, 1.0]},
        )
        analyzer = ConsensusAnalyzer(client)
        result = analyzer.analyze(["a", "b", "c"])
        self.assertEqual([cluster.cluster_id for cluster in result.all_clusters], [0, 1, 2])


class AvgIntraSimilarityTests(unittest.TestCase):
    """Direct unit tests for ConsensusAnalyzer._avg_intra_similarity."""

    def test_single_member_returns_one(self) -> None:
        matrix: list[list[float]] = [[1.0]]
        result = ConsensusAnalyzer._avg_intra_similarity([0], matrix)
        self.assertEqual(result, 1.0)

    def test_two_members_returns_their_similarity(self) -> None:
        matrix = [[1.0, 0.8], [0.8, 1.0]]
        result = ConsensusAnalyzer._avg_intra_similarity([0, 1], matrix)
        self.assertAlmostEqual(result, 0.8)

    def test_three_members_averages_all_pairs(self) -> None:
        # pairs: (0,1)=0.9, (0,2)=0.6, (1,2)=0.7 → avg = (0.9+0.6+0.7)/3
        matrix = [
            [1.0, 0.9, 0.6],
            [0.9, 1.0, 0.7],
            [0.6, 0.7, 1.0],
        ]
        result = ConsensusAnalyzer._avg_intra_similarity([0, 1, 2], matrix)
        self.assertAlmostEqual(result, (0.9 + 0.6 + 0.7) / 3, places=6)

    def test_sparse_indices_skip_diagonal(self) -> None:
        # indices [0, 2] in a 3×3 matrix; only pair (0,2)=0.5 used
        matrix = [
            [1.0, 0.9, 0.5],
            [0.9, 1.0, 0.7],
            [0.5, 0.7, 1.0],
        ]
        result = ConsensusAnalyzer._avg_intra_similarity([0, 2], matrix)
        self.assertAlmostEqual(result, 0.5)

    def test_zero_similarity_cluster(self) -> None:
        matrix = [[1.0, 0.0], [0.0, 1.0]]
        result = ConsensusAnalyzer._avg_intra_similarity([0, 1], matrix)
        self.assertAlmostEqual(result, 0.0)


class FindCentroidTests(unittest.TestCase):
    """Direct unit tests for ConsensusAnalyzer._find_centroid."""

    def test_single_member_returns_that_index(self) -> None:
        matrix: list[list[float]] = [[1.0]]
        result = ConsensusAnalyzer._find_centroid([0], matrix)
        self.assertEqual(result, 0)

    def test_two_members_equal_similarity_returns_first(self) -> None:
        matrix = [[1.0, 0.5], [0.5, 1.0]]
        result = ConsensusAnalyzer._find_centroid([0, 1], matrix)
        self.assertIn(result, [0, 1])

    def test_centroid_is_most_similar_to_others(self) -> None:
        # index 1 has highest total similarity: 0.9+0.8 = 1.7 vs 0.9+0.4 = 1.3 vs 0.8+0.4 = 1.2
        matrix = [
            [1.0, 0.9, 0.8],
            [0.9, 1.0, 0.4],
            [0.8, 0.4, 1.0],
        ]
        # Wait, recalculate: for [0,1,2]
        # idx 0: sum = matrix[0][1] + matrix[0][2] = 0.9 + 0.8 = 1.7
        # idx 1: sum = matrix[1][0] + matrix[1][2] = 0.9 + 0.4 = 1.3
        # idx 2: sum = matrix[2][0] + matrix[2][1] = 0.8 + 0.4 = 1.2
        # best is idx 0 with sum 1.7
        result = ConsensusAnalyzer._find_centroid([0, 1, 2], matrix)
        self.assertEqual(result, 0)

    def test_centroid_among_subset_of_indices(self) -> None:
        # 4×4 matrix, only indices [1, 3] considered
        matrix = [
            [1.0, 0.2, 0.2, 0.2],
            [0.2, 1.0, 0.2, 0.9],
            [0.2, 0.2, 1.0, 0.2],
            [0.2, 0.9, 0.2, 1.0],
        ]
        # idx 1 vs idx 3: both have same sim to each other (0.9)
        result = ConsensusAnalyzer._find_centroid([1, 3], matrix)
        self.assertIn(result, [1, 3])

    def test_clearly_central_node(self) -> None:
        # index 2 is the hub — most similar to all others
        matrix = [
            [1.0, 0.1, 0.9],
            [0.1, 1.0, 0.9],
            [0.9, 0.9, 1.0],
        ]
        # idx 0 sum = 0.1 + 0.9 = 1.0
        # idx 1 sum = 0.1 + 0.9 = 1.0
        # idx 2 sum = 0.9 + 0.9 = 1.8
        result = ConsensusAnalyzer._find_centroid([0, 1, 2], matrix)
        self.assertEqual(result, 2)


if __name__ == "__main__":
    unittest.main()
