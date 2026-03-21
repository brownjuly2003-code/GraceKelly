from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from gracekelly.core.adaptive_params import AdaptiveConsensusParams, get_adaptive_params
from gracekelly.core.cluster_confidence import compute_cluster_confidence
from gracekelly.core.clustering_hac import hac_cluster
from gracekelly.core.consensus import ClusterInfo, ConsensusResult
from gracekelly.core.cross_pollination import cross_pollinate
from gracekelly.core.debate_round import run_debate
from gracekelly.core.divergence import DivergenceAction, assess_divergence
from gracekelly.core.similarity import cosine_similarity
from gracekelly.core.task_classifier import classify_task


@dataclass(frozen=True, slots=True)
class ConsensusV2Config:
    use_adaptive_params: bool = True
    use_debate: bool = True
    use_cross_pollination: bool = True
    use_cluster_confidence: bool = True
    use_divergence_handling: bool = True


@dataclass(frozen=True, slots=True)
class DissentingView:
    perspective: str
    support_ratio: float


@dataclass(frozen=True, slots=True)
class ConsensusV2FinalResult:
    status: DivergenceAction
    dissenting_views: tuple[DissentingView, ...]


@dataclass(frozen=True, slots=True)
class ConsensusV2Result:
    best_response: str
    consensus_result: ConsensusResult
    weighted_score: float
    total_rounds: int
    final_result: ConsensusV2FinalResult


def _build_cluster_infos(
    hac_clusters: tuple[tuple[int, ...], ...],
    sim_matrix: list[list[float]],
) -> tuple[list[ClusterInfo], tuple[int, ...]]:
    infos: list[ClusterInfo] = []
    top_members: tuple[int, ...] = ()
    best_size = 0
    for cid, members in enumerate(hac_clusters):
        if len(members) <= 1:
            avg_sim = 1.0
        else:
            total = 0.0
            count = 0
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    total += sim_matrix[members[i]][members[j]]
                    count += 1
            avg_sim = total / count if count > 0 else 0.0

        centroid_idx = members[0]
        best_sum = -1.0
        for m in members:
            s = sum(sim_matrix[m][o] for o in members)
            if s > best_sum:
                best_sum = s
                centroid_idx = m

        info = ClusterInfo(
            cluster_id=cid,
            member_indices=members,
            centroid_index=centroid_idx,
            size=len(members),
            avg_similarity=avg_sim,
        )
        infos.append(info)
        if len(members) > best_size:
            best_size = len(members)
            top_members = members
    return infos, top_members


class ConsensusExecutorV2:
    def __init__(
        self, embeddings_client: object, config: ConsensusV2Config | None = None
    ):
        self._embeddings = embeddings_client
        self._config = config or ConsensusV2Config()

    def execute(
        self, prompt: str, execute_fn: Callable[[str], str]
    ) -> ConsensusV2Result:
        task_type = classify_task(prompt)

        if self._config.use_adaptive_params:
            params = get_adaptive_params(task_type)
        else:
            params = AdaptiveConsensusParams(0.85, 3, 3, True, False)

        all_responses: list[str] = []
        total_rounds = 0

        for round_num in range(params.max_rounds):
            total_rounds += 1
            new_responses = [execute_fn(prompt) for _ in range(params.min_responses)]
            all_responses.extend(new_responses)

            embeddings = self._embeddings.embed_batch(all_responses)
            n = len(embeddings)
            sim_matrix = [[0.0] * n for _ in range(n)]
            for i in range(n):
                for j in range(n):
                    sim_matrix[i][j] = cosine_similarity(embeddings[i], embeddings[j])

            hac_result = hac_cluster(sim_matrix)

            if self._config.use_cluster_confidence:
                conf_result = compute_cluster_confidence(
                    hac_result.clusters, sim_matrix
                )
                consensus_score = conf_result.confidence
            else:
                top_cluster = (
                    max(hac_result.clusters, key=len)
                    if hac_result.clusters
                    else ()
                )
                consensus_score = len(top_cluster) / n if n > 0 else 0.0

            if self._config.use_divergence_handling:
                div_result = assess_divergence(
                    consensus_score,
                    hac_result.num_clusters,
                    round_num,
                    params.max_rounds,
                )
                if div_result.action == DivergenceAction.ACCEPT:
                    break
                if (
                    div_result.action == DivergenceAction.DEBATE
                    and self._config.use_debate
                    and params.use_debate
                ):
                    top_cluster = max(hac_result.clusters, key=len)
                    debate_result = run_debate(
                        prompt, all_responses[top_cluster[0]], execute_fn
                    )
                    all_responses[top_cluster[0]] = debate_result.improved_response
                    break
                if div_result.action == DivergenceAction.ESCALATE:
                    break
            elif consensus_score >= params.consensus_target:
                break

        embeddings = self._embeddings.embed_batch(all_responses)
        n = len(embeddings)
        sim_matrix = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                sim_matrix[i][j] = cosine_similarity(embeddings[i], embeddings[j])

        hac_result = hac_cluster(sim_matrix)
        conf_result = compute_cluster_confidence(hac_result.clusters, sim_matrix)

        cluster_infos, top_members = _build_cluster_infos(
            hac_result.clusters, sim_matrix
        )
        sorted_infos = sorted(cluster_infos, key=lambda c: c.size, reverse=True)
        top_info = sorted_infos[0] if sorted_infos else ClusterInfo(
            cluster_id=0,
            member_indices=(0,),
            centroid_index=0,
            size=1,
            avg_similarity=1.0,
        )

        best_idx = top_info.centroid_index
        best_response = all_responses[best_idx] if all_responses else ""

        top_set = set(top_info.member_indices)
        dissenting: list[DissentingView] = []
        for info in sorted_infos:
            if set(info.member_indices) != top_set and info.member_indices:
                ratio = info.size / len(all_responses) if all_responses else 0.0
                dissenting.append(
                    DissentingView(
                        perspective=all_responses[info.member_indices[0]][:500],
                        support_ratio=ratio,
                    )
                )

        consensus_result = ConsensusResult(
            consensus_score=conf_result.confidence,
            num_clusters=hac_result.num_clusters,
            top_cluster=top_info,
            all_clusters=tuple(sorted_infos),
            needs_debate=conf_result.confidence < 0.7,
            round_number=total_rounds,
            total_responses=len(all_responses),
        )

        return ConsensusV2Result(
            best_response=best_response,
            consensus_result=consensus_result,
            weighted_score=conf_result.confidence,
            total_rounds=total_rounds,
            final_result=ConsensusV2FinalResult(
                status=(
                    DivergenceAction.ACCEPT
                    if conf_result.confidence >= 0.9
                    else DivergenceAction.ESCALATE
                ),
                dissenting_views=tuple(dissenting),
            ),
        )
