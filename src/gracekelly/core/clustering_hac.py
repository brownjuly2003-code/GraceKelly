from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HacResult:
    clusters: tuple[tuple[int, ...], ...]
    num_clusters: int
    merge_history: tuple[tuple[int, int, float], ...]


def hac_cluster(
    similarity_matrix: list[list[float]], threshold: float = 0.85
) -> HacResult:
    n = len(similarity_matrix)
    if n == 0:
        return HacResult(clusters=(), num_clusters=0, merge_history=())

    cluster_map: dict[int, list[int]] = {i: [i] for i in range(n)}
    active = set(range(n))
    merges: list[tuple[int, int, float]] = []

    while len(active) > 1:
        best_sim = -1.0
        best_pair = (-1, -1)
        active_list = sorted(active)
        for i_idx in range(len(active_list)):
            for j_idx in range(i_idx + 1, len(active_list)):
                ci, cj = active_list[i_idx], active_list[j_idx]
                sim = _avg_linkage(cluster_map[ci], cluster_map[cj], similarity_matrix)
                if sim > best_sim:
                    best_sim = sim
                    best_pair = (ci, cj)

        if best_sim < threshold:
            break

        ci, cj = best_pair
        cluster_map[ci] = cluster_map[ci] + cluster_map[cj]
        del cluster_map[cj]
        active.remove(cj)
        merges.append((ci, cj, best_sim))

    clusters = tuple(tuple(sorted(v)) for v in cluster_map.values())
    return HacResult(
        clusters=clusters, num_clusters=len(clusters), merge_history=tuple(merges)
    )


def _avg_linkage(
    c1: list[int], c2: list[int], sim_matrix: list[list[float]]
) -> float:
    total = 0.0
    count = 0
    for i in c1:
        for j in c2:
            total += sim_matrix[i][j]
            count += 1
    return total / count if count > 0 else 0.0
