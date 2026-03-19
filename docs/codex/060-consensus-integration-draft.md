# 060: Consensus Integration Draft (SANDBOX) — TODO

Phase 6 integration test. NOT production code — writes to `docs/codex/drafts/`.
Complexity: complex | Runs: 2, pick best

```
## GOAL
Create a DRAFT integration module that demonstrates how the consensus engine would wire into the execution pipeline. This is a sandbox experiment — files go in `docs/codex/drafts/`, NOT in `src/`. Two new files: `docs/codex/drafts/consensus_execution.py` and `docs/codex/drafts/test_consensus_execution.py`.

## CONTEXT
Files to CREATE:
- `docs/codex/drafts/consensus_execution.py` — draft integration module
- `docs/codex/drafts/test_consensus_execution.py` — tests (all mocked, no real API)

Files to READ (do NOT modify):
- `src/gracekelly/core/router.py` — ExecutionRouter, how execute() works, _aggregate(), merge strategies
- `src/gracekelly/core/contracts.py` — ExecutionPlan, ExecutionBatchResult, MergeStrategy, ExecutionResult, StepStatus
- `src/gracekelly/core/consensus.py` — ConsensusConfig, ConsensusResult, build_consensus_result, needs_another_round
- `src/gracekelly/core/consensus_analyzer.py` — ConsensusAnalyzer.analyze()
- `src/gracekelly/core/prompt_variations.py` — generate_variations()
- `src/gracekelly/core/confidence.py` — extract_batch_confidence(), weighted_vote()
- `src/gracekelly/core/peer_review.py` — anonymize_responses(), format_review_prompt(), parse_ranking()
- `src/gracekelly/core/roles.py` — RoleType, get_role(), format_prompt_with_role()
- `src/gracekelly/core/embeddings.py` — EmbeddingsClient
- `src/gracekelly/core/similarity.py` — cosine_similarity()
- `src/gracekelly/core/reliability.py` — ReliabilityLevel, ReliabilityConfig, get_reliability_config()
- `src/gracekelly/core/patterns.py` — ExecutionPattern, PatternConfig, get_pattern_config()

Architecture:
- Python >=3.11
- This draft imports from `gracekelly.*` modules (they exist in the project)
- Tests use `unittest.TestCase` with `unittest.mock`
- Test runner: `python -m pytest docs/codex/drafts/test_consensus_execution.py -q`
- pytest will find the test because `pyproject.toml` has `pythonpath = ["src"]`

## CONSTRAINTS
- Create ONLY the two files listed above in `docs/codex/drafts/`. Do NOT modify any existing files.
- Do NOT create `__init__.py` in `docs/codex/drafts/` — tests import directly.
- Follow these instructions EXACTLY. Do NOT deviate, improve, or "enhance".
- Do NOT add: logging, comments, docstrings.
- Preserve project code style: 4-space indentation, snake_case, `from __future__ import annotations`.
- This is a DRAFT. It demonstrates architecture, not production code.

### consensus_execution.py specification

The module demonstrates how a consensus-based execution flow would work:

1. Take a prompt and execution config
2. Generate prompt variations (3 per round)
3. Execute each variation through available models (simulated via callback)
4. Collect responses and run ConsensusAnalyzer
5. If consensus not reached and rounds remain, repeat with new variations
6. Extract confidence scores from responses
7. Compute weighted consensus score
8. Return final ConsensusResult + best response

```python
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
```

That is the COMPLETE implementation. Copy it exactly.

### test_consensus_execution.py specification

Exactly these tests, using mocked EmbeddingsClient and a fake execute_fn:

Setup helpers:
```python
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from unittest.mock import MagicMock
from gracekelly.core.embeddings import EmbeddingsClient
from gracekelly.core.consensus import ConsensusConfig
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
```

1. `test_single_round_converges` — all identical embeddings → 1 round, consensus_score=1.0
2. `test_best_response_is_centroid` — result.best_response is one of the responses
3. `test_total_llm_calls_equals_variations` — default 3 variations → total_llm_calls=3
4. `test_execute_fn_called_with_variations` — execute_fn receives different prompts (not all identical)
5. `test_weighted_score_present` — use_confidence_weighting=True → weighted_score is not None
6. `test_weighted_score_absent` — use_confidence_weighting=False → weighted_score is None
7. `test_all_responses_collected` — all_responses tuple contains all responses from all rounds
8. `test_result_is_frozen` — assigning result.best_response = "x" raises FrozenInstanceError
9. `test_multiple_rounds_with_divergent` — divergent embeddings → total_rounds > 1 (use _make_divergent_embeddings + max_rounds=2)
10. `test_custom_variations_count` — variations_per_round=5 → total_llm_calls=5 per round
11. `test_consensus_result_accessible` — result.consensus_result is a ConsensusResult with correct fields
12. `test_returns_consensus_execution_result` — isinstance(result, ConsensusExecutionResult)

End with:
```python
if __name__ == "__main__":
    unittest.main()
```

## DONE WHEN
- [ ] `docs/codex/drafts/consensus_execution.py` exists with ConsensusExecutor class
- [ ] `docs/codex/drafts/test_consensus_execution.py` exists with exactly 12 test methods
- [ ] `python -m pytest docs/codex/drafts/test_consensus_execution.py -q` → 12 passed, 0 failed
- [ ] `python -m pytest -q` → all existing tests still pass (607+) — the draft test is discovered but should not break anything
- [ ] NO existing files modified
- [ ] Files are in `docs/codex/drafts/`, NOT in `src/`

## SELF-EVALUATION
After completing, score yourself 1-10:
- Is the implementation EXACTLY as specified?
- Do all 12 tests pass, including test_multiple_rounds_with_divergent?
- Does `sys.path.insert` in the test file correctly allow importing from the same directory?
- Does the ConsensusExecutor correctly chain: variations → execute → analyze → loop?
- Is there any code beyond the specification?

If your self-score is below 9.8/10, fix issues before submitting. Target: 9.8/10.
```
