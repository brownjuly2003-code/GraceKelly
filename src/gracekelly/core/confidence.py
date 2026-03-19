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
