# 020: Cosine Similarity — TODO

Phase 6 (Consensus Engine). Dependency: none.
Complexity: routine | Runs: 1

```
## GOAL
Create a pure-Python cosine similarity module (no numpy/sklearn). Two new files: `src/gracekelly/core/similarity.py` and `tests/test_similarity.py`.

## CONTEXT
Files to CREATE:
- `src/gracekelly/core/similarity.py` — cosine similarity functions
- `tests/test_similarity.py` — unit tests

Files to READ (do NOT modify):
- `src/gracekelly/core/consensus.py` — will use similarity downstream for clustering

Architecture:
- Python >=3.11, NO external dependencies (no numpy, no sklearn, no scipy)
- Pure math using stdlib `math.sqrt`
- All files start with `from __future__ import annotations`
- Tests use `unittest.TestCase`
- Test runner: `python -m pytest tests/test_similarity.py -q`

## CONSTRAINTS
- Create ONLY the two files listed above. Do NOT modify any existing files.
- Follow these instructions EXACTLY. Do NOT deviate, improve, or "enhance".
- Do NOT import numpy, scipy, sklearn, or any external package.
- Do NOT add: logging, comments, docstrings, type guards beyond the ValueError specified.
- Preserve project code style: 4-space indentation, snake_case, `from __future__ import annotations`.

### similarity.py specification

```python
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
```

That is the COMPLETE implementation. Copy it exactly.

### test_similarity.py specification

Exactly these tests:

1. `test_identical_vectors` — cosine_similarity([1,0,0], [1,0,0]) == 1.0
2. `test_orthogonal_vectors` — cosine_similarity([1,0], [0,1]) == 0.0
3. `test_opposite_vectors` — cosine_similarity([1,0], [-1,0]) == -1.0
4. `test_similar_vectors` — cosine_similarity([1,2,3], [1,2,4]) > 0.99
5. `test_length_mismatch_raises` — cosine_similarity([1,2], [1,2,3]) raises ValueError
6. `test_zero_vector_returns_zero` — cosine_similarity([0,0,0], [1,2,3]) == 0.0
7. `test_pairwise_matrix_diagonal_is_ones` — all diagonal elements == 1.0
8. `test_pairwise_matrix_is_symmetric` — matrix[i][j] == matrix[j][i]
9. `test_pairwise_matrix_size` — 3 vectors → 3x3 matrix
10. `test_find_clusters_identical` — 3 identical vectors → 1 cluster of size 3
11. `test_find_clusters_distinct` — 3 orthogonal vectors → 3 clusters of size 1
12. `test_find_clusters_empty` — find_clusters_greedy([]) == []
13. `test_find_clusters_threshold` — 2 similar + 1 different → 2 clusters (sizes 2 and 1)
14. `test_find_clusters_all_assigned` — sum of all cluster sizes == number of vectors

End with:
```python
if __name__ == "__main__":
    unittest.main()
```

## DONE WHEN
- [ ] `src/gracekelly/core/similarity.py` exists with cosine_similarity(), pairwise_similarity_matrix(), find_clusters_greedy()
- [ ] `tests/test_similarity.py` exists with exactly 14 test methods
- [ ] `python -m pytest tests/test_similarity.py -q` → 14 passed, 0 failed
- [ ] `python -m pytest -q` → all existing tests still pass (541+)
- [ ] No external dependencies (no numpy, sklearn, scipy)
- [ ] No other files created or modified

## SELF-EVALUATION
After completing, score yourself 1-10:
- Is the implementation EXACTLY as specified?
- Are all 14 tests present? Do the math assertions use correct expected values?
- Is there any import of numpy/sklearn/scipy? (there should NOT be)
- Is there any code beyond the specification?

If your self-score is below 9.8/10, fix issues before submitting. Target: 9.8/10.
```
