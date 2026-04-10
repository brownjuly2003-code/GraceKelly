from __future__ import annotations

import unittest

from gracekelly.core.debate_round import (
    build_challenge_prompt,
    build_defense_prompt,
    run_debate,
)


class TestDebateRound(unittest.TestCase):
    def test_basic_debate(self) -> None:
        calls: list[str] = []

        def mock_fn(prompt: str) -> str:
            calls.append(prompt)
            if len(calls) == 1:
                return "challenge_text"
            return "improved_text"

        result = run_debate("question", "answer", mock_fn)
        self.assertEqual(result.challenge, "challenge_text")
        self.assertEqual(result.defense, "improved_text")
        self.assertEqual(result.improved_response, "improved_text")

    def test_execute_fn_called_twice(self) -> None:
        call_count = 0

        def mock_fn(prompt: str) -> str:
            nonlocal call_count
            call_count += 1
            return f"response_{call_count}"

        run_debate("q", "a", mock_fn)
        self.assertEqual(call_count, 2)

    def test_challenge_prompt_contains_original_and_response(self) -> None:
        prompt = build_challenge_prompt("my question", "my answer")
        self.assertIn("my question", prompt)
        self.assertIn("my answer", prompt)
        self.assertIn("Devil's Advocate", prompt)

    def test_defense_prompt_contains_challenge(self) -> None:
        prompt = build_defense_prompt("q", "a", "the critique")
        self.assertIn("q", prompt)
        self.assertIn("a", prompt)
        self.assertIn("the critique", prompt)

    def test_improved_response_equals_defense(self) -> None:
        result = run_debate("q", "a", lambda x: "same")
        self.assertEqual(result.improved_response, result.defense)

    def test_rounds_used_is_one(self) -> None:
        result = run_debate("q", "a", lambda x: "r")
        self.assertEqual(result.rounds_used, 1)

    def test_result_is_frozen(self) -> None:
        result = run_debate("q", "a", lambda x: "r")
        with self.assertRaises(AttributeError):
            setattr(result, "rounds_used", 5)


if __name__ == "__main__":
    unittest.main()
