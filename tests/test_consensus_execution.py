from __future__ import annotations

import dataclasses
import unittest
import unittest.mock

from gracekelly.core.consensus import ConsensusConfig
from gracekelly.core.consensus_execution import (
    ConsensusExecutionConfig,
    ConsensusExecutionResult,
    ConsensusExecutor,
)
from gracekelly.core.embeddings import EmbeddingsClient


def _identical_client() -> EmbeddingsClient:
    """Returns identical embeddings for all inputs → consensus in round 1."""
    client = unittest.mock.MagicMock(spec=EmbeddingsClient)
    client.embed_batch.side_effect = lambda texts: [[1.0, 0.0]] * len(texts)
    return client


def _two_round_client() -> EmbeddingsClient:
    """Round 1 (3 texts): diverse → no consensus. Round 2+ (6+ texts): identical → consensus."""
    calls: list[int] = [0]

    def embed_batch(texts: list[str]) -> list[list[float]]:
        calls[0] += 1
        if calls[0] == 1:
            return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        return [[1.0, 0.0, 0.0]] * len(texts)

    client = unittest.mock.MagicMock(spec=EmbeddingsClient)
    client.embed_batch.side_effect = embed_batch
    return client


def _always_diverse_client() -> EmbeddingsClient:
    """Always returns orthogonal embeddings → consensus never reached naturally."""

    def embed_batch(texts: list[str]) -> list[list[float]]:
        n = len(texts)
        dim = max(n, 3)
        result = []
        for i in range(n):
            vec = [0.0] * dim
            vec[i % dim] = 1.0
            result.append(vec)
        return result

    client = unittest.mock.MagicMock(spec=EmbeddingsClient)
    client.embed_batch.side_effect = embed_batch
    return client


class ConsensusExecutorTests(unittest.TestCase):
    def test_single_round_consensus(self) -> None:
        executor = ConsensusExecutor(
            _identical_client(),
            ConsensusExecutionConfig(
                consensus_config=ConsensusConfig(max_rounds=5),
                variations_per_round=3,
            ),
        )
        calls: list[str] = []
        result = executor.execute("What is 2+2?", lambda p: calls.append(p) or "Four")  # type: ignore[func-returns-value]
        self.assertIsInstance(result, ConsensusExecutionResult)
        self.assertEqual(result.total_rounds, 1)
        self.assertEqual(result.total_llm_calls, 3)
        self.assertEqual(len(result.all_responses), 3)
        self.assertEqual(result.best_response, "Four")

    def test_two_rounds_to_consensus(self) -> None:
        executor = ConsensusExecutor(
            _two_round_client(),
            ConsensusExecutionConfig(
                consensus_config=ConsensusConfig(max_rounds=5),
                variations_per_round=3,
            ),
        )
        result = executor.execute("Test prompt", lambda _p: "ok")
        self.assertEqual(result.total_rounds, 2)
        self.assertEqual(result.total_llm_calls, 6)
        self.assertEqual(len(result.all_responses), 6)

    def test_max_rounds_stops_iteration(self) -> None:
        max_rounds = 2
        executor = ConsensusExecutor(
            _always_diverse_client(),
            ConsensusExecutionConfig(
                consensus_config=ConsensusConfig(max_rounds=max_rounds),
                variations_per_round=3,
            ),
        )
        result = executor.execute("Test", lambda _p: "response")
        self.assertEqual(result.total_rounds, max_rounds)
        self.assertEqual(result.total_llm_calls, max_rounds * 3)

    def test_variations_per_round_respected(self) -> None:
        executor = ConsensusExecutor(
            _identical_client(),
            ConsensusExecutionConfig(
                consensus_config=ConsensusConfig(max_rounds=1),
                variations_per_round=2,
            ),
        )
        result = executor.execute("Test", lambda _p: "response")
        self.assertEqual(result.total_llm_calls, 2)
        self.assertEqual(len(result.all_responses), 2)

    def test_confidence_weighting_enabled(self) -> None:
        executor = ConsensusExecutor(
            _identical_client(),
            ConsensusExecutionConfig(
                consensus_config=ConsensusConfig(max_rounds=1),
                variations_per_round=3,
                use_confidence_weighting=True,
            ),
        )
        result = executor.execute("Test", lambda _p: "Answer. Confidence: 8/10")
        assert result.weighted_score is not None
        self.assertGreaterEqual(result.weighted_score, 0.0)
        self.assertLessEqual(result.weighted_score, 1.0)

    def test_confidence_weighting_disabled(self) -> None:
        executor = ConsensusExecutor(
            _identical_client(),
            ConsensusExecutionConfig(
                consensus_config=ConsensusConfig(max_rounds=1),
                variations_per_round=3,
                use_confidence_weighting=False,
            ),
        )
        result = executor.execute("Test", lambda _p: "response")
        self.assertIsNone(result.weighted_score)

    def test_default_config_used_when_none(self) -> None:
        executor = ConsensusExecutor(_identical_client())
        result = executor.execute("What is AI?", lambda _p: "response")
        self.assertGreaterEqual(result.total_rounds, 1)
        self.assertGreaterEqual(result.total_llm_calls, 1)

    def test_all_responses_is_tuple(self) -> None:
        executor = ConsensusExecutor(
            _identical_client(),
            ConsensusExecutionConfig(
                consensus_config=ConsensusConfig(max_rounds=1),
                variations_per_round=3,
            ),
        )
        result = executor.execute("Test", lambda _p: "r")
        self.assertIsInstance(result.all_responses, tuple)

    def test_consensus_result_attached(self) -> None:
        executor = ConsensusExecutor(
            _identical_client(),
            ConsensusExecutionConfig(
                consensus_config=ConsensusConfig(max_rounds=1),
                variations_per_round=3,
            ),
        )
        result = executor.execute("Test", lambda _p: "response")
        self.assertIsNotNone(result.consensus_result)
        self.assertGreater(result.consensus_result.consensus_score, 0.0)

    def test_execute_fn_receives_prompt_variations(self) -> None:
        received: list[str] = []
        executor = ConsensusExecutor(
            _identical_client(),
            ConsensusExecutionConfig(
                consensus_config=ConsensusConfig(max_rounds=1),
                variations_per_round=3,
            ),
        )
        executor.execute("Test prompt", lambda p: received.append(p) or "r")  # type: ignore[func-returns-value]
        self.assertEqual(len(received), 3)
        self.assertTrue(all("Test prompt" in v for v in received))

    def test_result_is_frozen_dataclass(self) -> None:
        executor = ConsensusExecutor(
            _identical_client(),
            ConsensusExecutionConfig(
                consensus_config=ConsensusConfig(max_rounds=1),
                variations_per_round=2,
            ),
        )
        result = executor.execute("Test", lambda _p: "response")
        with self.assertRaises((AttributeError, TypeError, dataclasses.FrozenInstanceError)):
            result.total_rounds = 99


if __name__ == "__main__":
    unittest.main()
