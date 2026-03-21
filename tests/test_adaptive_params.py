from __future__ import annotations

import unittest

from gracekelly.core.adaptive_params import (
    AdaptiveConsensusParams,
    _DEFAULT,
    _TASK_PARAMS,
    get_adaptive_params,
)
from gracekelly.core.task_classifier import TaskType


class TestAdaptiveParams(unittest.TestCase):
    def test_each_task_type_returns_params(self):
        for tt in TaskType:
            params = get_adaptive_params(tt)
            self.assertIsInstance(params, AdaptiveConsensusParams)

    def test_coding_strict(self):
        params = get_adaptive_params(TaskType.CODING)
        self.assertAlmostEqual(params.consensus_target, 0.95)
        self.assertTrue(params.use_debate)
        self.assertTrue(params.use_cross_pollination)

    def test_creative_loose(self):
        params = get_adaptive_params(TaskType.CREATIVE)
        self.assertAlmostEqual(params.consensus_target, 0.70)
        self.assertFalse(params.use_debate)
        self.assertFalse(params.use_cross_pollination)

    def test_math_params(self):
        params = get_adaptive_params(TaskType.MATH)
        self.assertAlmostEqual(params.consensus_target, 0.95)
        self.assertTrue(params.use_debate)
        self.assertFalse(params.use_cross_pollination)

    def test_general_default(self):
        params = get_adaptive_params(TaskType.GENERAL)
        self.assertAlmostEqual(params.consensus_target, 0.85)

    def test_all_positive_max_rounds(self):
        for tt in TaskType:
            params = get_adaptive_params(tt)
            self.assertGreater(params.max_rounds, 0)

    def test_all_positive_min_responses(self):
        for tt in TaskType:
            params = get_adaptive_params(tt)
            self.assertGreater(params.min_responses, 0)

    def test_consensus_target_in_range(self):
        for tt in TaskType:
            params = get_adaptive_params(tt)
            self.assertGreater(params.consensus_target, 0.0)
            self.assertLessEqual(params.consensus_target, 1.0)

    def test_default_params_structure(self):
        self.assertAlmostEqual(_DEFAULT.consensus_target, 0.85)
        self.assertEqual(_DEFAULT.max_rounds, 3)
        self.assertEqual(_DEFAULT.min_responses, 3)

    def test_all_task_types_covered(self):
        for tt in TaskType:
            self.assertIn(tt, _TASK_PARAMS)


if __name__ == "__main__":
    unittest.main()
