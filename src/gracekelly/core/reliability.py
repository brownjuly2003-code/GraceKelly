from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ReliabilityLevel(StrEnum):
    QUICK = "quick"
    STANDARD = "standard"
    HIGH = "high"
    MAXIMUM = "maximum"


@dataclass(frozen=True, slots=True)
class ReliabilityConfig:
    level: ReliabilityLevel
    min_models: int
    max_models: int
    use_verification: bool
    use_devil_advocate: bool
    use_consensus: bool
    consensus_threshold: float
    use_decomposition: bool
    max_consensus_rounds: int
    use_peer_review: bool
    use_confidence: bool
    description: str


RELIABILITY_CONFIGS: dict[ReliabilityLevel, ReliabilityConfig] = {
    ReliabilityLevel.QUICK: ReliabilityConfig(
        level=ReliabilityLevel.QUICK,
        min_models=1,
        max_models=1,
        use_verification=True,
        use_devil_advocate=False,
        use_consensus=False,
        consensus_threshold=0.0,
        use_decomposition=False,
        max_consensus_rounds=0,
        use_peer_review=False,
        use_confidence=False,
        description="Single model with fact verification. Fast, low cost.",
    ),
    ReliabilityLevel.STANDARD: ReliabilityConfig(
        level=ReliabilityLevel.STANDARD,
        min_models=2,
        max_models=3,
        use_verification=True,
        use_devil_advocate=False,
        use_consensus=False,
        consensus_threshold=0.0,
        use_decomposition=False,
        max_consensus_rounds=0,
        use_peer_review=False,
        use_confidence=True,
        description="Two models with comparison and synthesis. Balanced.",
    ),
    ReliabilityLevel.HIGH: ReliabilityConfig(
        level=ReliabilityLevel.HIGH,
        min_models=3,
        max_models=5,
        use_verification=True,
        use_devil_advocate=True,
        use_consensus=True,
        consensus_threshold=0.85,
        use_decomposition=True,
        max_consensus_rounds=1,
        use_peer_review=False,
        use_confidence=True,
        description="Three+ models with full verification, devil's advocate, and consensus.",
    ),
    ReliabilityLevel.MAXIMUM: ReliabilityConfig(
        level=ReliabilityLevel.MAXIMUM,
        min_models=5,
        max_models=5,
        use_verification=True,
        use_devil_advocate=True,
        use_consensus=True,
        consensus_threshold=0.95,
        use_decomposition=True,
        max_consensus_rounds=5,
        use_peer_review=True,
        use_confidence=True,
        description="All models, iterative consensus loop, peer review, all roles.",
    ),
}


def get_reliability_config(level: ReliabilityLevel) -> ReliabilityConfig:
    return RELIABILITY_CONFIGS[level]


def resolve_reliability_level(name: str) -> ReliabilityLevel:
    level = ReliabilityLevel(name)
    return level
