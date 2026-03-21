from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WeightedScore:
    raw_score: float
    weighted_score: float
    total_weight: float
    round_weights: tuple[float, ...]


def round_weight(round_number: int, decay_base: float = 0.8) -> float:
    return decay_base**round_number


def weighted_cluster_size(
    cluster_indices: tuple[int, ...],
    response_rounds: tuple[int, ...],
    decay_base: float = 0.8,
) -> float:
    return sum(
        round_weight(response_rounds[i], decay_base) for i in cluster_indices
    )


def consensus_score_weighted(
    top_cluster_indices: tuple[int, ...],
    all_indices: tuple[int, ...],
    response_rounds: tuple[int, ...],
    decay_base: float = 0.8,
) -> WeightedScore:
    top_weight = weighted_cluster_size(
        top_cluster_indices, response_rounds, decay_base
    )
    total_weight = sum(
        round_weight(response_rounds[i], decay_base) for i in all_indices
    )

    weights = tuple(
        round_weight(response_rounds[i], decay_base) for i in all_indices
    )

    if total_weight == 0:
        return WeightedScore(0.0, 0.0, 0.0, weights)

    raw = (
        len(top_cluster_indices) / len(all_indices) if all_indices else 0.0
    )
    weighted = top_weight / total_weight

    return WeightedScore(raw, weighted, total_weight, weights)
