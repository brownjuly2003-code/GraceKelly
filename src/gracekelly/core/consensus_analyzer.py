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
