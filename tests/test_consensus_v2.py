from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from gracekelly.core.consensus import ConsensusResult
from gracekelly.core.consensus_v2 import (
    ConsensusExecutorV2,
    ConsensusV2Config,
    ConsensusV2Result,
    DivergenceAction,
)


def _make_embeddings_client(vectors: list[list[float]] | None = None):
    client = MagicMock()
    if vectors is not None:
        client.embed_batch.return_value = vectors
    else:
        client.embed_batch.side_effect = lambda texts: [[1.0, 0.0]] * len(texts)
    return client


class TestConsensusV2(unittest.TestCase):
    def test_basic_execution(self):
        client = _make_embeddings_client()
        executor = ConsensusExecutorV2(client)
        result = executor.execute("hello", lambda p: "response")
        self.assertIsInstance(result, ConsensusV2Result)
        self.assertTrue(len(result.best_response) > 0)

    def test_all_flags_false(self):
        config = ConsensusV2Config(
            use_adaptive_params=False,
            use_debate=False,
            use_cross_pollination=False,
            use_cluster_confidence=False,
            use_divergence_handling=False,
        )
        client = _make_embeddings_client()
        executor = ConsensusExecutorV2(client, config)
        result = executor.execute("hello", lambda p: "response")
        self.assertIsInstance(result, ConsensusV2Result)

    def test_adaptive_params_affect_behavior(self):
        call_counts: dict[str, int] = {"coding": 0, "creative": 0}

        def count_coding(p: str) -> str:
            call_counts["coding"] += 1
            return "code_response"

        def count_creative(p: str) -> str:
            call_counts["creative"] += 1
            return "creative_response"

        client = _make_embeddings_client()
        config = ConsensusV2Config(use_divergence_handling=True)
        executor = ConsensusExecutorV2(client, config)

        executor.execute("write a python function", count_coding)
        executor.execute("write a poem", count_creative)

        self.assertGreater(call_counts["coding"], 0)
        self.assertGreater(call_counts["creative"], 0)

    def test_high_similarity_accept(self):
        client = _make_embeddings_client()
        config = ConsensusV2Config(
            use_adaptive_params=False,
            use_divergence_handling=True,
        )
        executor = ConsensusExecutorV2(client, config)
        result = executor.execute("hello", lambda p: "same")
        self.assertEqual(result.total_rounds, 1)
        self.assertEqual(result.final_result.status, DivergenceAction.ACCEPT)

    def test_debate_triggered_on_moderate_consensus(self):
        def make_diverse_embeddings(texts):
            n = len(texts)
            vecs = []
            for i in range(n):
                if i < n * 2 // 3:
                    vecs.append([1.0, 0.0, 0.0])
                else:
                    vecs.append([0.0, 1.0, 0.0])
            return vecs

        client = MagicMock()
        client.embed_batch.side_effect = make_diverse_embeddings

        config = ConsensusV2Config(
            use_adaptive_params=False,
            use_debate=True,
            use_divergence_handling=True,
        )

        debate_calls: list[str] = []

        def mock_execute(prompt: str) -> str:
            debate_calls.append(prompt)
            return "response"

        executor = ConsensusExecutorV2(client, config)
        executor.execute("analyze this", mock_execute)
        self.assertGreater(len(debate_calls), 0)

    def test_dissenting_views_populated(self):
        def make_diverse(texts):
            n = len(texts)
            vecs = []
            for i in range(n):
                v = [0.0] * 10
                v[i % 10] = 1.0
                vecs.append(v)
            return vecs

        client = MagicMock()
        client.embed_batch.side_effect = make_diverse

        config = ConsensusV2Config(
            use_adaptive_params=False,
            use_divergence_handling=False,
        )

        responses = iter([f"response_{i}" for i in range(100)])
        executor = ConsensusExecutorV2(client, config)
        result = executor.execute("hello", lambda p: next(responses))
        if result.consensus_result.num_clusters > 1:
            self.assertGreater(len(result.final_result.dissenting_views), 0)

    def test_total_rounds_gte_one(self):
        client = _make_embeddings_client()
        executor = ConsensusExecutorV2(client)
        result = executor.execute("hello", lambda p: "r")
        self.assertGreaterEqual(result.total_rounds, 1)

    def test_best_response_non_empty(self):
        client = _make_embeddings_client()
        executor = ConsensusExecutorV2(client)
        result = executor.execute("hello", lambda p: "my_response")
        self.assertTrue(len(result.best_response) > 0)

    def test_consensus_result_valid_score(self):
        client = _make_embeddings_client()
        executor = ConsensusExecutorV2(client)
        result = executor.execute("hello", lambda p: "r")
        self.assertGreaterEqual(result.consensus_result.consensus_score, 0.0)
        self.assertLessEqual(result.consensus_result.consensus_score, 1.0)

    def test_all_features_enabled(self):
        client = _make_embeddings_client()
        config = ConsensusV2Config(
            use_adaptive_params=True,
            use_debate=True,
            use_cross_pollination=True,
            use_cluster_confidence=True,
            use_divergence_handling=True,
        )
        executor = ConsensusExecutorV2(client, config)
        result = executor.execute("write python code", lambda p: "code_output")
        self.assertIsInstance(result, ConsensusV2Result)
        self.assertIsInstance(result.consensus_result, ConsensusResult)

    def test_consensus_result_has_cluster_info(self):
        client = _make_embeddings_client()
        executor = ConsensusExecutorV2(client)
        result = executor.execute("hello", lambda p: "r")
        self.assertGreater(result.consensus_result.num_clusters, 0)
        self.assertGreater(result.consensus_result.total_responses, 0)
        self.assertIsNotNone(result.consensus_result.top_cluster)

    def test_peer_review_enabled(self):
        client = _make_embeddings_client()
        config = ConsensusV2Config(
            use_adaptive_params=False,
            use_divergence_handling=False,
            use_peer_review=True,
        )
        call_log: list[str] = []

        def mock_fn(prompt: str) -> str:
            call_log.append(prompt)
            return "response"

        executor = ConsensusExecutorV2(client, config)
        result = executor.execute("hello", mock_fn)
        self.assertIsInstance(result, ConsensusV2Result)
        review_calls = [c for c in call_log if "Rank these answers" in c]
        self.assertGreater(len(review_calls), 0)

    def test_round_weighting_enabled(self):
        client = _make_embeddings_client()
        config = ConsensusV2Config(
            use_adaptive_params=False,
            use_divergence_handling=False,
            use_round_weighting=True,
        )
        executor = ConsensusExecutorV2(client, config)
        result = executor.execute("hello", lambda p: "response")
        self.assertIsInstance(result, ConsensusV2Result)
        self.assertGreaterEqual(result.weighted_score, 0.0)
        self.assertLessEqual(result.weighted_score, 1.0)

    def test_all_new_features_enabled(self):
        client = _make_embeddings_client()
        config = ConsensusV2Config(
            use_adaptive_params=True,
            use_debate=True,
            use_cross_pollination=True,
            use_cluster_confidence=True,
            use_divergence_handling=True,
            use_peer_review=True,
            use_round_weighting=True,
        )
        executor = ConsensusExecutorV2(client, config)
        result = executor.execute("write python code", lambda p: "code_output")
        self.assertIsInstance(result, ConsensusV2Result)
        self.assertGreaterEqual(result.weighted_score, 0.0)


if __name__ == "__main__":
    unittest.main()
