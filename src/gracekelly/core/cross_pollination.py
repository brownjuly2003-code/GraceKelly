from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class CrossPollinationResult:
    refined_responses: tuple[str, ...]
    num_pollinated: int
    original_indices: tuple[int, ...]


def build_cross_pollination_prompt(
    original_prompt: str, top_response: str, other_response: str
) -> str:
    return (
        f"Original question: {original_prompt}\n\n"
        f"A strong answer was: {top_response}\n\n"
        f"Another perspective was: {other_response}\n\n"
        "Synthesize both perspectives into an improved answer. "
        "Keep the strengths of both. Be concise."
    )


def cross_pollinate(
    original_prompt: str,
    responses: list[str],
    clusters: tuple[tuple[int, ...], ...],
    execute_fn: Callable[[str], str],
) -> CrossPollinationResult:
    if not clusters or not responses:
        return CrossPollinationResult(
            refined_responses=(), num_pollinated=0, original_indices=()
        )

    top_cluster = max(clusters, key=len)
    top_response = responses[top_cluster[0]]

    top_set = set(top_cluster)
    non_top_indices = [i for i in range(len(responses)) if i not in top_set]

    if not non_top_indices:
        return CrossPollinationResult(
            refined_responses=tuple(responses),
            num_pollinated=0,
            original_indices=tuple(range(len(responses))),
        )

    refined = list(responses)
    for idx in non_top_indices:
        prompt = build_cross_pollination_prompt(
            original_prompt, top_response, responses[idx]
        )
        refined[idx] = execute_fn(prompt)

    return CrossPollinationResult(
        refined_responses=tuple(refined),
        num_pollinated=len(non_top_indices),
        original_indices=tuple(non_top_indices),
    )
