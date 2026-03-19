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


if __name__ == "__main__":
    unittest.main()
