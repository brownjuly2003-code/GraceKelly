# 130: Pattern Resolver — TODO

Phase 9 (Reliability + Patterns). Dependency: patterns.py, reliability.py, roles.py exist.
Complexity: moderate | Runs: 2

```
## GOAL
Create a pattern resolver that maps a reliability level or pattern name to a complete execution configuration including roles, model count, and consensus settings. Two new files: `src/gracekelly/core/pattern_resolver.py` and `tests/test_pattern_resolver.py`.

## CONTEXT
Files to CREATE:
- `src/gracekelly/core/pattern_resolver.py` — resolver logic
- `tests/test_pattern_resolver.py` — unit tests

Files to READ (do NOT modify):
- `src/gracekelly/core/patterns.py` — ExecutionPattern, PatternConfig, get_pattern_config()
- `src/gracekelly/core/reliability.py` — ReliabilityLevel, ReliabilityConfig, get_reliability_config()
- `src/gracekelly/core/roles.py` — RoleType
- `src/gracekelly/core/contracts.py` — MergeStrategy

Architecture:
- Python >=3.11, no external dependencies
- Test runner: `python -m pytest tests/test_pattern_resolver.py -q`

## CONSTRAINTS
- Create ONLY the two files listed above. Do NOT modify any existing files.
- Follow these instructions EXACTLY.
- Do NOT add: logging, comments, docstrings.
- Preserve project code style: 4-space indentation, snake_case, `from __future__ import annotations`.

### pattern_resolver.py specification

```python
from __future__ import annotations

from dataclasses import dataclass

from gracekelly.core.contracts import MergeStrategy
from gracekelly.core.patterns import ExecutionPattern, PatternConfig, get_pattern_config
from gracekelly.core.reliability import ReliabilityLevel, ReliabilityConfig, get_reliability_config
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
```

That is the COMPLETE implementation. Copy it exactly.

### test_pattern_resolver.py specification

Exactly these tests:

1. `test_quick_maps_to_single` — resolve_from_level(QUICK).pattern == SINGLE
2. `test_standard_maps_to_dual` — resolve_from_level(STANDARD).pattern == DUAL
3. `test_high_maps_to_consensus` — resolve_from_level(HIGH).pattern == CONSENSUS
4. `test_maximum_maps_to_maximum` — resolve_from_level(MAXIMUM).pattern == MAXIMUM
5. `test_quick_has_fact_verifier_role` — QUICK roles contain FACT_VERIFIER only
6. `test_maximum_has_all_roles` — MAXIMUM roles contain all 6 RoleTypes
7. `test_maximum_is_iterative` — resolve_from_level(MAXIMUM).iterative == True
8. `test_quick_no_consensus` — resolve_from_level(QUICK).use_consensus == False
9. `test_high_uses_consensus` — resolve_from_level(HIGH).use_consensus == True
10. `test_resolve_from_pattern_sonar` — resolve_from_pattern(SONAR).reliability_level == QUICK
11. `test_resolve_from_pattern_maximum` — resolve_from_pattern(MAXIMUM).reliability_level == MAXIMUM
12. `test_resolve_from_pattern_consensus` — resolve_from_pattern(CONSENSUS).use_consensus == True
13. `test_resolved_execution_is_frozen` — assigning result.pattern = "x" raises FrozenInstanceError
14. `test_consensus_threshold_from_level` — MAXIMUM threshold == 0.95, HIGH == 0.85

End with:
```python
if __name__ == "__main__":
    unittest.main()
```

## DONE WHEN
- [ ] `src/gracekelly/core/pattern_resolver.py` exists
- [ ] `tests/test_pattern_resolver.py` exists with exactly 14 test methods
- [ ] `python -m pytest tests/test_pattern_resolver.py -q` → 14 passed, 0 failed
- [ ] `python -m pytest -q` → all existing tests still pass (631+)
- [ ] No other files created or modified

## SELF-EVALUATION
After completing, score yourself 1-10. Target: 9.8/10.
```
