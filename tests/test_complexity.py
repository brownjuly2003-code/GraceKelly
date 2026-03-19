from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from gracekelly.core.complexity import ComplexityLevel, assess_complexity


class ComplexityTests(unittest.TestCase):
    def test_empty_prompt_is_simple(self) -> None:
        result = assess_complexity("")
        self.assertEqual(result.level, ComplexityLevel.SIMPLE)
        self.assertEqual(result.score, 0.0)
        self.assertFalse(result.should_decompose)

    def test_whitespace_is_simple(self) -> None:
        result = assess_complexity("   ")
        self.assertEqual(result.level, ComplexityLevel.SIMPLE)
        self.assertEqual(result.score, 0.0)

    def test_short_question_is_simple(self) -> None:
        result = assess_complexity("What is Python?")
        self.assertEqual(result.level, ComplexityLevel.SIMPLE)

    def test_single_indicator_moderate(self) -> None:
        result = assess_complexity("Analyze the market trends")
        self.assertIn("analyze", result.indicators_found)

    def test_multiple_indicators_complex(self) -> None:
        result = assess_complexity(
            "Compare and evaluate the trade-off between speed and accuracy in a comprehensive detailed analysis "
            "that explains multiple implications and consequences across different perspectives for a large organization",
        )
        self.assertEqual(result.level, ComplexityLevel.COMPLEX)

    def test_long_prompt_affects_score(self) -> None:
        short_result = assess_complexity("Analyze these market trends today carefully")
        long_prompt = "Analyze " + "word " * 59
        long_result = assess_complexity(long_prompt)
        self.assertGreater(long_result.score, short_result.score)

    def test_decomposition_signal_detected(self) -> None:
        result = assess_complexity("Explain X and also describe Y additionally Z")
        self.assertTrue(result.should_decompose)

    def test_no_decomposition_for_simple(self) -> None:
        result = assess_complexity("What is 2+2?")
        self.assertFalse(result.should_decompose)

    def test_word_count_accurate(self) -> None:
        result = assess_complexity("one two three four five")
        self.assertEqual(result.word_count, 5)

    def test_case_insensitive(self) -> None:
        result = assess_complexity("COMPARE the ADVANTAGES AND DISADVANTAGES")
        self.assertIn("compare", result.indicators_found)

    def test_score_between_zero_and_one(self) -> None:
        result = assess_complexity("Analyze the relationship between X and Y")
        self.assertGreaterEqual(result.score, 0.0)
        self.assertLessEqual(result.score, 1.0)

    def test_indicators_found_is_tuple(self) -> None:
        result = assess_complexity("Analyze the market trends")
        self.assertIsInstance(result.indicators_found, tuple)

    def test_assessment_is_frozen(self) -> None:
        result = assess_complexity("Analyze the market trends")
        with self.assertRaises(FrozenInstanceError):
            result.level = "simple"  # type: ignore[misc]

    def test_complexity_level_is_str_enum(self) -> None:
        self.assertEqual(ComplexityLevel.SIMPLE, "simple")

    def test_complex_forces_decompose(self) -> None:
        result = assess_complexity(
            "Compare and evaluate the trade-off between speed and accuracy in a comprehensive detailed analysis "
            "that explains multiple implications and consequences across different perspectives for a large organization",
        )
        self.assertEqual(result.level, ComplexityLevel.COMPLEX)
        self.assertTrue(result.should_decompose)

    def test_regex_indicator_how_does_affect(self) -> None:
        result = assess_complexity("How does inflation affect housing prices?")
        self.assertIn("how does .+ affect", result.indicators_found)

    def test_all_complexity_levels_count(self) -> None:
        self.assertEqual(len(ComplexityLevel), 3)


if __name__ == "__main__":
    unittest.main()
