from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from gracekelly.core.contracts import MergeStrategy


class ExecutionPattern(StrEnum):
    SONAR = "sonar"
    SINGLE = "single"
    DUAL = "dual"
    FIVE_MODELS = "five_models"
    FIVE_MODELS_COMPARE = "five_models_compare"
    CONSENSUS = "consensus"
    MAXIMUM = "maximum"


@dataclass(frozen=True, slots=True)
class PatternConfig:
    pattern: ExecutionPattern
    model_count: int | None
    reasoning: bool
    merge_strategy: MergeStrategy
    quorum: int
    use_consensus: bool
    use_roles: bool
    iterative: bool
    description: str


PATTERN_CONFIGS: dict[ExecutionPattern, PatternConfig] = {
    ExecutionPattern.SONAR: PatternConfig(
        pattern=ExecutionPattern.SONAR,
        model_count=1,
        reasoning=False,
        merge_strategy=MergeStrategy.FIRST_SUCCESS,
        quorum=1,
        use_consensus=False,
        use_roles=False,
        iterative=False,
        description="Single Sonar model, no reasoning. Maximum speed.",
    ),
    ExecutionPattern.SINGLE: PatternConfig(
        pattern=ExecutionPattern.SINGLE,
        model_count=1,
        reasoning=True,
        merge_strategy=MergeStrategy.FIRST_SUCCESS,
        quorum=1,
        use_consensus=False,
        use_roles=False,
        iterative=False,
        description="Single model with reasoning enabled.",
    ),
    ExecutionPattern.DUAL: PatternConfig(
        pattern=ExecutionPattern.DUAL,
        model_count=2,
        reasoning=True,
        merge_strategy=MergeStrategy.CONCAT,
        quorum=2,
        use_consensus=False,
        use_roles=False,
        iterative=False,
        description="Two models, both answers returned for comparison.",
    ),
    ExecutionPattern.FIVE_MODELS: PatternConfig(
        pattern=ExecutionPattern.FIVE_MODELS,
        model_count=5,
        reasoning=True,
        merge_strategy=MergeStrategy.CONCAT,
        quorum=3,
        use_consensus=False,
        use_roles=False,
        iterative=False,
        description="All models, answers returned as-is.",
    ),
    ExecutionPattern.FIVE_MODELS_COMPARE: PatternConfig(
        pattern=ExecutionPattern.FIVE_MODELS_COMPARE,
        model_count=5,
        reasoning=True,
        merge_strategy=MergeStrategy.FIRST_SUCCESS,
        quorum=3,
        use_consensus=False,
        use_roles=True,
        iterative=False,
        description="All models, then Judge role analyzes differences.",
    ),
    ExecutionPattern.CONSENSUS: PatternConfig(
        pattern=ExecutionPattern.CONSENSUS,
        model_count=3,
        reasoning=True,
        merge_strategy=MergeStrategy.FIRST_SUCCESS,
        quorum=3,
        use_consensus=True,
        use_roles=True,
        iterative=False,
        description="Three models with embedding-based consensus clustering.",
    ),
    ExecutionPattern.MAXIMUM: PatternConfig(
        pattern=ExecutionPattern.MAXIMUM,
        model_count=5,
        reasoning=True,
        merge_strategy=MergeStrategy.FIRST_SUCCESS,
        quorum=5,
        use_consensus=True,
        use_roles=True,
        iterative=True,
        description="All models, iterative consensus loop until threshold.",
    ),
}


def get_pattern_config(pattern: ExecutionPattern) -> PatternConfig:
    return PATTERN_CONFIGS[pattern]


def resolve_pattern(name: str) -> ExecutionPattern:
    return ExecutionPattern(name)


def patterns_using_consensus() -> tuple[ExecutionPattern, ...]:
    return tuple(
        p for p, cfg in PATTERN_CONFIGS.items() if cfg.use_consensus
    )


def patterns_using_roles() -> tuple[ExecutionPattern, ...]:
    return tuple(
        p for p, cfg in PATTERN_CONFIGS.items() if cfg.use_roles
    )
