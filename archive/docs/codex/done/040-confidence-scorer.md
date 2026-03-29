# 040: Confidence Scorer — TODO

Phase 6 (Consensus Engine, ReConcile enrichment). Dependency: none.
Complexity: routine | Runs: 1

```
## GOAL
Create a confidence scoring module that extracts self-assessed confidence (1-10) from LLM responses and computes weighted votes. Two new files: `src/gracekelly/core/confidence.py` and `tests/test_confidence.py`.

## CONTEXT
Files to CREATE:
- `src/gracekelly/core/confidence.py` — confidence extraction and weighted voting
- `tests/test_confidence.py` — unit tests

Files to READ (do NOT modify):
- `src/gracekelly/core/consensus.py` — ConsensusResult (downstream consumer)

Architecture:
- Python >=3.11, no external dependencies (only `re` from stdlib)
- All files start with `from __future__ import annotations`
- Tests use `unittest.TestCase`
- Test runner: `python -m pytest tests/test_confidence.py -q`

## CONSTRAINTS
- Create ONLY the two files listed above. Do NOT modify any existing files.
- Follow these instructions EXACTLY. Do NOT deviate, improve, or "enhance".
- Do NOT add: logging, comments, docstrings, NLP libraries, ML models.
- Do NOT use nltk, spacy, or any external package. Only `re` from stdlib.
- Preserve project code style: 4-space indentation, snake_case, `from __future__ import annotations`.

### confidence.py specification

```python
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConfidenceScore:
    response_index: int
    raw_score: float
    normalized_score: float


_CONFIDENCE_PATTERN = re.compile(
    r"(?:confidence|уверенность)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(?:/\s*10)?",
    re.IGNORECASE,
)


def extract_confidence(text: str, response_index: int = 0) -> ConfidenceScore:
    match = _CONFIDENCE_PATTERN.search(text)
    if match:
        raw = float(match.group(1))
        raw = min(10.0, max(0.0, raw))
    else:
        raw = 5.0
    return ConfidenceScore(
        response_index=response_index,
        raw_score=raw,
        normalized_score=raw / 10.0,
    )


def extract_batch_confidence(
    texts: list[str],
) -> list[ConfidenceScore]:
    return [extract_confidence(text, i) for i, text in enumerate(texts)]


def weighted_vote(
    cluster_indices: list[int],
    scores: list[ConfidenceScore],
    total_responses: int,
) -> float:
    if total_responses == 0:
        return 0.0
    score_map = {s.response_index: s.normalized_score for s in scores}
    cluster_weight = sum(score_map.get(idx, 0.5) for idx in cluster_indices)
    total_weight = sum(s.normalized_score for s in scores)
    if total_weight == 0.0:
        return len(cluster_indices) / total_responses
    return cluster_weight / total_weight
```

That is the COMPLETE implementation. Copy it exactly.

### test_confidence.py specification

Exactly these tests:

1. `test_extract_explicit_confidence` — "Confidence: 8/10" → raw_score=8.0, normalized=0.8
2. `test_extract_without_slash` — "confidence: 7" → raw_score=7.0
3. `test_extract_with_equals` — "Confidence=9" → raw_score=9.0
4. `test_extract_russian` — "уверенность: 6/10" → raw_score=6.0
5. `test_extract_no_confidence_defaults_five` — "Just a regular answer" → raw_score=5.0
6. `test_extract_clamps_above_ten` — "confidence: 15" → raw_score=10.0
7. `test_extract_float_score` — "confidence: 7.5/10" → raw_score=7.5
8. `test_extract_batch` — 3 texts → list of 3 ConfidenceScores with correct indices
9. `test_weighted_vote_equal_weights` — 2 of 4 responses in cluster, all weight 0.5 → vote ≈ 0.5
10. `test_weighted_vote_high_confidence_cluster` — high-confidence cluster gets higher vote
11. `test_weighted_vote_empty_cluster` — empty cluster_indices → 0.0
12. `test_weighted_vote_zero_total` — total_responses=0 → 0.0
13. `test_confidence_score_is_frozen` — assigning score.raw_score = 1.0 raises FrozenInstanceError
14. `test_response_index_preserved` — extract_confidence("text", 5).response_index == 5

End with:
```python
if __name__ == "__main__":
    unittest.main()
```

## DONE WHEN
- [ ] `src/gracekelly/core/confidence.py` exists with ConfidenceScore, extract_confidence(), extract_batch_confidence(), weighted_vote()
- [ ] `tests/test_confidence.py` exists with exactly 14 test methods
- [ ] `python -m pytest tests/test_confidence.py -q` → 14 passed, 0 failed
- [ ] `python -m pytest -q` → all existing tests still pass (541+)
- [ ] No other files created or modified

## SELF-EVALUATION
After completing, score yourself 1-10:
- Is the implementation EXACTLY as specified?
- Are all 14 tests present?
- Does the regex handle all specified formats (English, Russian, with/without slash)?
- Is there any code beyond the specification?

If your self-score is below 9.8/10, fix issues before submitting. Target: 9.8/10.
```
