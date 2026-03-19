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
