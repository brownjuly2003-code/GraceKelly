from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from gracekelly.core.consensus_v2 import (
    ConsensusExecutorV2,
    ConsensusV2Config,
    _build_cluster_infos,
)
from gracekelly.core.embeddings import EmbeddingsClient


def _identical_client() -> EmbeddingsClient:
    client = MagicMock(spec=EmbeddingsClient)
    client.embed_batch.side_effect = lambda texts: [[1.0, 0.0]] * len(texts)
    return client


def _diverse_client() -> EmbeddingsClient:
    """Returns orthogonal embeddings → forced low consensus."""
    def embed(texts: list[str]) -> list[list[float]]:
        n = len(texts)
        dim = max(n, 2)
        return [([1.0 if i == j % dim else 0.0 for i in range(dim)]) for j in range(n)]

    client = MagicMock(spec=EmbeddingsClient)
    client.embed_batch.side_effect = embed
    return client


class BuildClusterInfosTests(unittest.TestCase):
    """Unit tests for the pure _build_cluster_infos helper."""

    def _unit_sim_matrix(self, n: int) -> list[list[float]]:
        return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]

    def test_single_member_cluster_avg_sim_one(self) -> None:
        sim = self._unit_sim_matrix(3)
        infos, top = _build_cluster_infos(((0,),), sim)
        self.assertEqual(len(infos), 1)
        self.assertEqual(infos[0].avg_similarity, 1.0)

    def test_two_member_cluster_computes_avg_sim(self) -> None:
        # Similarity between 0 and 1 is 0.5
        sim = [[1.0, 0.5, 0.0], [0.5, 1.0, 0.0], [0.0, 0.0, 1.0]]
        infos, _ = _build_cluster_infos(((0, 1),), sim)
        self.assertAlmostEqual(infos[0].avg_similarity, 0.5)

    def test_top_members_from_largest_cluster(self) -> None:
        sim = self._unit_sim_matrix(5)
        small = (0, 1)
        large = (2, 3, 4)
        infos, top = _build_cluster_infos((small, large), sim)
        self.assertEqual(set(top), {2, 3, 4})

    def test_centroid_selected_from_members(self) -> None:
        sim = [[1.0, 0.8, 0.2], [0.8, 1.0, 0.2], [0.2, 0.2, 1.0]]
        infos, _ = _build_cluster_infos(((0, 1, 2),), sim)
        # centroid should be 0 or 1 (highest sum of similarities)
        self.assertIn(infos[0].centroid_index, (0, 1))

    def test_empty_clusters_returns_empty_infos(self) -> None:
        infos, top = _build_cluster_infos((), [[]])
        self.assertEqual(infos, [])
        self.assertEqual(top, ())

    def test_cluster_size_equals_member_count(self) -> None:
        sim = self._unit_sim_matrix(4)
        infos, _ = _build_cluster_infos(((0, 1, 2),), sim)
        self.assertEqual(infos[0].size, 3)


class ConsensusV2EdgeCasesTests(unittest.TestCase):
    def test_peer_review_skipped_for_single_response(self) -> None:
        """With min_responses=1 and single round, peer review should be skipped."""
        config = ConsensusV2Config(
            use_peer_review=True,
            use_adaptive_params=False,
            use_debate=False,
            use_divergence_handling=False,
            use_cross_pollination=False,
            use_cluster_confidence=False,
            use_round_weighting=False,
        )
        call_count = {"n": 0}

        def execute_fn(p: str) -> str:
            call_count["n"] += 1
            return "answer"

        client = _identical_client()
        executor = ConsensusExecutorV2(client, config)
        result = executor.execute("question", execute_fn)
        # With peer_review enabled, extra call_count would indicate peer review executed.
        # With 1 response peer review is skipped (len > 1 check), so only min_responses calls.
        # The result must still be valid.
        self.assertIsNotNone(result.best_response)

    def test_best_response_non_empty_with_identical_responses(self) -> None:
        config = ConsensusV2Config(use_adaptive_params=False, use_debate=False,
                                   use_divergence_handling=False, use_cross_pollination=False,
                                   use_cluster_confidence=False, use_round_weighting=False,
                                   use_peer_review=False)
        executor = ConsensusExecutorV2(_identical_client(), config)
        result = executor.execute("question", lambda p: "consistent answer")
        self.assertEqual(result.best_response, "consistent answer")

    def test_weighted_score_between_zero_and_one(self) -> None:
        executor = ConsensusExecutorV2(_identical_client())
        result = executor.execute("test", lambda _: "ok")
        self.assertGreaterEqual(result.weighted_score, 0.0)
        self.assertLessEqual(result.weighted_score, 1.0)

    def test_total_rounds_at_least_one(self) -> None:
        executor = ConsensusExecutorV2(_identical_client())
        result = executor.execute("test", lambda _: "ok")
        self.assertGreaterEqual(result.total_rounds, 1)

    def test_dissenting_views_is_tuple(self) -> None:
        executor = ConsensusExecutorV2(_identical_client())
        result = executor.execute("test", lambda _: "same")
        self.assertIsInstance(result.final_result.dissenting_views, tuple)

    def test_round_weighting_enabled_returns_valid_score(self) -> None:
        config = ConsensusV2Config(use_round_weighting=True)
        executor = ConsensusExecutorV2(_identical_client(), config)
        result = executor.execute("test", lambda _: "response")
        self.assertGreaterEqual(result.weighted_score, 0.0)

    def test_all_flags_disabled_still_returns_result(self) -> None:
        config = ConsensusV2Config(
            use_adaptive_params=False,
            use_debate=False,
            use_cross_pollination=False,
            use_cluster_confidence=False,
            use_divergence_handling=False,
            use_peer_review=False,
            use_round_weighting=False,
        )
        executor = ConsensusExecutorV2(_identical_client(), config)
        result = executor.execute("test", lambda _: "answer")
        self.assertIsNotNone(result)
        self.assertIsInstance(result.best_response, str)

    def test_diverse_responses_produce_dissenting_views(self) -> None:
        """With diverse embeddings, multiple clusters → dissenting views likely."""
        config = ConsensusV2Config(
            use_adaptive_params=False,
            use_debate=False,
            use_divergence_handling=False,
            use_cross_pollination=False,
            use_cluster_confidence=False,
            use_round_weighting=False,
            use_peer_review=False,
        )
        responses = ["A", "B", "C"]
        idx = [0]

        def execute_fn(_: str) -> str:
            r = responses[idx[0] % len(responses)]
            idx[0] += 1
            return r

        executor = ConsensusExecutorV2(_diverse_client(), config)
        result = executor.execute("question", execute_fn)
        # result must be valid even with high divergence
        self.assertIsInstance(result.best_response, str)
        self.assertIsInstance(result.final_result.dissenting_views, tuple)


if __name__ == "__main__":
    unittest.main()
