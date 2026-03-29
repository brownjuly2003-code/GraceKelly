from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from gracekelly.core.confidence import extract_batch_confidence, weighted_vote
from gracekelly.core.consensus import ConsensusConfig, ConsensusResult, needs_another_round
from gracekelly.core.consensus_analyzer import ConsensusAnalyzer
from gracekelly.core.embeddings import EmbeddingsClient
from gracekelly.core.prompt_variations import generate_variations


@dataclass(frozen=True, slots=True)
class ConsensusExecutionConfig:
    consensus_config: ConsensusConfig
    variations_per_round: int = 3
    use_confidence_weighting: bool = True


@dataclass(frozen=True, slots=True)
class ConsensusExecutionResult:
    consensus_result: ConsensusResult
    best_response: str
    all_responses: tuple[str, ...]
    weighted_score: float | None
    total_rounds: int
    total_llm_calls: int


ExecuteFunc = Callable[[str], str]


class ConsensusExecutor:
    def __init__(
        self,
        embeddings_client: EmbeddingsClient,
        config: ConsensusExecutionConfig | None = None,
    ) -> None:
        self._config = config or ConsensusExecutionConfig(
            consensus_config=ConsensusConfig(),
        )
        self._analyzer = ConsensusAnalyzer(
            embeddings_client,
            self._config.consensus_config,
        )

    def execute(
        self,
        prompt: str,
        execute_fn: ExecuteFunc,
    ) -> ConsensusExecutionResult:
        all_responses: list[str] = []
        total_calls = 0
        round_number = 0
        result: ConsensusResult | None = None

        while True:
            round_number += 1
            variations = generate_variations(
                prompt,
                count=self._config.variations_per_round,
            )
            round_responses: list[str] = []
            for variation in variations:
                response = execute_fn(variation)
                round_responses.append(response)
                total_calls += 1

            all_responses.extend(round_responses)
            result = self._analyzer.analyze(all_responses, round_number)

            if not needs_another_round(result, self._config.consensus_config):
                break

        best_idx = result.top_cluster.centroid_index
        best_response = all_responses[best_idx]

        weighted_score: float | None = None
        if self._config.use_confidence_weighting:
            scores = extract_batch_confidence(all_responses)
            weighted_score = weighted_vote(
                list(result.top_cluster.member_indices),
                scores,
                result.total_responses,
            )

        return ConsensusExecutionResult(
            consensus_result=result,
            best_response=best_response,
            all_responses=tuple(all_responses),
            weighted_score=weighted_score,
            total_rounds=round_number,
            total_llm_calls=total_calls,
        )
