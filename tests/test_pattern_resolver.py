from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from gracekelly.core.pattern_resolver import ResolvedExecution, resolve_from_level, resolve_from_pattern
from gracekelly.core.patterns import ExecutionPattern
from gracekelly.core.reliability import ReliabilityLevel
from gracekelly.core.roles import RoleType


class PatternResolverTests(unittest.TestCase):
    def test_quick_maps_to_single(self) -> None:
        result = resolve_from_level(ReliabilityLevel.QUICK)

        self.assertEqual(ExecutionPattern.SINGLE, result.pattern)

    def test_standard_maps_to_dual(self) -> None:
        result = resolve_from_level(ReliabilityLevel.STANDARD)

        self.assertEqual(ExecutionPattern.DUAL, result.pattern)

    def test_high_maps_to_consensus(self) -> None:
        result = resolve_from_level(ReliabilityLevel.HIGH)

        self.assertEqual(ExecutionPattern.CONSENSUS, result.pattern)

    def test_maximum_maps_to_maximum(self) -> None:
        result = resolve_from_level(ReliabilityLevel.MAXIMUM)

        self.assertEqual(ExecutionPattern.MAXIMUM, result.pattern)

    def test_quick_has_fact_verifier_role(self) -> None:
        result = resolve_from_level(ReliabilityLevel.QUICK)

        self.assertEqual((RoleType.FACT_VERIFIER,), result.roles)

    def test_maximum_has_all_roles(self) -> None:
        result = resolve_from_level(ReliabilityLevel.MAXIMUM)

        self.assertEqual(
            {
                RoleType.VERIFIER,
                RoleType.JUDGE,
                RoleType.DEVIL_ADVOCATE,
                RoleType.FACT_VERIFIER,
                RoleType.SYNTHESIZER,
                RoleType.DECOMPOSER,
            },
            set(result.roles),
        )

    def test_maximum_is_iterative(self) -> None:
        result = resolve_from_level(ReliabilityLevel.MAXIMUM)

        self.assertTrue(result.iterative)

    def test_quick_no_consensus(self) -> None:
        result = resolve_from_level(ReliabilityLevel.QUICK)

        self.assertFalse(result.use_consensus)

    def test_high_uses_consensus(self) -> None:
        result = resolve_from_level(ReliabilityLevel.HIGH)

        self.assertTrue(result.use_consensus)

    def test_resolve_from_pattern_sonar(self) -> None:
        result = resolve_from_pattern(ExecutionPattern.SONAR)

        self.assertEqual(ReliabilityLevel.QUICK, result.reliability_level)

    def test_resolve_from_pattern_maximum(self) -> None:
        result = resolve_from_pattern(ExecutionPattern.MAXIMUM)

        self.assertEqual(ReliabilityLevel.MAXIMUM, result.reliability_level)

    def test_resolve_from_pattern_consensus(self) -> None:
        result = resolve_from_pattern(ExecutionPattern.CONSENSUS)

        self.assertTrue(result.use_consensus)

    def test_resolved_execution_is_frozen(self) -> None:
        result = ResolvedExecution(
            pattern=ExecutionPattern.SINGLE,
            reliability_level=ReliabilityLevel.QUICK,
            model_count=1,
            quorum=1,
            merge_strategy=resolve_from_level(ReliabilityLevel.QUICK).merge_strategy,
            reasoning=True,
            roles=(RoleType.FACT_VERIFIER,),
            use_consensus=False,
            consensus_threshold=0.0,
            max_consensus_rounds=0,
            use_decomposition=False,
            use_peer_review=False,
            use_confidence=False,
            iterative=False,
        )

        with self.assertRaises(FrozenInstanceError):
            setattr(result, "pattern", ExecutionPattern.MAXIMUM)

    def test_consensus_threshold_from_level(self) -> None:
        maximum = resolve_from_level(ReliabilityLevel.MAXIMUM)
        high = resolve_from_level(ReliabilityLevel.HIGH)

        self.assertEqual(0.95, maximum.consensus_threshold)
        self.assertEqual(0.85, high.consensus_threshold)


if __name__ == "__main__":
    unittest.main()
