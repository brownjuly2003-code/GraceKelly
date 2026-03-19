from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from gracekelly.core.reliability import (
    RELIABILITY_CONFIGS,
    ReliabilityLevel,
    get_reliability_config,
    resolve_reliability_level,
)


class ReliabilityTests(unittest.TestCase):
    def test_all_levels_have_configs(self) -> None:
        for level in ReliabilityLevel:
            self.assertIn(level, RELIABILITY_CONFIGS)

    def test_config_count_matches_enum(self) -> None:
        self.assertEqual(len(RELIABILITY_CONFIGS), len(ReliabilityLevel))

    def test_quick_is_minimal(self) -> None:
        config = RELIABILITY_CONFIGS[ReliabilityLevel.QUICK]
        self.assertEqual(config.min_models, 1)
        self.assertFalse(config.use_consensus)
        self.assertFalse(config.use_devil_advocate)

    def test_standard_uses_two_models(self) -> None:
        config = RELIABILITY_CONFIGS[ReliabilityLevel.STANDARD]
        self.assertEqual(config.min_models, 2)
        self.assertTrue(config.use_confidence)

    def test_high_uses_consensus(self) -> None:
        config = RELIABILITY_CONFIGS[ReliabilityLevel.HIGH]
        self.assertTrue(config.use_consensus)
        self.assertEqual(config.consensus_threshold, 0.85)
        self.assertTrue(config.use_devil_advocate)

    def test_maximum_is_full(self) -> None:
        config = RELIABILITY_CONFIGS[ReliabilityLevel.MAXIMUM]
        self.assertEqual(config.min_models, 5)
        self.assertEqual(config.max_consensus_rounds, 5)
        self.assertTrue(config.use_peer_review)
        self.assertEqual(config.consensus_threshold, 0.95)

    def test_configs_are_frozen(self) -> None:
        config = RELIABILITY_CONFIGS[ReliabilityLevel.QUICK]
        with self.assertRaises(FrozenInstanceError):
            config.min_models = 10  # type: ignore[misc]

    def test_get_reliability_config(self) -> None:
        config = get_reliability_config(ReliabilityLevel.HIGH)
        self.assertEqual(config.level, ReliabilityLevel.HIGH)

    def test_get_reliability_config_raises_on_invalid(self) -> None:
        with self.assertRaises(KeyError):
            get_reliability_config("nonexistent")  # type: ignore[arg-type]

    def test_resolve_reliability_level_valid(self) -> None:
        self.assertEqual(resolve_reliability_level("quick"), ReliabilityLevel.QUICK)

    def test_resolve_reliability_level_invalid(self) -> None:
        with self.assertRaises(ValueError):
            resolve_reliability_level("ultra")

    def test_reliability_level_is_str_enum(self) -> None:
        self.assertEqual(ReliabilityLevel.QUICK, "quick")

    def test_all_configs_have_descriptions(self) -> None:
        for config in RELIABILITY_CONFIGS.values():
            self.assertGreater(len(config.description), 10)

    def test_consensus_threshold_increases_with_level(self) -> None:
        quick = RELIABILITY_CONFIGS[ReliabilityLevel.QUICK].consensus_threshold
        standard = RELIABILITY_CONFIGS[ReliabilityLevel.STANDARD].consensus_threshold
        high = RELIABILITY_CONFIGS[ReliabilityLevel.HIGH].consensus_threshold
        maximum = RELIABILITY_CONFIGS[ReliabilityLevel.MAXIMUM].consensus_threshold
        self.assertLessEqual(quick, standard)
        self.assertLessEqual(standard, high)
        self.assertLess(high, maximum)


if __name__ == "__main__":
    unittest.main()
