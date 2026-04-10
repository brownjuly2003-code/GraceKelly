from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from gracekelly.core.consensus import (
    ClusterInfo,
    ConsensusConfig,
    ConsensusResult,
    build_consensus_result,
    needs_another_round,
)


class ConsensusTests(unittest.TestCase):
    def test_default_config_values(self) -> None:
        config = ConsensusConfig()
        self.assertEqual(config.similarity_threshold, 0.85)
        self.assertEqual(config.consensus_target, 0.95)
        self.assertEqual(config.max_rounds, 5)
        self.assertEqual(config.variations_per_round, 3)
        self.assertFalse(config.enable_peer_review)
        self.assertTrue(config.enable_confidence)

    def test_config_custom_values(self) -> None:
        config = ConsensusConfig(similarity_threshold=0.9, consensus_target=0.8)
        self.assertEqual(config.similarity_threshold, 0.9)
        self.assertEqual(config.consensus_target, 0.8)

    def test_config_is_frozen(self) -> None:
        config = ConsensusConfig()
        with self.assertRaises(FrozenInstanceError):
            setattr(config, "max_rounds", 10)

    def test_cluster_info_creation(self) -> None:
        cluster = ClusterInfo(cluster_id=0, member_indices=(0, 1, 2), centroid_index=1, size=3, avg_similarity=0.92)
        self.assertEqual(cluster.cluster_id, 0)
        self.assertEqual(cluster.member_indices, (0, 1, 2))
        self.assertEqual(cluster.centroid_index, 1)
        self.assertEqual(cluster.size, 3)
        self.assertEqual(cluster.avg_similarity, 0.92)

    def test_cluster_info_is_frozen(self) -> None:
        cluster = ClusterInfo(cluster_id=0, member_indices=(0,), centroid_index=0, size=1, avg_similarity=1.0)
        with self.assertRaises(FrozenInstanceError):
            setattr(cluster, "size", 5)

    def test_consensus_result_creation(self) -> None:
        cluster = ClusterInfo(cluster_id=0, member_indices=(0, 1), centroid_index=0, size=2, avg_similarity=0.8)
        result = ConsensusResult(
            consensus_score=0.8,
            num_clusters=1,
            top_cluster=cluster,
            all_clusters=(cluster,),
            needs_debate=True,
            round_number=1,
            total_responses=2,
        )
        self.assertEqual(result.consensus_score, 0.8)
        self.assertEqual(result.num_clusters, 1)
        self.assertEqual(result.top_cluster, cluster)
        self.assertEqual(result.all_clusters, (cluster,))
        self.assertTrue(result.needs_debate)
        self.assertEqual(result.round_number, 1)
        self.assertEqual(result.total_responses, 2)

    def test_consensus_result_needs_debate_true(self) -> None:
        cluster = ClusterInfo(cluster_id=0, member_indices=(0, 1), centroid_index=0, size=2, avg_similarity=0.5)
        result = build_consensus_result([cluster], 1, 4, ConsensusConfig())
        self.assertTrue(result.needs_debate)

    def test_consensus_result_needs_debate_false(self) -> None:
        cluster = ClusterInfo(cluster_id=0, member_indices=(0, 1, 2, 3, 4), centroid_index=0, size=24, avg_similarity=0.96)
        result = build_consensus_result([cluster], 1, 25, ConsensusConfig())
        self.assertFalse(result.needs_debate)

    def test_needs_another_round_true(self) -> None:
        cluster = ClusterInfo(cluster_id=0, member_indices=(0, 1), centroid_index=0, size=2, avg_similarity=0.8)
        result = ConsensusResult(0.5, 1, cluster, (cluster,), True, 1, 4)
        self.assertTrue(needs_another_round(result, ConsensusConfig()))

    def test_needs_another_round_false_converged(self) -> None:
        cluster = ClusterInfo(cluster_id=0, member_indices=(0, 1), centroid_index=0, size=2, avg_similarity=0.8)
        result = ConsensusResult(1.0, 1, cluster, (cluster,), False, 1, 2)
        self.assertFalse(needs_another_round(result, ConsensusConfig()))

    def test_needs_another_round_false_max_rounds(self) -> None:
        cluster = ClusterInfo(cluster_id=0, member_indices=(0, 1), centroid_index=0, size=2, avg_similarity=0.8)
        result = ConsensusResult(0.5, 1, cluster, (cluster,), True, 5, 4)
        self.assertFalse(needs_another_round(result, ConsensusConfig()))

    def test_build_consensus_result_single_cluster(self) -> None:
        cluster = ClusterInfo(cluster_id=0, member_indices=(0, 1, 2, 3, 4), centroid_index=0, size=5, avg_similarity=1.0)
        result = build_consensus_result([cluster], 1, 5, ConsensusConfig())
        self.assertEqual(result.consensus_score, 1.0)
        self.assertFalse(result.needs_debate)

    def test_build_consensus_result_multiple_clusters(self) -> None:
        first = ClusterInfo(cluster_id=0, member_indices=(0, 1, 2), centroid_index=0, size=3, avg_similarity=0.9)
        second = ClusterInfo(cluster_id=1, member_indices=(3, 4), centroid_index=3, size=2, avg_similarity=0.88)
        result = build_consensus_result([first, second], 1, 5, ConsensusConfig())
        self.assertEqual(result.consensus_score, 0.6)
        self.assertTrue(result.needs_debate)

    def test_build_consensus_result_sorts_by_size(self) -> None:
        smaller = ClusterInfo(cluster_id=1, member_indices=(3, 4), centroid_index=3, size=2, avg_similarity=0.88)
        larger = ClusterInfo(cluster_id=0, member_indices=(0, 1, 2), centroid_index=0, size=3, avg_similarity=0.9)
        result = build_consensus_result([smaller, larger], 1, 5, ConsensusConfig())
        self.assertEqual(result.top_cluster, larger)

    def test_build_consensus_result_empty_raises(self) -> None:
        with self.assertRaises(ValueError):
            build_consensus_result([], 1, 0, ConsensusConfig())


if __name__ == "__main__":
    unittest.main()
