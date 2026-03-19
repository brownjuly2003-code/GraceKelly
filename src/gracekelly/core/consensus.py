from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConsensusConfig:
    similarity_threshold: float = 0.85
    consensus_target: float = 0.95
    max_rounds: int = 5
    variations_per_round: int = 3
    enable_peer_review: bool = False
    enable_confidence: bool = True


@dataclass(frozen=True, slots=True)
class ClusterInfo:
    cluster_id: int
    member_indices: tuple[int, ...]
    centroid_index: int
    size: int
    avg_similarity: float


@dataclass(frozen=True, slots=True)
class ConsensusResult:
    consensus_score: float
    num_clusters: int
    top_cluster: ClusterInfo
    all_clusters: tuple[ClusterInfo, ...]
    needs_debate: bool
    round_number: int
    total_responses: int


def needs_another_round(result: ConsensusResult, config: ConsensusConfig) -> bool:
    return (
        result.needs_debate
        and result.round_number < config.max_rounds
    )


def build_consensus_result(
    clusters: list[ClusterInfo],
    round_number: int,
    total_responses: int,
    config: ConsensusConfig,
) -> ConsensusResult:
    if not clusters:
        raise ValueError("At least one cluster is required.")
    sorted_clusters = sorted(clusters, key=lambda c: c.size, reverse=True)
    top = sorted_clusters[0]
    consensus_score = top.size / total_responses if total_responses > 0 else 0.0
    return ConsensusResult(
        consensus_score=consensus_score,
        num_clusters=len(clusters),
        top_cluster=top,
        all_clusters=tuple(sorted_clusters),
        needs_debate=consensus_score < config.consensus_target,
        round_number=round_number,
        total_responses=total_responses,
    )
