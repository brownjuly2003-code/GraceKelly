from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from gracekelly.core.contracts import MergeStrategy
from gracekelly.core.patterns import (
    PATTERN_CONFIGS,
    ExecutionPattern,
    get_pattern_config,
    patterns_using_consensus,
    patterns_using_roles,
    resolve_pattern,
)


class PatternTests(unittest.TestCase):
    def test_all_patterns_have_configs(self) -> None:
        for pattern in ExecutionPattern:
            self.assertIn(pattern, PATTERN_CONFIGS)

    def test_config_count_matches_enum(self) -> None:
        self.assertEqual(len(PATTERN_CONFIGS), len(ExecutionPattern))

    def test_sonar_is_fast(self) -> None:
        config = PATTERN_CONFIGS[ExecutionPattern.SONAR]
        self.assertEqual(config.model_count, 1)
        self.assertFalse(config.reasoning)
        self.assertFalse(config.use_consensus)

    def test_single_has_reasoning(self) -> None:
        config = PATTERN_CONFIGS[ExecutionPattern.SINGLE]
        self.assertEqual(config.model_count, 1)
        self.assertTrue(config.reasoning)

    def test_dual_uses_concat(self) -> None:
        config = PATTERN_CONFIGS[ExecutionPattern.DUAL]
        self.assertEqual(config.model_count, 2)
        self.assertEqual(config.merge_strategy, MergeStrategy.CONCAT)

    def test_five_models_quorum_three(self) -> None:
        config = PATTERN_CONFIGS[ExecutionPattern.FIVE_MODELS]
        self.assertEqual(config.model_count, 5)
        self.assertEqual(config.quorum, 3)

    def test_five_models_compare_uses_roles(self) -> None:
        config = PATTERN_CONFIGS[ExecutionPattern.FIVE_MODELS_COMPARE]
        self.assertTrue(config.use_roles)
        self.assertFalse(config.use_consensus)

    def test_consensus_uses_consensus(self) -> None:
        config = PATTERN_CONFIGS[ExecutionPattern.CONSENSUS]
        self.assertTrue(config.use_consensus)
        self.assertEqual(config.model_count, 3)

    def test_maximum_is_iterative(self) -> None:
        config = PATTERN_CONFIGS[ExecutionPattern.MAXIMUM]
        self.assertTrue(config.iterative)
        self.assertTrue(config.use_consensus)
        self.assertTrue(config.use_roles)
        self.assertEqual(config.model_count, 5)

    def test_get_pattern_config(self) -> None:
        config = get_pattern_config(ExecutionPattern.DUAL)
        self.assertEqual(config.pattern, ExecutionPattern.DUAL)

    def test_get_pattern_config_raises_on_invalid(self) -> None:
        with self.assertRaises(KeyError):
            get_pattern_config("nonexistent")  # type: ignore[arg-type]

    def test_resolve_pattern_valid(self) -> None:
        self.assertEqual(resolve_pattern("sonar"), ExecutionPattern.SONAR)

    def test_resolve_pattern_invalid(self) -> None:
        with self.assertRaises(ValueError):
            resolve_pattern("ultra")

    def test_patterns_using_consensus(self) -> None:
        patterns = patterns_using_consensus()
        self.assertIn(ExecutionPattern.CONSENSUS, patterns)
        self.assertIn(ExecutionPattern.MAXIMUM, patterns)
        self.assertNotIn(ExecutionPattern.SONAR, patterns)

    def test_patterns_using_roles(self) -> None:
        patterns = patterns_using_roles()
        self.assertIn(ExecutionPattern.FIVE_MODELS_COMPARE, patterns)
        self.assertIn(ExecutionPattern.CONSENSUS, patterns)
        self.assertIn(ExecutionPattern.MAXIMUM, patterns)
        self.assertNotIn(ExecutionPattern.SONAR, patterns)

    def test_pattern_is_str_enum(self) -> None:
        self.assertEqual(ExecutionPattern.SONAR, "sonar")

    def test_configs_are_frozen(self) -> None:
        config = PATTERN_CONFIGS[ExecutionPattern.SONAR]
        with self.assertRaises(FrozenInstanceError):
            config.quorum = 10  # type: ignore[misc]

    def test_all_configs_have_descriptions(self) -> None:
        for config in PATTERN_CONFIGS.values():
            self.assertGreater(len(config.description), 10)


if __name__ == "__main__":
    unittest.main()
