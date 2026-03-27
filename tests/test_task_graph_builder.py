from __future__ import annotations

import unittest

from gracekelly.core.task_graph_builder import (
    build_fan_out_fan_in,
    build_parallel,
    build_pipeline,
    build_sequential,
)


class BuildSequentialTests(unittest.TestCase):
    def test_chain_order(self) -> None:
        g = build_sequential(["A", "B", "C"])
        order = g.topological_order()
        self.assertEqual(["step-0", "step-1", "step-2"], order)

    def test_empty(self) -> None:
        g = build_sequential([])
        self.assertEqual(0, g.task_count())

    def test_dependencies(self) -> None:
        g = build_sequential(["A", "B"])
        self.assertEqual((), g.get_task("step-0").dependencies)
        self.assertEqual(("step-0",), g.get_task("step-1").dependencies)


class BuildParallelTests(unittest.TestCase):
    def test_all_ready(self) -> None:
        g = build_parallel(["A", "B", "C"])
        self.assertEqual(3, len(g.ready_tasks()))

    def test_no_dependencies(self) -> None:
        g = build_parallel(["A", "B"])
        for t in g.all_tasks():
            self.assertEqual((), t.dependencies)


class BuildFanOutFanInTests(unittest.TestCase):
    def test_synthesis_depends_on_all(self) -> None:
        g = build_fan_out_fan_in(["A", "B", "C"], "synthesize")
        synth = g.get_task("synthesis")
        self.assertEqual(("fan-0", "fan-1", "fan-2"), synth.dependencies)

    def test_synthesis_not_ready_initially(self) -> None:
        g = build_fan_out_fan_in(["A", "B"], "synthesize")
        ready_ids = [t.id for t in g.ready_tasks()]
        self.assertNotIn("synthesis", ready_ids)

    def test_synthesis_ready_after_fans_complete(self) -> None:
        g = build_fan_out_fan_in(["A", "B"], "synthesize")
        g.mark_completed("fan-0", "r0")
        g.mark_completed("fan-1", "r1")
        ready_ids = [t.id for t in g.ready_tasks()]
        self.assertIn("synthesis", ready_ids)


class BuildPipelineTests(unittest.TestCase):
    def test_two_stages(self) -> None:
        g = build_pipeline([["A1", "A2"], ["B1"]])
        self.assertEqual(3, g.task_count())
        b1 = g.get_task("stage-1-task-0")
        self.assertIn("stage-0-task-0", b1.dependencies)
        self.assertIn("stage-0-task-1", b1.dependencies)

    def test_stage2_blocked_until_stage1(self) -> None:
        g = build_pipeline([["A"], ["B"]])
        ready_ids = [t.id for t in g.ready_tasks()]
        self.assertIn("stage-0-task-0", ready_ids)
        self.assertNotIn("stage-1-task-0", ready_ids)

    def test_valid_topological_order(self) -> None:
        g = build_pipeline([["A", "B"], ["C"]])
        order = g.topological_order()
        self.assertEqual(3, len(order))


if __name__ == "__main__":
    unittest.main()
