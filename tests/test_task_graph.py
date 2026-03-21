from __future__ import annotations

import unittest

from gracekelly.core.task_graph import SubTask, SubTaskStatus, TaskGraph


class TaskGraphTests(unittest.TestCase):
    def test_add_and_get(self) -> None:
        g = TaskGraph()
        g.add_task(SubTask(id="a", prompt="do A"))
        self.assertIsNotNone(g.get_task("a"))
        self.assertEqual("do A", g.get_task("a").prompt)

    def test_get_missing(self) -> None:
        g = TaskGraph()
        self.assertIsNone(g.get_task("nope"))

    def test_ready_no_deps(self) -> None:
        g = TaskGraph()
        g.add_task(SubTask(id="a", prompt="A"))
        g.add_task(SubTask(id="b", prompt="B"))
        self.assertEqual(2, len(g.ready_tasks()))

    def test_ready_with_unmet_dep(self) -> None:
        g = TaskGraph()
        g.add_task(SubTask(id="a", prompt="A"))
        g.add_task(SubTask(id="b", prompt="B", dependencies=("a",)))
        ready_ids = [t.id for t in g.ready_tasks()]
        self.assertIn("a", ready_ids)
        self.assertNotIn("b", ready_ids)

    def test_ready_after_dep_completed(self) -> None:
        g = TaskGraph()
        g.add_task(SubTask(id="a", prompt="A"))
        g.add_task(SubTask(id="b", prompt="B", dependencies=("a",)))
        g.mark_completed("a", "done")
        ready_ids = [t.id for t in g.ready_tasks()]
        self.assertIn("b", ready_ids)

    def test_mark_completed(self) -> None:
        g = TaskGraph()
        g.add_task(SubTask(id="a", prompt="A"))
        g.mark_completed("a", "result")
        self.assertEqual(SubTaskStatus.COMPLETED, g.get_task("a").status)
        self.assertEqual("result", g.get_task("a").result)

    def test_mark_failed(self) -> None:
        g = TaskGraph()
        g.add_task(SubTask(id="a", prompt="A"))
        g.mark_failed("a")
        self.assertEqual(SubTaskStatus.FAILED, g.get_task("a").status)

    def test_is_complete_all_done(self) -> None:
        g = TaskGraph()
        g.add_task(SubTask(id="a", prompt="A"))
        g.mark_completed("a", "ok")
        self.assertTrue(g.is_complete())

    def test_is_complete_pending(self) -> None:
        g = TaskGraph()
        g.add_task(SubTask(id="a", prompt="A"))
        self.assertFalse(g.is_complete())

    def test_is_complete_empty(self) -> None:
        self.assertTrue(TaskGraph().is_complete())

    def test_topological_linear(self) -> None:
        g = TaskGraph()
        g.add_task(SubTask(id="a", prompt="A"))
        g.add_task(SubTask(id="b", prompt="B", dependencies=("a",)))
        g.add_task(SubTask(id="c", prompt="C", dependencies=("b",)))
        order = g.topological_order()
        self.assertEqual(["a", "b", "c"], order)

    def test_topological_diamond(self) -> None:
        g = TaskGraph()
        g.add_task(SubTask(id="a", prompt="A"))
        g.add_task(SubTask(id="b", prompt="B", dependencies=("a",)))
        g.add_task(SubTask(id="c", prompt="C", dependencies=("a",)))
        g.add_task(SubTask(id="d", prompt="D", dependencies=("b", "c")))
        order = g.topological_order()
        self.assertEqual("a", order[0])
        self.assertEqual("d", order[-1])
        self.assertIn("b", order[1:3])
        self.assertIn("c", order[1:3])

    def test_topological_cycle(self) -> None:
        g = TaskGraph()
        g.add_task(SubTask(id="a", prompt="A", dependencies=("b",)))
        g.add_task(SubTask(id="b", prompt="B", dependencies=("a",)))
        with self.assertRaises(ValueError):
            g.topological_order()

    def test_task_count(self) -> None:
        g = TaskGraph()
        g.add_task(SubTask(id="a", prompt="A"))
        g.add_task(SubTask(id="b", prompt="B"))
        self.assertEqual(2, g.task_count())
        self.assertEqual(0, g.completed_count())
        g.mark_completed("a", "ok")
        self.assertEqual(1, g.completed_count())


if __name__ == "__main__":
    unittest.main()
