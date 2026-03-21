from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class DebateResult:
    challenge: str
    defense: str
    improved_response: str
    rounds_used: int


def build_challenge_prompt(original_prompt: str, top_response: str) -> str:
    return (
        f"Original question: {original_prompt}\n\n"
        f"Proposed answer: {top_response}\n\n"
        "As Devil's Advocate, identify weaknesses, gaps, or errors in this answer. "
        "Be specific and constructive."
    )


def build_defense_prompt(
    original_prompt: str, top_response: str, challenge: str
) -> str:
    return (
        f"Original question: {original_prompt}\n\n"
        f"Your answer: {top_response}\n\n"
        f"Critique received: {challenge}\n\n"
        "Address each critique. Improve your answer where the critique is valid. "
        "Defend your position where the critique is wrong. Return the improved answer."
    )


def run_debate(
    original_prompt: str,
    top_response: str,
    execute_fn: Callable[[str], str],
) -> DebateResult:
    challenge_prompt = build_challenge_prompt(original_prompt, top_response)
    challenge = execute_fn(challenge_prompt)

    defense_prompt = build_defense_prompt(original_prompt, top_response, challenge)
    improved = execute_fn(defense_prompt)

    return DebateResult(
        challenge=challenge,
        defense=improved,
        improved_response=improved,
        rounds_used=1,
    )
