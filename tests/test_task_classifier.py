from __future__ import annotations

import unittest

from gracekelly.core.task_classifier import TaskType, classify_task


class ClassifyTaskGeneralTests(unittest.TestCase):
    def test_empty_string_returns_general(self) -> None:
        self.assertEqual(classify_task(""), TaskType.GENERAL)

    def test_whitespace_only_returns_general(self) -> None:
        self.assertEqual(classify_task("   "), TaskType.GENERAL)

    def test_no_keywords_returns_general(self) -> None:
        self.assertEqual(classify_task("hello world"), TaskType.GENERAL)

    def test_unknown_topic_returns_general(self) -> None:
        self.assertEqual(classify_task("what is the weather today"), TaskType.GENERAL)


class ClassifyTaskCodingTests(unittest.TestCase):
    def test_function_keyword_detected(self) -> None:
        self.assertEqual(classify_task("write a function"), TaskType.CODING)

    def test_python_keyword_detected(self) -> None:
        self.assertEqual(classify_task("PYTHON script"), TaskType.CODING)

    def test_debug_keyword_detected(self) -> None:
        self.assertEqual(classify_task("debug this issue"), TaskType.CODING)

    def test_sql_keyword_detected(self) -> None:
        self.assertEqual(classify_task("write a sql query"), TaskType.CODING)

    def test_bug_keyword_detected(self) -> None:
        self.assertEqual(classify_task("there is a bug here"), TaskType.CODING)

    def test_refactor_keyword_detected(self) -> None:
        self.assertEqual(classify_task("refactor this class"), TaskType.CODING)

    def test_case_insensitive_coding(self) -> None:
        self.assertEqual(classify_task("IMPLEMENT the API"), TaskType.CODING)

    def test_error_keyword_at_word_boundary(self) -> None:
        self.assertEqual(classify_task("fix the error message"), TaskType.CODING)


class ClassifyTaskMathTests(unittest.TestCase):
    def test_calculate_keyword_detected(self) -> None:
        self.assertEqual(classify_task("calculate the integral"), TaskType.MATH)

    def test_theorem_keyword_detected(self) -> None:
        self.assertEqual(classify_task("prove the theorem"), TaskType.MATH)

    def test_probability_keyword_detected(self) -> None:
        self.assertEqual(classify_task("what is the probability"), TaskType.MATH)

    def test_equation_keyword_detected(self) -> None:
        self.assertEqual(classify_task("solve this equation"), TaskType.MATH)


class ClassifyTaskAnalysisTests(unittest.TestCase):
    def test_analyze_keyword_detected(self) -> None:
        self.assertEqual(classify_task("analyze the data"), TaskType.ANALYSIS)

    def test_compare_keyword_detected(self) -> None:
        self.assertEqual(classify_task("compare the two options"), TaskType.ANALYSIS)

    def test_audit_keyword_detected(self) -> None:
        self.assertEqual(classify_task("audit the system"), TaskType.ANALYSIS)

    def test_review_keyword_detected(self) -> None:
        # "review" is ANALYSIS; no higher-priority keywords in this string
        self.assertEqual(classify_task("peer review the output"), TaskType.ANALYSIS)


class ClassifyTaskResearchTests(unittest.TestCase):
    def test_research_keyword_detected(self) -> None:
        self.assertEqual(classify_task("research the topic"), TaskType.RESEARCH)

    def test_paper_keyword_detected(self) -> None:
        self.assertEqual(classify_task("find a paper on this"), TaskType.RESEARCH)

    def test_evidence_keyword_detected(self) -> None:
        self.assertEqual(classify_task("what is the evidence"), TaskType.RESEARCH)

    def test_methodology_keyword_detected(self) -> None:
        self.assertEqual(classify_task("describe the methodology"), TaskType.RESEARCH)


class ClassifyTaskCreativeTests(unittest.TestCase):
    def test_poem_keyword_detected(self) -> None:
        self.assertEqual(classify_task("write a poem"), TaskType.CREATIVE)

    def test_story_keyword_detected(self) -> None:
        self.assertEqual(classify_task("tell me a story"), TaskType.CREATIVE)

    def test_brainstorm_keyword_detected(self) -> None:
        self.assertEqual(classify_task("brainstorm ideas"), TaskType.CREATIVE)

    def test_essay_keyword_detected(self) -> None:
        self.assertEqual(classify_task("write an essay"), TaskType.CREATIVE)


class ClassifyTaskPriorityTests(unittest.TestCase):
    """Verify priority order: CODING > MATH > ANALYSIS > RESEARCH > CREATIVE."""

    def test_coding_beats_creative_for_write_function(self) -> None:
        # "write" is CREATIVE but "function" is CODING — CODING wins
        self.assertEqual(classify_task("write a function in python"), TaskType.CODING)

    def test_coding_beats_creative_for_javascript_story(self) -> None:
        # "story" is CREATIVE but "javascript" is CODING — CODING wins
        self.assertEqual(classify_task("javascript story"), TaskType.CODING)

    def test_math_beats_research_for_prove_with_research(self) -> None:
        # "prove" is MATH; checked before RESEARCH
        self.assertEqual(classify_task("prove the theorem using research"), TaskType.MATH)

    def test_analysis_beats_creative_for_compare_narrative(self) -> None:
        # "compare" is ANALYSIS, "narrative" is CREATIVE — ANALYSIS wins
        self.assertEqual(classify_task("compare the narrative style"), TaskType.ANALYSIS)

    def test_research_beats_creative_for_paper_story(self) -> None:
        # "paper" is RESEARCH, "story" is CREATIVE — RESEARCH wins
        self.assertEqual(classify_task("the paper covers a story"), TaskType.RESEARCH)


class ClassifyTaskWordBoundaryTests(unittest.TestCase):
    """Keywords must not match as sub-words."""

    def test_api_not_matched_inside_rapid(self) -> None:
        # "rapid" has no word boundary before the 'a' in r-a-p-i-d
        self.assertEqual(classify_task("a rapid response"), TaskType.GENERAL)

    def test_code_not_matched_inside_decode(self) -> None:
        # "code" substring of "decode" — not at a word boundary
        self.assertEqual(classify_task("decode this value"), TaskType.GENERAL)

    def test_bug_not_matched_inside_debug(self) -> None:
        # "debug" contains "bug" — but "debug" itself IS in CODING keywords
        self.assertEqual(classify_task("debug the script"), TaskType.CODING)

    def test_standalone_code_word_matches(self) -> None:
        # When "code" is a standalone word it should match CODING
        self.assertEqual(classify_task("clean up the code"), TaskType.CODING)


if __name__ == "__main__":
    unittest.main()
