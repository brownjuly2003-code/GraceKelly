from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import Mock

from gracekelly.core.complexity import assess_complexity
from gracekelly.core.decomposition import (
    DecompositionResult,
    SubTask,
    decompose_prompt,
    execute_decomposed,
)

SIMPLE_PROMPT = "What is 2+2?"
COMPLEX_PROMPT = (
    "Compare and analyze the relationship between inflation and unemployment, "
    "evaluate the trade-off between short-term interventions and long-term policy, "
    "and explain the consequences across multiple aspects from different perspectives."
)


class DecompositionTests(unittest.TestCase):
    def test_simple_prompt_not_decomposed(self) -> None:
        execute_fn = Mock(return_value="4")

        result = execute_decomposed(SIMPLE_PROMPT, execute_fn)

        self.assertFalse(result.was_decomposed)
        self.assertEqual(1, len(result.subtasks))

    def test_simple_prompt_no_llm_decomposition_call(self) -> None:
        execute_fn = Mock(return_value="4")

        execute_decomposed(SIMPLE_PROMPT, execute_fn)

        self.assertEqual(1, execute_fn.call_count)

    def test_complex_prompt_decomposed(self) -> None:
        execute_fn = Mock(
            side_effect=[
                '["subtask 1", "subtask 2", "subtask 3"]',
                "answer 1",
                "answer 2",
                "answer 3",
                "final",
            ]
        )

        result = execute_decomposed(COMPLEX_PROMPT, execute_fn)

        self.assertTrue(result.was_decomposed)
        self.assertEqual(3, len(result.subtasks))

    def test_decompose_invalid_json_fallback(self) -> None:
        execute_fn = Mock(return_value="not json")

        result = decompose_prompt(COMPLEX_PROMPT, execute_fn)

        self.assertEqual(1, len(result))

    def test_decompose_empty_array_fallback(self) -> None:
        execute_fn = Mock(return_value="[]")

        result = decompose_prompt(COMPLEX_PROMPT, execute_fn)

        self.assertEqual(1, len(result))

    def test_subtask_index_sequential(self) -> None:
        execute_fn = Mock(return_value='["subtask 1", "subtask 2", "subtask 3"]')

        result = decompose_prompt(COMPLEX_PROMPT, execute_fn)

        self.assertEqual([0, 1, 2], [subtask.index for subtask in result])

    def test_synthesis_called_when_decomposed(self) -> None:
        execute_fn = Mock(
            side_effect=[
                '["subtask 1", "subtask 2", "subtask 3"]',
                "answer 1",
                "answer 2",
                "answer 3",
                "final",
            ]
        )

        execute_decomposed(COMPLEX_PROMPT, execute_fn)

        self.assertEqual(5, execute_fn.call_count)

    def test_no_synthesis_when_not_decomposed(self) -> None:
        execute_fn = Mock(return_value="4")

        execute_decomposed(SIMPLE_PROMPT, execute_fn)

        self.assertEqual(1, execute_fn.call_count)

    def test_final_answer_is_synthesis(self) -> None:
        execute_fn = Mock(
            side_effect=[
                '["subtask 1", "subtask 2", "subtask 3"]',
                "answer 1",
                "answer 2",
                "answer 3",
                "synthesis result",
            ]
        )

        result = execute_decomposed(COMPLEX_PROMPT, execute_fn)

        self.assertEqual("synthesis result", result.final_answer)

    def test_final_answer_is_direct_when_simple(self) -> None:
        execute_fn = Mock(return_value="4")

        result = execute_decomposed(SIMPLE_PROMPT, execute_fn)

        self.assertEqual("4", result.final_answer)

    def test_result_is_frozen(self) -> None:
        result = DecompositionResult(
            original_prompt="prompt",
            complexity_level=assess_complexity("prompt").level,
            was_decomposed=False,
            subtasks=(),
            subtask_results=(),
            final_answer="answer",
        )

        with self.assertRaises(FrozenInstanceError):
            result.final_answer = "changed"

    def test_subtask_is_frozen(self) -> None:
        subtask = SubTask(index=0, prompt="prompt")

        with self.assertRaises(FrozenInstanceError):
            subtask.prompt = "changed"

    def test_execute_fn_call_count_decomposed(self) -> None:
        execute_fn = Mock(
            side_effect=[
                '["subtask 1", "subtask 2", "subtask 3"]',
                "answer 1",
                "answer 2",
                "answer 3",
                "final",
            ]
        )

        execute_decomposed(COMPLEX_PROMPT, execute_fn)

        self.assertEqual(5, execute_fn.call_count)

    def test_complexity_level_preserved(self) -> None:
        execute_fn = Mock(return_value="4")

        result = execute_decomposed(SIMPLE_PROMPT, execute_fn)

        self.assertEqual(assess_complexity(SIMPLE_PROMPT).level, result.complexity_level)


if __name__ == "__main__":
    unittest.main()
