from __future__ import annotations

import unittest

from gracekelly.core.divergence import (
    DivergenceAction,
    DivergenceResult,
    assess_divergence,
)


class TestDivergence(unittest.TestCase):
    def test_high_score_accept(self):
        result = assess_divergence(0.95, 1, 0, 5)
        self.assertEqual(result.action, DivergenceAction.ACCEPT)
        self.assertEqual(result.extra_rounds_needed, 0)

    def test_moderate_score_debate(self):
        result = assess_divergence(0.75, 2, 0, 5)
        self.assertEqual(result.action, DivergenceAction.DEBATE)
        self.assertEqual(result.extra_rounds_needed, 0)

    def test_low_score_expand(self):
        result = assess_divergence(0.5, 3, 1, 5)
        self.assertEqual(result.action, DivergenceAction.EXPAND)
        self.assertGreater(result.extra_rounds_needed, 0)

    def test_low_score_at_max_escalate(self):
        result = assess_divergence(0.3, 4, 5, 5)
        self.assertEqual(result.action, DivergenceAction.ESCALATE)
        self.assertEqual(result.extra_rounds_needed, 0)

    def test_boundary_090_accept(self):
        result = assess_divergence(0.9, 1, 0, 5)
        self.assertEqual(result.action, DivergenceAction.ACCEPT)

    def test_boundary_070_debate(self):
        result = assess_divergence(0.7, 2, 0, 5)
        self.assertEqual(result.action, DivergenceAction.DEBATE)

    def test_extra_rounds_capped_at_3(self):
        result = assess_divergence(0.1, 5, 0, 10)
        self.assertLessEqual(result.extra_rounds_needed, 3)

    def test_reason_strings_not_empty(self):
        for score, rn, mx in [(0.95, 0, 5), (0.75, 0, 5), (0.5, 1, 5), (0.3, 5, 5)]:
            result = assess_divergence(score, 2, rn, mx)
            self.assertTrue(len(result.reason) > 0)

    def test_result_is_frozen(self):
        result = assess_divergence(0.95, 1, 0, 5)
        with self.assertRaises(AttributeError):
            result.action = DivergenceAction.ESCALATE

    def test_expand_extra_rounds_correct(self):
        result = assess_divergence(0.5, 3, 2, 4)
        self.assertEqual(result.extra_rounds_needed, 2)


if __name__ == "__main__":
    unittest.main()
