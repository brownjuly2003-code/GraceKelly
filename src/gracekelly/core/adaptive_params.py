from __future__ import annotations

from dataclasses import dataclass

from gracekelly.core.task_classifier import TaskType


@dataclass(frozen=True, slots=True)
class AdaptiveConsensusParams:
    consensus_target: float
    max_rounds: int
    min_responses: int
    use_debate: bool
    use_cross_pollination: bool


_TASK_PARAMS: dict[TaskType, AdaptiveConsensusParams] = {
    TaskType.CODING: AdaptiveConsensusParams(0.95, 5, 3, True, True),
    TaskType.ANALYSIS: AdaptiveConsensusParams(0.90, 4, 3, True, True),
    TaskType.CREATIVE: AdaptiveConsensusParams(0.70, 2, 3, False, False),
    TaskType.RESEARCH: AdaptiveConsensusParams(0.85, 4, 3, True, True),
    TaskType.MATH: AdaptiveConsensusParams(0.95, 5, 3, True, False),
    TaskType.GENERAL: AdaptiveConsensusParams(0.85, 3, 3, True, False),
}

_DEFAULT = AdaptiveConsensusParams(0.85, 3, 3, True, False)


def get_adaptive_params(task_type: TaskType) -> AdaptiveConsensusParams:
    return _TASK_PARAMS.get(task_type, _DEFAULT)
