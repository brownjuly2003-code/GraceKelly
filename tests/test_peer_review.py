from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from gracekelly.core.peer_review import (
    anonymize_responses,
    format_review_prompt,
    parse_ranking,
)


class PeerReviewTests(unittest.TestCase):
    def test_anonymize_labels(self) -> None:
        responses = anonymize_responses(["one", "two", "three"])
        self.assertEqual([response.label for response in responses], ["A", "B", "C"])

    def test_anonymize_preserves_text(self) -> None:
        responses = anonymize_responses(["first", "second"])
        self.assertEqual([response.text for response in responses], ["first", "second"])

    def test_anonymize_original_index(self) -> None:
        responses = anonymize_responses(["one", "two", "three"])
        self.assertEqual([response.original_index for response in responses], [0, 1, 2])

    def test_anonymize_more_than_ten(self) -> None:
        responses = anonymize_responses([str(i) for i in range(11)])
        self.assertEqual(responses[10].label, "R10")

    def test_format_excludes_reviewer(self) -> None:
        anonymized = anonymize_responses(["alpha", "beta", "gamma"])
        prompt = format_review_prompt("Which is best?", anonymized, reviewer_index=1)
        self.assertNotIn("--- Answer B ---", prompt.user_prompt)

    def test_format_includes_others(self) -> None:
        anonymized = anonymize_responses(["alpha", "beta", "gamma"])
        prompt = format_review_prompt("Which is best?", anonymized, reviewer_index=0)
        self.assertIn("--- Answer B ---", prompt.user_prompt)
        self.assertIn("--- Answer C ---", prompt.user_prompt)

    def test_format_system_prompt(self) -> None:
        anonymized = anonymize_responses(["alpha", "beta"])
        prompt = format_review_prompt("Which is best?", anonymized, reviewer_index=0)
        self.assertIn("peer reviewer", prompt.system_prompt.lower())

    def test_format_contains_question(self) -> None:
        anonymized = anonymize_responses(["alpha", "beta"])
        prompt = format_review_prompt("Which is best?", anonymized, reviewer_index=0)
        self.assertTrue(prompt.user_prompt.startswith("Question: Which is best?"))

    def test_format_reviewer_index(self) -> None:
        anonymized = anonymize_responses(["alpha", "beta"])
        prompt = format_review_prompt("Which is best?", anonymized, reviewer_index=1)
        self.assertEqual(prompt.reviewer_index, 1)

    def test_parse_ranking_simple(self) -> None:
        self.assertEqual(parse_ranking("B, A, C"), ["B", "A", "C"])

    def test_parse_ranking_no_spaces(self) -> None:
        self.assertEqual(parse_ranking("B,A,C"), ["B", "A", "C"])

    def test_parse_ranking_empty(self) -> None:
        self.assertEqual(parse_ranking(""), [])

    def test_anonymized_response_is_frozen(self) -> None:
        response = anonymize_responses(["alpha"])[0]
        with self.assertRaises(FrozenInstanceError):
            response.label = "X"  # type: ignore[misc]

    def test_peer_review_prompt_is_frozen(self) -> None:
        prompt = format_review_prompt("Which is best?", anonymize_responses(["alpha", "beta"]), reviewer_index=0)
        with self.assertRaises(FrozenInstanceError):
            prompt.system_prompt = "X"  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
