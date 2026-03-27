from __future__ import annotations

import unittest

from gracekelly.core.peer_review import (
    anonymize_responses,
    format_review_prompt,
    parse_ranking,
)


class AnonymizeEdgeCasesTests(unittest.TestCase):
    def test_empty_responses(self) -> None:
        result = anonymize_responses([])
        self.assertEqual(result, [])

    def test_single_response_gets_label_a(self) -> None:
        result = anonymize_responses(["only answer"])
        self.assertEqual(result[0].label, "A")
        self.assertEqual(result[0].original_index, 0)

    def test_exactly_ten_responses_all_letters(self) -> None:
        responses = [f"answer {i}" for i in range(10)]
        result = anonymize_responses(responses)
        self.assertEqual(result[9].label, "J")
        # All should be letters, not R-format
        self.assertTrue(all(not r.label.startswith("R") for r in result))

    def test_eleventh_response_gets_r_format(self) -> None:
        responses = [f"answer {i}" for i in range(11)]
        result = anonymize_responses(responses)
        self.assertEqual(result[10].label, "R10")

    def test_large_index_r_format(self) -> None:
        responses = [f"answer {i}" for i in range(100)]
        result = anonymize_responses(responses)
        self.assertEqual(result[99].label, "R99")

    def test_boundary_index_nine_is_last_letter(self) -> None:
        responses = [f"a{i}" for i in range(10)]
        result = anonymize_responses(responses)
        self.assertEqual(result[9].label, "J")
        self.assertEqual(result[9].original_index, 9)


class FormatReviewPromptEdgeCasesTests(unittest.TestCase):
    def test_reviewer_is_only_response_visible_empty(self) -> None:
        anonymized = anonymize_responses(["solo answer"])
        prompt = format_review_prompt("Test question?", anonymized, reviewer_index=0)
        # No other answers visible → prompt still formed, just has the ranking line
        self.assertIn("Rank these answers", prompt.user_prompt)

    def test_out_of_bounds_reviewer_index_excludes_nothing(self) -> None:
        """reviewer_index > len-1 means no actual response is excluded."""
        anonymized = anonymize_responses(["ans A", "ans B"])
        prompt = format_review_prompt("Q?", anonymized, reviewer_index=99)
        # Both A and B should be visible since neither has original_index == 99
        self.assertIn("Answer A", prompt.user_prompt)
        self.assertIn("Answer B", prompt.user_prompt)

    def test_negative_reviewer_index_excludes_nothing(self) -> None:
        anonymized = anonymize_responses(["ans A", "ans B"])
        prompt = format_review_prompt("Q?", anonymized, reviewer_index=-1)
        self.assertIn("Answer A", prompt.user_prompt)
        self.assertIn("Answer B", prompt.user_prompt)

    def test_reviewer_index_recorded_in_result(self) -> None:
        anonymized = anonymize_responses(["ans A", "ans B", "ans C"])
        prompt = format_review_prompt("Q?", anonymized, reviewer_index=1)
        self.assertEqual(prompt.reviewer_index, 1)
        self.assertEqual(prompt.excluded_index, 1)

    def test_question_appears_in_prompt(self) -> None:
        anonymized = anonymize_responses(["ans"])
        prompt = format_review_prompt("What is AI?", anonymized, reviewer_index=99)
        self.assertIn("What is AI?", prompt.user_prompt)

    def test_two_of_three_visible(self) -> None:
        anonymized = anonymize_responses(["A-text", "B-text", "C-text"])
        prompt = format_review_prompt("Q", anonymized, reviewer_index=1)
        self.assertIn("Answer A", prompt.user_prompt)
        self.assertNotIn("Answer B", prompt.user_prompt)
        self.assertIn("Answer C", prompt.user_prompt)


class ParseRankingEdgeCasesTests(unittest.TestCase):
    def test_whitespace_only_returns_empty(self) -> None:
        self.assertEqual(parse_ranking("   "), [])

    def test_whitespace_only_commas_returns_empty(self) -> None:
        self.assertEqual(parse_ranking("  ,  ,  "), [])

    def test_single_label_no_comma(self) -> None:
        self.assertEqual(parse_ranking("A"), ["A"])

    def test_labels_with_internal_spaces(self) -> None:
        result = parse_ranking("A , B , C")
        self.assertEqual(result, ["A", "B", "C"])

    def test_trailing_comma_ignored(self) -> None:
        result = parse_ranking("A,B,C,")
        self.assertEqual(result, ["A", "B", "C"])

    def test_leading_comma_ignored(self) -> None:
        result = parse_ranking(",A,B")
        self.assertEqual(result, ["A", "B"])

    def test_mixed_case_preserved(self) -> None:
        result = parse_ranking("R10, R11")
        self.assertEqual(result, ["R10", "R11"])

    def test_empty_string_returns_empty(self) -> None:
        self.assertEqual(parse_ranking(""), [])


if __name__ == "__main__":
    unittest.main()
