from __future__ import annotations

import math


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"Vector length mismatch: {len(a)} vs {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def pairwise_similarity_matrix(
    vectors: list[list[float]],
) -> list[list[float]]:
    n = len(vectors)
    matrix: list[list[float]] = []
    for i in range(n):
        row: list[float] = []
        for j in range(n):
            if i == j:
                row.append(1.0)
            elif j < i:
                row.append(matrix[j][i])
            else:
                row.append(cosine_similarity(vectors[i], vectors[j]))
        matrix.append(row)
    return matrix


def find_clusters_greedy(
    vectors: list[list[float]],
    threshold: float = 0.85,
) -> list[list[int]]:
    n = len(vectors)
    if n == 0:
        return []
    matrix = pairwise_similarity_matrix(vectors)
    assigned: set[int] = set()
    clusters: list[list[int]] = []
    for i in range(n):
        if i in assigned:
            continue
        cluster = [i]
        assigned.add(i)
        for j in range(i + 1, n):
            if j in assigned:
                continue
            if matrix[i][j] >= threshold:
                cluster.append(j)
                assigned.add(j)
        clusters.append(cluster)
    return clusters
