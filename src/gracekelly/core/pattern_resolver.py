from __future__ import annotations

from dataclasses import dataclass

from gracekelly.core.contracts import MergeStrategy
from gracekelly.core.patterns import ExecutionPattern, get_pattern_config
from gracekelly.core.reliability import ReliabilityLevel, get_reliability_config
from gracekelly.core.roles import RoleType


@dataclass(frozen=True, slots=True)
class ResolvedExecution:
    pattern: ExecutionPattern
    reliability_level: ReliabilityLevel
    model_count: int
    quorum: int
    merge_strategy: MergeStrategy
    reasoning: bool
    roles: tuple[RoleType, ...]
    use_consensus: bool
    consensus_threshold: float
    max_consensus_rounds: int
    use_decomposition: bool
    use_peer_review: bool
    use_confidence: bool
    iterative: bool


_LEVEL_TO_PATTERN: dict[ReliabilityLevel, ExecutionPattern] = {
    ReliabilityLevel.QUICK: ExecutionPattern.SINGLE,
    ReliabilityLevel.STANDARD: ExecutionPattern.DUAL,
    ReliabilityLevel.HIGH: ExecutionPattern.CONSENSUS,
    ReliabilityLevel.MAXIMUM: ExecutionPattern.MAXIMUM,
}

_LEVEL_TO_ROLES: dict[ReliabilityLevel, tuple[RoleType, ...]] = {
    ReliabilityLevel.QUICK: (RoleType.FACT_VERIFIER,),
    ReliabilityLevel.STANDARD: (RoleType.JUDGE, RoleType.SYNTHESIZER),
    ReliabilityLevel.HIGH: (
        RoleType.VERIFIER,
        RoleType.JUDGE,
        RoleType.DEVIL_ADVOCATE,
        RoleType.SYNTHESIZER,
    ),
    ReliabilityLevel.MAXIMUM: (
        RoleType.VERIFIER,
        RoleType.JUDGE,
        RoleType.DEVIL_ADVOCATE,
        RoleType.FACT_VERIFIER,
        RoleType.SYNTHESIZER,
        RoleType.DECOMPOSER,
    ),
}


def resolve_from_level(level: ReliabilityLevel) -> ResolvedExecution:
    reliability = get_reliability_config(level)
    pattern = _LEVEL_TO_PATTERN[level]
    pattern_config = get_pattern_config(pattern)
    roles = _LEVEL_TO_ROLES[level]

    return ResolvedExecution(
        pattern=pattern,
        reliability_level=level,
        model_count=pattern_config.model_count or reliability.min_models,
        quorum=pattern_config.quorum,
        merge_strategy=pattern_config.merge_strategy,
        reasoning=pattern_config.reasoning,
        roles=roles,
        use_consensus=reliability.use_consensus,
        consensus_threshold=reliability.consensus_threshold,
        max_consensus_rounds=reliability.max_consensus_rounds,
        use_decomposition=reliability.use_decomposition,
        use_peer_review=reliability.use_peer_review,
        use_confidence=reliability.use_confidence,
        iterative=pattern_config.iterative,
    )


def resolve_from_pattern(pattern: ExecutionPattern) -> ResolvedExecution:
    pattern_config = get_pattern_config(pattern)

    if pattern_config.iterative:
        level = ReliabilityLevel.MAXIMUM
    elif pattern_config.use_consensus:
        level = ReliabilityLevel.HIGH
    elif pattern_config.model_count and pattern_config.model_count >= 2:
        level = ReliabilityLevel.STANDARD
    else:
        level = ReliabilityLevel.QUICK

    reliability = get_reliability_config(level)
    roles = _LEVEL_TO_ROLES[level]

    return ResolvedExecution(
        pattern=pattern,
        reliability_level=level,
        model_count=pattern_config.model_count or reliability.min_models,
        quorum=pattern_config.quorum,
        merge_strategy=pattern_config.merge_strategy,
        reasoning=pattern_config.reasoning,
        roles=roles,
        use_consensus=pattern_config.use_consensus,
        consensus_threshold=reliability.consensus_threshold,
        max_consensus_rounds=reliability.max_consensus_rounds,
        use_decomposition=reliability.use_decomposition,
        use_peer_review=reliability.use_peer_review,
        use_confidence=reliability.use_confidence,
        iterative=pattern_config.iterative,
    )
