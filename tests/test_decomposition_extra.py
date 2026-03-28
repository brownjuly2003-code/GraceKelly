from __future__ import annotations

import unittest
from unittest.mock import Mock

from gracekelly.core.decomposition import SubTask, decompose_prompt, execute_decomposed  # noqa: E501

COMPLEX_PROMPT = (
    "Compare and analyze the relationship between inflation and unemployment, "
    "evaluate the trade-off between short-term interventions and long-term policy, "
    "and explain the consequences across multiple aspects from different perspectives."
)

SIMPLE_PROMPT = "What is 2+2?"


class DecomposePromptNonStringItemsTests(unittest.TestCase):
    """JSON array containing non-string items should still produce SubTasks via str()."""

    def test_integer_items_converted_to_str(self) -> None:
        execute_fn = Mock(return_value="[1, 2, 3]")
        result = decompose_prompt(COMPLEX_PROMPT, execute_fn)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].prompt, "1")
        self.assertEqual(result[1].prompt, "2")

    def test_mixed_types_converted_to_str(self) -> None:
        execute_fn = Mock(return_value='["question one", 42, true]')
        result = decompose_prompt(COMPLEX_PROMPT, execute_fn)
        self.assertEqual(len(result), 3)
        self.assertIsInstance(result[1].prompt, str)

    def test_json_object_not_list_falls_back(self) -> None:
        execute_fn = Mock(return_value='{"key": "value"}')
        result = decompose_prompt(COMPLEX_PROMPT, execute_fn)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].prompt, COMPLEX_PROMPT)

    def test_json_null_falls_back(self) -> None:
        execute_fn = Mock(return_value="null")
        result = decompose_prompt(COMPLEX_PROMPT, execute_fn)
        self.assertEqual(len(result), 1)

    def test_json_array_with_single_item_not_decomposed(self) -> None:
        execute_fn = Mock(return_value='["only one"]')
        result = decompose_prompt(COMPLEX_PROMPT, execute_fn)
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], SubTask)

    def test_subtask_indices_always_sequential(self) -> None:
        execute_fn = Mock(return_value='["a", "b", "c", "d"]')
        result = decompose_prompt(COMPLEX_PROMPT, execute_fn)
        self.assertEqual([st.index for st in result], [0, 1, 2, 3])


class ExecuteDecomposedFallbackTests(unittest.TestCase):
    """execute_decomposed with complex prompt but LLM returns invalid JSON
    → was_decomposed=False, no synthesis call."""

    def test_invalid_json_fallback_not_decomposed(self) -> None:
        execute_fn = Mock(side_effect=["not valid json", "direct answer"])
        result = execute_decomposed(COMPLEX_PROMPT, execute_fn)
        self.assertFalse(result.was_decomposed)

    def test_invalid_json_fallback_final_answer_is_direct(self) -> None:
        execute_fn = Mock(side_effect=["not valid json", "direct answer"])
        result = execute_decomposed(COMPLEX_PROMPT, execute_fn)
        self.assertEqual(result.final_answer, "direct answer")

    def test_invalid_json_fallback_call_count(self) -> None:
        """Decompose call + 1 subtask call = 2 total (no synthesis)."""
        execute_fn = Mock(side_effect=["not valid json", "answer"])
        execute_decomposed(COMPLEX_PROMPT, execute_fn)
        self.assertEqual(execute_fn.call_count, 2)

    def test_empty_array_fallback_not_decomposed(self) -> None:
        execute_fn = Mock(side_effect=["[]", "answer"])
        result = execute_decomposed(COMPLEX_PROMPT, execute_fn)
        self.assertFalse(result.was_decomposed)
        self.assertEqual(result.final_answer, "answer")

    def test_subtask_results_tuple_on_fallback(self) -> None:
        execute_fn = Mock(side_effect=["[]", "my answer"])
        result = execute_decomposed(COMPLEX_PROMPT, execute_fn)
        self.assertIsInstance(result.subtask_results, tuple)
        self.assertEqual(result.subtask_results, ("my answer",))


class ExecuteDecomposedSynthesisPromptTests(unittest.TestCase):
    """Verify that synthesis prompt contains original question and sub-answers."""

    def test_synthesis_receives_original_prompt(self) -> None:
        received: list[str] = []

        def execute_fn(p: str) -> str:
            received.append(p)
            if len(received) == 1:
                return '["sub1", "sub2"]'
            if len(received) <= 3:
                return f"answer {len(received) - 1}"
            return "synthesis"

        result = execute_decomposed(COMPLEX_PROMPT, execute_fn)
        # Last call is synthesis — should mention original prompt
        synthesis_call = received[-1]
        self.assertIn(COMPLEX_PROMPT, synthesis_call)
        self.assertEqual(result.final_answer, "synthesis")

    def test_subtasks_tuple_length_matches_decomposition(self) -> None:
        execute_fn = Mock(
            side_effect=[
                '["q1", "q2"]',
                "a1",
                "a2",
                "final",
            ]
        )
        result = execute_decomposed(COMPLEX_PROMPT, execute_fn)
        self.assertEqual(len(result.subtasks), 2)
        self.assertEqual(len(result.subtask_results), 2)


if __name__ == "__main__":
    unittest.main()
