from __future__ import annotations

import unittest

from gracekelly.core.task_graph import SubTaskStatus
from gracekelly.core.task_graph_builder import (
    build_fan_out_fan_in,
    build_parallel,
    build_sequential,
)
from gracekelly.core.task_graph_executor import execute_graph, TaskGraph


class ExecuteGraphTests(unittest.TestCase):
    def test_all_succeed(self) -> None:
        g = build_sequential(["A", "B", "C"])
        result = execute_graph(g, lambda p: f"done:{p}")
        self.assertEqual(3, result.completed)
        self.assertEqual(0, result.failed)
        self.assertEqual(0, result.skipped)
        self.assertTrue(result.is_complete)

    def test_results_dict(self) -> None:
        g = build_parallel(["X", "Y"])
        result = execute_graph(g, lambda p: p.upper())
        self.assertEqual("X", result.results["parallel-0"])
        self.assertEqual("Y", result.results["parallel-1"])

    def test_failure_skips_downstream(self) -> None:
        call_log = []

        def fn(p: str) -> str:
            call_log.append(p)
            if p == "B":
                raise RuntimeError("boom")
            return f"ok:{p}"

        g = build_sequential(["A", "B", "C"])
        result = execute_graph(g, fn)
        self.assertEqual(1, result.completed)
        self.assertEqual(1, result.failed)
        self.assertEqual(1, result.skipped)
        self.assertNotIn("step-2", result.results)

    def test_no_skip_on_failure(self) -> None:
        def fn(p: str) -> str:
            if p == "A":
                raise RuntimeError("boom")
            return f"ok:{p}"

        g = build_sequential(["A", "B"])
        result = execute_graph(g, fn, skip_on_dependency_failure=False)
        self.assertEqual(1, result.completed)
        self.assertEqual(1, result.failed)
        self.assertEqual(0, result.skipped)

    def test_parallel_one_failure(self) -> None:
        def fn(p: str) -> str:
            if p == "B":
                raise RuntimeError("boom")
            return "ok"

        g = build_parallel(["A", "B", "C"])
        result = execute_graph(g, fn)
        self.assertEqual(2, result.completed)
        self.assertEqual(1, result.failed)
        self.assertEqual(0, result.skipped)

    def test_fan_in_skipped_on_fan_failure(self) -> None:
        def fn(p: str) -> str:
            if p == "B":
                raise RuntimeError("boom")
            return "ok"

        g = build_fan_out_fan_in(["A", "B"], "synthesize")
        result = execute_graph(g, fn)
        self.assertEqual(1, result.completed)
        self.assertEqual(1, result.failed)
        self.assertEqual(1, result.skipped)
        synth = g.get_task("synthesis")
        self.assertEqual(SubTaskStatus.SKIPPED, synth.status)

    def test_empty_graph(self) -> None:
        g = TaskGraph()
        result = execute_graph(g, lambda p: p)
        self.assertEqual(0, result.total)
        self.assertEqual(0, result.completed)
        self.assertTrue(result.is_complete)

    def test_execute_fn_receives_prompt(self) -> None:
        prompts_seen = []

        def fn(p: str) -> str:
            prompts_seen.append(p)
            return "ok"

        g = build_sequential(["hello", "world"])
        execute_graph(g, fn)
        self.assertEqual(["hello", "world"], prompts_seen)

    def test_total_matches_graph(self) -> None:
        g = build_parallel(["A", "B", "C", "D"])
        result = execute_graph(g, lambda p: "ok")
        self.assertEqual(4, result.total)


if __name__ == "__main__":
    unittest.main()
