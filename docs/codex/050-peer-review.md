# 050: Peer Review Protocol — TODO

Phase 6 (Consensus Engine, LLM Council enrichment). Dependency: none.
Complexity: routine | Runs: 1

```
## GOAL
Create a peer review protocol module that anonymizes responses and formats ranking prompts for LLM-based peer review. Two new files: `src/gracekelly/core/peer_review.py` and `tests/test_peer_review.py`.

## CONTEXT
Files to CREATE:
- `src/gracekelly/core/peer_review.py` — anonymization and prompt formatting
- `tests/test_peer_review.py` — unit tests

Files to READ (do NOT modify):
- `src/gracekelly/core/roles.py` — for system prompt pattern reference

Architecture:
- Python >=3.11, no external dependencies
- All files start with `from __future__ import annotations`
- Tests use `unittest.TestCase`
- Test runner: `python -m pytest tests/test_peer_review.py -q`

## CONSTRAINTS
- Create ONLY the two files listed above. Do NOT modify any existing files.
- Follow these instructions EXACTLY. Do NOT deviate, improve, or "enhance".
- Do NOT add: logging, comments, docstrings, LLM API calls, async support.
- This module creates PROMPTS only. It does NOT call any LLM API.
- Preserve project code style: 4-space indentation, snake_case, `from __future__ import annotations`.

### peer_review.py specification

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AnonymizedResponse:
    label: str
    text: str
    original_index: int


@dataclass(frozen=True, slots=True)
class PeerReviewPrompt:
    system_prompt: str
    user_prompt: str
    reviewer_index: int
    excluded_index: int


_LABELS = ("A", "B", "C", "D", "E", "F", "G", "H", "I", "J")

_SYSTEM_PROMPT = (
    "You are an impartial peer reviewer. "
    "You will see multiple anonymized answers to the same question. "
    "Rank them from best to worst based on accuracy, completeness, and clarity. "
    "Return ONLY a comma-separated list of labels, best first. "
    "Example: B, A, C"
)


def anonymize_responses(responses: list[str]) -> list[AnonymizedResponse]:
    return [
        AnonymizedResponse(
            label=_LABELS[i] if i < len(_LABELS) else f"R{i}",
            text=text,
            original_index=i,
        )
        for i, text in enumerate(responses)
    ]


def format_review_prompt(
    question: str,
    anonymized: list[AnonymizedResponse],
    reviewer_index: int,
) -> PeerReviewPrompt:
    visible = [r for r in anonymized if r.original_index != reviewer_index]
    lines = [f"Question: {question}", ""]
    for resp in visible:
        lines.append(f"--- Answer {resp.label} ---")
        lines.append(resp.text)
        lines.append("")
    lines.append("Rank these answers from best to worst (comma-separated labels):")

    return PeerReviewPrompt(
        system_prompt=_SYSTEM_PROMPT,
        user_prompt="\n".join(lines),
        reviewer_index=reviewer_index,
        excluded_index=reviewer_index,
    )


def parse_ranking(ranking_text: str) -> list[str]:
    return [label.strip() for label in ranking_text.split(",") if label.strip()]
```

That is the COMPLETE implementation. Copy it exactly.

### test_peer_review.py specification

Exactly these tests:

1. `test_anonymize_labels` — 3 responses → labels ["A", "B", "C"]
2. `test_anonymize_preserves_text` — original text preserved in AnonymizedResponse.text
3. `test_anonymize_original_index` — indices [0, 1, 2] match
4. `test_anonymize_more_than_ten` — 11 responses → 11th label is "R10"
5. `test_format_excludes_reviewer` — reviewer_index=1 → Answer B not in user_prompt
6. `test_format_includes_others` — reviewer_index=0 → Answers B, C in prompt
7. `test_format_system_prompt` — system prompt contains "peer reviewer"
8. `test_format_contains_question` — user_prompt starts with "Question: ..."
9. `test_format_reviewer_index` — result.reviewer_index matches input
10. `test_parse_ranking_simple` — parse_ranking("B, A, C") == ["B", "A", "C"]
11. `test_parse_ranking_no_spaces` — parse_ranking("B,A,C") == ["B", "A", "C"]
12. `test_parse_ranking_empty` — parse_ranking("") == []
13. `test_anonymized_response_is_frozen` — assigning resp.label = "X" raises FrozenInstanceError
14. `test_peer_review_prompt_is_frozen` — assigning prompt.system_prompt = "X" raises FrozenInstanceError

End with:
```python
if __name__ == "__main__":
    unittest.main()
```

## DONE WHEN
- [ ] `src/gracekelly/core/peer_review.py` exists with AnonymizedResponse, PeerReviewPrompt, anonymize_responses(), format_review_prompt(), parse_ranking()
- [ ] `tests/test_peer_review.py` exists with exactly 14 test methods
- [ ] `python -m pytest tests/test_peer_review.py -q` → 14 passed, 0 failed
- [ ] `python -m pytest -q` → all existing tests still pass (541+)
- [ ] No LLM API calls anywhere
- [ ] No other files created or modified

## SELF-EVALUATION
After completing, score yourself 1-10:
- Is the implementation EXACTLY as specified?
- Are all 14 tests present?
- Does test_format_excludes_reviewer actually verify the reviewer's answer is NOT in the prompt?
- Is there any code beyond the specification?

If your self-score is below 9.8/10, fix issues before submitting. Target: 9.8/10.
```
