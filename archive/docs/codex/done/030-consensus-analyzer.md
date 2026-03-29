# 030: Consensus Analyzer — TODO

Phase 6 (Consensus Engine). Dependency: 010-embeddings-client, 020-cosine-similarity.
Complexity: moderate | Runs: 2

```
## GOAL
Create a ConsensusAnalyzer that takes text responses, embeds them, clusters by similarity, and produces a ConsensusResult. Two new files: `src/gracekelly/core/consensus_analyzer.py` and `tests/test_consensus_analyzer.py`.

## CONTEXT
Files to CREATE:
- `src/gracekelly/core/consensus_analyzer.py` — analyzer logic
- `tests/test_consensus_analyzer.py` — unit tests (mock EmbeddingsClient)

Files to READ (do NOT modify):
- `src/gracekelly/core/consensus.py` — ConsensusConfig, ClusterInfo, ConsensusResult, build_consensus_result()
- `src/gracekelly/core/similarity.py` — cosine_similarity(), find_clusters_greedy(), pairwise_similarity_matrix()
- `src/gracekelly/core/embeddings.py` — EmbeddingsClient

Architecture:
- Python >=3.11, no external dependencies
- Imports from gracekelly.core.consensus, gracekelly.core.similarity, gracekelly.core.embeddings
- Tests mock EmbeddingsClient.embed to avoid real API calls
- Tests use `unittest.TestCase` with `unittest.mock`
- Test runner: `python -m pytest tests/test_consensus_analyzer.py -q`

## CONSTRAINTS
- Create ONLY the two files listed above. Do NOT modify any existing files.
- Follow these instructions EXACTLY. Do NOT deviate, improve, or "enhance".
- Do NOT add: logging, comments, docstrings, retry logic, async support.
- Do NOT import numpy, sklearn, or any external package.
- Preserve project code style: 4-space indentation, snake_case, `from __future__ import annotations`.

### consensus_analyzer.py specification

```python
from __future__ import annotations

from gracekelly.core.consensus import (
    ClusterInfo,
    ConsensusConfig,
    ConsensusResult,
    build_consensus_result,
)
from gracekelly.core.embeddings import EmbeddingsClient
from gracekelly.core.similarity import (
    find_clusters_greedy,
    pairwise_similarity_matrix,
)


class ConsensusAnalyzer:
    def __init__(
        self,
        embeddings_client: EmbeddingsClient,
        config: ConsensusConfig | None = None,
    ) -> None:
        self._embeddings = embeddings_client
        self._config = config or ConsensusConfig()

    @property
    def config(self) -> ConsensusConfig:
        return self._config

    def analyze(
        self,
        responses: list[str],
        round_number: int = 1,
    ) -> ConsensusResult:
        if not responses:
            raise ValueError("At least one response is required.")

        embeddings = self._embeddings.embed_batch(responses)
        raw_clusters = find_clusters_greedy(
            embeddings,
            threshold=self._config.similarity_threshold,
        )

        matrix = pairwise_similarity_matrix(embeddings)
        cluster_infos: list[ClusterInfo] = []

        for cluster_id, member_indices in enumerate(raw_clusters):
            avg_sim = self._avg_intra_similarity(member_indices, matrix)
            centroid_idx = self._find_centroid(member_indices, matrix)
            cluster_infos.append(
                ClusterInfo(
                    cluster_id=cluster_id,
                    member_indices=tuple(member_indices),
                    centroid_index=centroid_idx,
                    size=len(member_indices),
                    avg_similarity=round(avg_sim, 4),
                )
            )

        return build_consensus_result(
            clusters=cluster_infos,
            round_number=round_number,
            total_responses=len(responses),
            config=self._config,
        )

    @staticmethod
    def _avg_intra_similarity(
        indices: list[int],
        matrix: list[list[float]],
    ) -> float:
        if len(indices) <= 1:
            return 1.0
        total = 0.0
        count = 0
        for i, idx_i in enumerate(indices):
            for idx_j in indices[i + 1:]:
                total += matrix[idx_i][idx_j]
                count += 1
        return total / count if count > 0 else 1.0

    @staticmethod
    def _find_centroid(
        indices: list[int],
        matrix: list[list[float]],
    ) -> int:
        if len(indices) == 1:
            return indices[0]
        best_idx = indices[0]
        best_sum = -1.0
        for idx in indices:
            sim_sum = sum(matrix[idx][other] for other in indices if other != idx)
            if sim_sum > best_sum:
                best_sum = sim_sum
                best_idx = idx
        return best_idx
```

That is the COMPLETE implementation. Copy it exactly.

### test_consensus_analyzer.py specification

Exactly these tests, using `unittest.mock.patch` or mock EmbeddingsClient:

Create a mock embeddings client:
```python
def _make_mock_client(embeddings_map: dict[str, list[float]]) -> EmbeddingsClient:
    client = unittest.mock.MagicMock(spec=EmbeddingsClient)
    client.embed.side_effect = lambda text: embeddings_map[text]
    client.embed_batch.side_effect = lambda texts: [embeddings_map[t] for t in texts]
    return client
```

1. `test_single_response` — 1 response → consensus_score=1.0, num_clusters=1
2. `test_identical_responses` — 3 identical embeddings → 1 cluster, consensus_score=1.0
3. `test_distinct_responses` — 3 orthogonal embeddings → 3 clusters, consensus_score ≈ 0.33
4. `test_two_similar_one_different` — 2 similar + 1 different → 2 clusters, top_cluster.size=2
5. `test_needs_debate_true` — consensus_score < 0.95 → needs_debate=True
6. `test_needs_debate_false` — all identical → needs_debate=False
7. `test_round_number_passed_through` — round_number=3 → result.round_number=3
8. `test_centroid_is_most_central` — centroid_index is in member_indices of top cluster
9. `test_empty_responses_raises` — analyze([]) raises ValueError
10. `test_custom_config_threshold` — ConsensusConfig(similarity_threshold=0.99) → more clusters for same data
11. `test_avg_similarity_single_member` — single-member cluster has avg_similarity=1.0
12. `test_cluster_infos_have_correct_ids` — cluster_ids are sequential (0, 1, 2, ...)

End with:
```python
if __name__ == "__main__":
    unittest.main()
```

## DONE WHEN
- [ ] `src/gracekelly/core/consensus_analyzer.py` exists with ConsensusAnalyzer class
- [ ] `tests/test_consensus_analyzer.py` exists with exactly 12 test methods
- [ ] `python -m pytest tests/test_consensus_analyzer.py -q` → 12 passed, 0 failed
- [ ] `python -m pytest -q` → all existing tests still pass (541+)
- [ ] No real API calls in tests
- [ ] No other files created or modified

## SELF-EVALUATION
After completing, score yourself 1-10:
- Is the implementation EXACTLY as specified?
- Are all 12 tests present with correct mock setup?
- Does the mock client use spec=EmbeddingsClient?
- Is there any code beyond the specification?

If your self-score is below 9.8/10, fix issues before submitting. Target: 9.8/10.
```
