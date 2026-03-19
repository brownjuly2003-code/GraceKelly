from __future__ import annotations

import os
import sys
import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(__file__))

from gracekelly.core.consensus import ConsensusConfig, ConsensusResult
from gracekelly.core.embeddings import EmbeddingsClient
from consensus_execution import ConsensusExecutor, ConsensusExecutionConfig, ConsensusExecutionResult


def _make_mock_embeddings(embedding: list[float]) -> EmbeddingsClient:
    client = MagicMock(spec=EmbeddingsClient)
    client.embed.return_value = embedding
    client.embed_batch.side_effect = lambda texts: [embedding for _ in texts]
    return client


def _make_divergent_embeddings() -> EmbeddingsClient:
    call_count = {"n": 0}
    vectors = [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
        [1.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
    ]
    client = MagicMock(spec=EmbeddingsClient)

    def embed_batch(texts):
        result = []
        for _ in texts:
            idx = min(call_count["n"], len(vectors) - 1)
            result.append(vectors[idx])
            call_count["n"] += 1
        return result

    client.embed_batch.side_effect = embed_batch
    return client


class ConsensusExecutionTests(unittest.TestCase):
    def test_single_round_converges(self) -> None:
        executor = ConsensusExecutor(_make_mock_embeddings([1.0, 0.0, 0.0]))
        result = executor.execute("prompt", lambda text: f"Response to {text}")
        self.assertEqual(result.total_rounds, 1)
        self.assertEqual(result.consensus_result.consensus_score, 1.0)

    def test_best_response_is_centroid(self) -> None:
        executor = ConsensusExecutor(_make_mock_embeddings([1.0, 0.0, 0.0]))
        result = executor.execute("prompt", lambda text: f"Response to {text}")
        self.assertIn(result.best_response, result.all_responses)

    def test_total_llm_calls_equals_variations(self) -> None:
        executor = ConsensusExecutor(_make_mock_embeddings([1.0, 0.0, 0.0]))
        result = executor.execute("prompt", lambda text: f"Response to {text}")
        self.assertEqual(result.total_llm_calls, 3)

    def test_execute_fn_called_with_variations(self) -> None:
        executor = ConsensusExecutor(_make_mock_embeddings([1.0, 0.0, 0.0]))
        seen: list[str] = []

        def execute_fn(text: str) -> str:
            seen.append(text)
            return f"Response to {text}"

        executor.execute("prompt", execute_fn)
        self.assertGreater(len(set(seen)), 1)

    def test_weighted_score_present(self) -> None:
        executor = ConsensusExecutor(_make_mock_embeddings([1.0, 0.0, 0.0]))
        result = executor.execute("prompt", lambda text: "Confidence: 8/10")
        self.assertIsNotNone(result.weighted_score)

    def test_weighted_score_absent(self) -> None:
        executor = ConsensusExecutor(
            _make_mock_embeddings([1.0, 0.0, 0.0]),
            ConsensusExecutionConfig(
                consensus_config=ConsensusConfig(),
                use_confidence_weighting=False,
            ),
        )
        result = executor.execute("prompt", lambda text: "Confidence: 8/10")
        self.assertIsNone(result.weighted_score)

    def test_all_responses_collected(self) -> None:
        executor = ConsensusExecutor(_make_mock_embeddings([1.0, 0.0, 0.0]))
        result = executor.execute("prompt", lambda text: f"Response to {text}")
        self.assertEqual(len(result.all_responses), 3)

    def test_result_is_frozen(self) -> None:
        executor = ConsensusExecutor(_make_mock_embeddings([1.0, 0.0, 0.0]))
        result = executor.execute("prompt", lambda text: f"Response to {text}")
        with self.assertRaises(FrozenInstanceError):
            result.best_response = "x"  # type: ignore[misc]

    def test_multiple_rounds_with_divergent(self) -> None:
        executor = ConsensusExecutor(
            _make_divergent_embeddings(),
            ConsensusExecutionConfig(
                consensus_config=ConsensusConfig(max_rounds=2),
            ),
        )
        result = executor.execute("prompt", lambda text: f"Response to {text}")
        self.assertGreater(result.total_rounds, 1)

    def test_custom_variations_count(self) -> None:
        executor = ConsensusExecutor(
            _make_mock_embeddings([1.0, 0.0, 0.0]),
            ConsensusExecutionConfig(
                consensus_config=ConsensusConfig(),
                variations_per_round=5,
            ),
        )
        result = executor.execute("prompt", lambda text: f"Response to {text}")
        self.assertEqual(result.total_llm_calls, 5)

    def test_consensus_result_accessible(self) -> None:
        executor = ConsensusExecutor(_make_mock_embeddings([1.0, 0.0, 0.0]))
        result = executor.execute("prompt", lambda text: f"Response to {text}")
        self.assertIsInstance(result.consensus_result, ConsensusResult)
        self.assertEqual(result.consensus_result.num_clusters, 1)

    def test_returns_consensus_execution_result(self) -> None:
        executor = ConsensusExecutor(_make_mock_embeddings([1.0, 0.0, 0.0]))
        result = executor.execute("prompt", lambda text: f"Response to {text}")
        self.assertIsInstance(result, ConsensusExecutionResult)


if __name__ == "__main__":
    unittest.main()
