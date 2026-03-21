from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PeerRanking:
    response_index: int
    score: float
    rank: int


def build_review_prompt(original_prompt: str, responses: list[str]) -> str:
    parts = [
        f"Original question: {original_prompt}\n\nRank these answers from best to worst:\n"
    ]
    for i, resp in enumerate(responses):
        parts.append(f"\n[Answer {i + 1}]: {resp[:500]}\n")
    parts.append(
        "\nReturn ONLY a comma-separated list of answer numbers, best first. Example: 2,1,3"
    )
    return "".join(parts)


def parse_rankings(review_output: str, num_responses: int) -> list[int]:
    numbers = re.findall(r"\d+", review_output)
    indices: list[int] = []
    seen: set[int] = set()
    for n in numbers:
        idx = int(n) - 1
        if 0 <= idx < num_responses and idx not in seen:
            indices.append(idx)
            seen.add(idx)
    if len(indices) < num_responses:
        for i in range(num_responses):
            if i not in seen:
                indices.append(i)
    return indices[:num_responses]


def rerank_cluster(
    responses: list[str],
    rankings_list: list[list[int]],
) -> list[PeerRanking]:
    n = len(responses)
    if n == 0:
        return []
    scores = [0.0] * n
    for ranking in rankings_list:
        for position, resp_idx in enumerate(ranking):
            if 0 <= resp_idx < n:
                scores[resp_idx] += n - position
    indexed = sorted(enumerate(scores), key=lambda x: (-x[1], x[0]))
    return [
        PeerRanking(response_index=idx, score=score, rank=rank + 1)
        for rank, (idx, score) in enumerate(indexed)
    ]
