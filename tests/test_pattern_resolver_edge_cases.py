from __future__ import annotations

import unittest

from gracekelly.core.pattern_resolver import resolve_from_level, resolve_from_pattern
from gracekelly.core.patterns import ExecutionPattern
from gracekelly.core.reliability import ReliabilityLevel


class ResolveFromPatternEdgeCasesTests(unittest.TestCase):
    """Tests covering all ExecutionPattern variants via resolve_from_pattern."""

    def test_dual_resolves_to_standard_level(self) -> None:
        result = resolve_from_pattern(ExecutionPattern.DUAL)
        self.assertEqual(result.reliability_level, ReliabilityLevel.STANDARD)

    def test_five_models_resolves_to_standard_level(self) -> None:
        result = resolve_from_pattern(ExecutionPattern.FIVE_MODELS)
        self.assertEqual(result.reliability_level, ReliabilityLevel.STANDARD)

    def test_five_models_compare_resolves_to_standard_level(self) -> None:
        result = resolve_from_pattern(ExecutionPattern.FIVE_MODELS_COMPARE)
        self.assertEqual(result.reliability_level, ReliabilityLevel.STANDARD)

    def test_single_resolves_to_quick_level(self) -> None:
        """SINGLE has model_count=1 and no consensus → QUICK."""
        result = resolve_from_pattern(ExecutionPattern.SINGLE)
        self.assertEqual(result.reliability_level, ReliabilityLevel.QUICK)

    def test_consensus_resolves_to_high_level(self) -> None:
        result = resolve_from_pattern(ExecutionPattern.CONSENSUS)
        self.assertEqual(result.reliability_level, ReliabilityLevel.HIGH)

    def test_pattern_preserved_regardless_of_inferred_level(self) -> None:
        """The pattern field should stay as given, not be overridden by the inferred level."""
        result = resolve_from_pattern(ExecutionPattern.DUAL)
        self.assertEqual(result.pattern, ExecutionPattern.DUAL)

    def test_dual_use_consensus_false(self) -> None:
        result = resolve_from_pattern(ExecutionPattern.DUAL)
        self.assertFalse(result.use_consensus)

    def test_five_models_compare_use_consensus_false(self) -> None:
        result = resolve_from_pattern(ExecutionPattern.FIVE_MODELS_COMPARE)
        self.assertFalse(result.use_consensus)


class ResolveFromLevelTests(unittest.TestCase):
    """Edge cases for resolve_from_level — all four levels."""

    def test_quick_has_one_role(self) -> None:
        result = resolve_from_level(ReliabilityLevel.QUICK)
        self.assertEqual(len(result.roles), 1)

    def test_standard_has_two_roles(self) -> None:
        result = resolve_from_level(ReliabilityLevel.STANDARD)
        self.assertEqual(len(result.roles), 2)

    def test_maximum_has_six_roles(self) -> None:
        result = resolve_from_level(ReliabilityLevel.MAXIMUM)
        self.assertEqual(len(result.roles), 6)

    def test_high_use_decomposition(self) -> None:
        result = resolve_from_level(ReliabilityLevel.HIGH)
        self.assertTrue(result.use_decomposition)

    def test_quick_no_decomposition(self) -> None:
        result = resolve_from_level(ReliabilityLevel.QUICK)
        self.assertFalse(result.use_decomposition)

    def test_maximum_use_peer_review(self) -> None:
        result = resolve_from_level(ReliabilityLevel.MAXIMUM)
        self.assertTrue(result.use_peer_review)

    def test_high_no_peer_review(self) -> None:
        result = resolve_from_level(ReliabilityLevel.HIGH)
        self.assertFalse(result.use_peer_review)

    def test_level_preserved_in_result(self) -> None:
        for level in ReliabilityLevel:
            result = resolve_from_level(level)
            self.assertEqual(result.reliability_level, level)


if __name__ == "__main__":
    unittest.main()
