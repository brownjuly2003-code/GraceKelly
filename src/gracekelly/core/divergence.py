from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DivergenceAction(StrEnum):
    ACCEPT = "accept"
    DEBATE = "debate"
    EXPAND = "expand"
    ESCALATE = "escalate"


@dataclass(frozen=True, slots=True)
class DivergenceResult:
    action: DivergenceAction
    reason: str
    extra_rounds_needed: int


def assess_divergence(
    consensus_score: float,
    num_clusters: int,
    round_number: int,
    max_rounds: int,
) -> DivergenceResult:
    if consensus_score >= 0.9:
        return DivergenceResult(
            DivergenceAction.ACCEPT, "Strong consensus reached.", 0
        )
    if consensus_score >= 0.7:
        return DivergenceResult(
            DivergenceAction.DEBATE, "Moderate consensus — debate may help.", 0
        )
    if round_number < max_rounds:
        extra = min(max_rounds - round_number, 3)
        return DivergenceResult(
            DivergenceAction.EXPAND,
            f"Low consensus — expand with {extra} more rounds.",
            extra,
        )
    return DivergenceResult(
        DivergenceAction.ESCALATE, "Max rounds reached with low consensus.", 0
    )
