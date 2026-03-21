from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ClusterConfidenceResult:
    top_cluster_size: int
    total_responses: int
    raw_ratio: float
    avg_intra_similarity: float
    confidence: float
    is_unanimous: bool


def compute_cluster_confidence(
    clusters: tuple[tuple[int, ...], ...],
    similarity_matrix: list[list[float]],
) -> ClusterConfidenceResult:
    if not clusters:
        return ClusterConfidenceResult(0, 0, 0.0, 0.0, 0.0, False)

    top = max(clusters, key=len)
    total = sum(len(c) for c in clusters)
    ratio = len(top) / total if total > 0 else 0.0

    intra_sim = _avg_intra_similarity(top, similarity_matrix)
    confidence = ratio * intra_sim
    is_unanimous = len(clusters) == 1

    return ClusterConfidenceResult(
        top_cluster_size=len(top),
        total_responses=total,
        raw_ratio=ratio,
        avg_intra_similarity=intra_sim,
        confidence=confidence,
        is_unanimous=is_unanimous,
    )


def _avg_intra_similarity(
    cluster: tuple[int, ...], sim_matrix: list[list[float]]
) -> float:
    if len(cluster) <= 1:
        return 1.0
    total = 0.0
    count = 0
    for i in range(len(cluster)):
        for j in range(i + 1, len(cluster)):
            total += sim_matrix[cluster[i]][cluster[j]]
            count += 1
    return total / count if count > 0 else 0.0
