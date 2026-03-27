from __future__ import annotations

import unittest

from gracekelly.core.consensus import (
    ClusterInfo,
    ConsensusConfig,
    ConsensusResult,
    build_consensus_result,
    needs_another_round,
)


def _cluster(cluster_id: int = 0, *, size: int = 1, member_indices: tuple[int, ...] | None = None) -> ClusterInfo:
    return ClusterInfo(
        cluster_id=cluster_id,
        member_indices=member_indices if member_indices is not None else tuple(range(size)),
        centroid_index=0,
        size=size,
        avg_similarity=1.0,
    )


def _result(
    *,
    consensus_score: float = 0.9,
    needs_debate: bool = True,
    round_number: int = 1,
    total_responses: int = 3,
) -> ConsensusResult:
    cluster = _cluster(size=total_responses)
    return ConsensusResult(
        consensus_score=consensus_score,
        num_clusters=1,
        top_cluster=cluster,
        all_clusters=(cluster,),
        needs_debate=needs_debate,
        round_number=round_number,
        total_responses=total_responses,
    )


class BuildConsensusResultEdgeCasesTests(unittest.TestCase):
    def test_zero_total_responses_gives_zero_score(self) -> None:
        cluster = _cluster(size=0)
        result = build_consensus_result([cluster], round_number=1, total_responses=0, config=ConsensusConfig())
        self.assertEqual(result.consensus_score, 0.0)

    def test_consensus_score_exactly_at_target_does_not_need_debate(self) -> None:
        """Score exactly equal to consensus_target → needs_debate = False (< is strict)."""
        config = ConsensusConfig(consensus_target=0.9)
        cluster = _cluster(size=9)
        result = build_consensus_result([cluster], round_number=1, total_responses=10, config=config)
        self.assertEqual(result.consensus_score, 0.9)
        self.assertFalse(result.needs_debate)

    def test_consensus_score_just_below_target_needs_debate(self) -> None:
        config = ConsensusConfig(consensus_target=1.0)
        cluster = _cluster(size=9)
        result = build_consensus_result([cluster], round_number=1, total_responses=10, config=config)
        self.assertLess(result.consensus_score, 1.0)
        self.assertTrue(result.needs_debate)

    def test_single_response_perfect_consensus(self) -> None:
        config = ConsensusConfig(consensus_target=0.95)
        cluster = _cluster(size=1)
        result = build_consensus_result([cluster], round_number=1, total_responses=1, config=config)
        self.assertEqual(result.consensus_score, 1.0)
        self.assertFalse(result.needs_debate)

    def test_top_cluster_is_largest(self) -> None:
        small = _cluster(cluster_id=0, size=2)
        large = _cluster(cluster_id=1, size=5)
        result = build_consensus_result([small, large], round_number=1, total_responses=7, config=ConsensusConfig())
        self.assertEqual(result.top_cluster.size, 5)

    def test_all_clusters_sorted_by_size_descending(self) -> None:
        clusters = [_cluster(cluster_id=i, size=i + 1) for i in range(4)]
        result = build_consensus_result(clusters, round_number=1, total_responses=10, config=ConsensusConfig())
        sizes = [c.size for c in result.all_clusters]
        self.assertEqual(sizes, sorted(sizes, reverse=True))

    def test_total_responses_stored(self) -> None:
        cluster = _cluster(size=7)
        result = build_consensus_result([cluster], round_number=3, total_responses=7, config=ConsensusConfig())
        self.assertEqual(result.total_responses, 7)

    def test_round_number_stored(self) -> None:
        cluster = _cluster(size=1)
        result = build_consensus_result([cluster], round_number=4, total_responses=1, config=ConsensusConfig())
        self.assertEqual(result.round_number, 4)

    def test_num_clusters_matches_input_count(self) -> None:
        clusters = [_cluster(cluster_id=i, size=1) for i in range(3)]
        result = build_consensus_result(clusters, round_number=1, total_responses=3, config=ConsensusConfig())
        self.assertEqual(result.num_clusters, 3)


class NeedsAnotherRoundEdgeCasesTests(unittest.TestCase):
    def test_at_max_round_no_more_rounds(self) -> None:
        config = ConsensusConfig(max_rounds=3)
        result = _result(needs_debate=True, round_number=3)
        self.assertFalse(needs_another_round(result, config))

    def test_past_max_round_no_more_rounds(self) -> None:
        config = ConsensusConfig(max_rounds=2)
        result = _result(needs_debate=True, round_number=5)
        self.assertFalse(needs_another_round(result, config))

    def test_converged_at_round_one_no_more_rounds(self) -> None:
        config = ConsensusConfig(max_rounds=5)
        result = _result(needs_debate=False, round_number=1)
        self.assertFalse(needs_another_round(result, config))

    def test_needs_debate_below_max_continues(self) -> None:
        config = ConsensusConfig(max_rounds=5)
        result = _result(needs_debate=True, round_number=2)
        self.assertTrue(needs_another_round(result, config))

    def test_max_rounds_zero_no_continuation(self) -> None:
        config = ConsensusConfig(max_rounds=0)
        result = _result(needs_debate=True, round_number=0)
        self.assertFalse(needs_another_round(result, config))


if __name__ == "__main__":
    unittest.main()
