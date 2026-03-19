from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class ComplexityLevel(StrEnum):
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


_COMPLEXITY_INDICATORS: tuple[str, ...] = (
    "compare",
    "analyze",
    "evaluate",
    "trade-off",
    "pros and cons",
    "step by step",
    "multiple",
    "different perspectives",
    "comprehensive",
    "in-depth",
    "detailed analysis",
    "implications",
    "consequences",
    "relationship between",
    "how does .+ affect",
    "explain the difference",
    "advantages and disadvantages",
    "critically assess",
)

_DECOMPOSITION_SIGNALS: tuple[str, ...] = (
    "and also",
    "additionally",
    "furthermore",
    "as well as",
    "along with",
    "on top of that",
    "not only .+ but also",
    "first .+ then .+ finally",
    "both .+ and",
    "several",
    "multiple aspects",
)


@dataclass(frozen=True, slots=True)
class ComplexityAssessment:
    level: ComplexityLevel
    score: float
    indicators_found: tuple[str, ...]
    should_decompose: bool
    word_count: int


def assess_complexity(prompt: str) -> ComplexityAssessment:
    if not prompt or not prompt.strip():
        return ComplexityAssessment(
            level=ComplexityLevel.SIMPLE,
            score=0.0,
            indicators_found=(),
            should_decompose=False,
            word_count=0,
        )

    lower = prompt.lower()
    words = prompt.split()
    word_count = len(words)

    indicators_found: list[str] = []
    for indicator in _COMPLEXITY_INDICATORS:
        if re.search(r"\b" + indicator + r"\b", lower):
            indicators_found.append(indicator)

    decomposition_signals: list[str] = []
    for signal in _DECOMPOSITION_SIGNALS:
        if re.search(signal, lower):
            decomposition_signals.append(signal)

    indicator_score = min(1.0, len(indicators_found) / 4.0)
    length_score = min(1.0, word_count / 50.0)
    decomp_score = min(1.0, len(decomposition_signals) / 2.0)

    score = (indicator_score * 0.5) + (length_score * 0.3) + (decomp_score * 0.2)
    score = round(score, 3)

    if score >= 0.6:
        level = ComplexityLevel.COMPLEX
    elif score >= 0.3:
        level = ComplexityLevel.MODERATE
    else:
        level = ComplexityLevel.SIMPLE

    should_decompose = (
        level == ComplexityLevel.COMPLEX
        or len(decomposition_signals) >= 2
    )

    return ComplexityAssessment(
        level=level,
        score=score,
        indicators_found=tuple(indicators_found),
        should_decompose=should_decompose,
        word_count=word_count,
    )
