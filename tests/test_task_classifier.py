from __future__ import annotations

import unittest

from gracekelly.core.task_classifier import TaskType, classify_task


class TaskClassifierTests(unittest.TestCase):
    def test_python_function_is_coding(self) -> None:
        self.assertEqual(classify_task("Write a Python function to sort a list"), TaskType.CODING)

    def test_debug_is_coding(self) -> None:
        self.assertEqual(classify_task("Debug this error in my code"), TaskType.CODING)

    def test_calculate_integral_is_math(self) -> None:
        self.assertEqual(classify_task("Calculate the integral of x^2"), TaskType.MATH)

    def test_prove_theorem_is_math(self) -> None:
        self.assertEqual(classify_task("Prove the Pythagorean theorem"), TaskType.MATH)

    def test_analyze_market_is_analysis(self) -> None:
        self.assertEqual(classify_task("Analyze market trends for Q4"), TaskType.ANALYSIS)

    def test_compare_is_analysis(self) -> None:
        self.assertEqual(classify_task("Compare React and Vue frameworks"), TaskType.ANALYSIS)

    def test_research_papers_is_research(self) -> None:
        self.assertEqual(classify_task("Research papers on transformer architectures"), TaskType.RESEARCH)

    def test_write_poem_is_creative(self) -> None:
        self.assertEqual(classify_task("Write a poem about spring"), TaskType.CREATIVE)

    def test_brainstorm_is_creative(self) -> None:
        self.assertEqual(classify_task("Brainstorm ideas for a startup"), TaskType.CREATIVE)

    def test_hello_world_is_general(self) -> None:
        self.assertEqual(classify_task("Hello, how are you?"), TaskType.GENERAL)

    def test_case_insensitive(self) -> None:
        self.assertEqual(classify_task("WRITE PYTHON CODE"), TaskType.CODING)

    def test_coding_beats_creative(self) -> None:
        self.assertEqual(classify_task("Write code for a game"), TaskType.CODING)

    def test_coding_beats_analysis(self) -> None:
        self.assertEqual(classify_task("Analyze this code for bugs"), TaskType.CODING)

    def test_empty_string_is_general(self) -> None:
        self.assertEqual(classify_task(""), TaskType.GENERAL)

    def test_whitespace_is_general(self) -> None:
        self.assertEqual(classify_task("   "), TaskType.GENERAL)

    def test_word_boundary_no_substring(self) -> None:
        self.assertEqual(classify_task("I need to decode this message"), TaskType.GENERAL)

    def test_task_type_is_str_enum(self) -> None:
        self.assertEqual(TaskType.CODING, "coding")

    def test_all_task_types_count(self) -> None:
        self.assertEqual(len(TaskType), 6)


if __name__ == "__main__":
    unittest.main()
