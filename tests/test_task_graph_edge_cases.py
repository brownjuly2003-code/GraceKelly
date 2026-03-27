from __future__ import annotations

import unittest

from gracekelly.core.task_graph import SubTask, SubTaskStatus, TaskGraph


def _task(task_id: str, *, deps: tuple[str, ...] = ()) -> SubTask:
    return SubTask(id=task_id, prompt=f"Do {task_id}", dependencies=deps)


class ReadyTasksEdgeCasesTests(unittest.TestCase):
    def test_task_with_nonexistent_dependency_is_ready(self) -> None:
        """Dep not in graph is silently ignored → task treated as ready."""
        g = TaskGraph()
        g.add_task(_task("t1", deps=("ghost",)))
        ready = g.ready_tasks()
        self.assertEqual(len(ready), 1)
        self.assertEqual(ready[0].id, "t1")

    def test_task_not_ready_when_dep_is_failed(self) -> None:
        g = TaskGraph()
        g.add_task(_task("t1"))
        g.add_task(_task("t2", deps=("t1",)))
        g.mark_failed("t1")
        # Only COMPLETED counts as met — FAILED does not
        ready = g.ready_tasks()
        ready_ids = [t.id for t in ready]
        self.assertNotIn("t2", ready_ids)

    def test_task_not_ready_when_dep_is_running(self) -> None:
        g = TaskGraph()
        g.add_task(_task("t1"))
        g.add_task(_task("t2", deps=("t1",)))
        t1 = g.get_task("t1")
        assert t1 is not None
        t1.status = SubTaskStatus.RUNNING
        ready = g.ready_tasks()
        ready_ids = [t.id for t in ready]
        self.assertNotIn("t2", ready_ids)

    def test_task_not_ready_when_dep_is_skipped(self) -> None:
        g = TaskGraph()
        g.add_task(_task("t1"))
        g.add_task(_task("t2", deps=("t1",)))
        t1 = g.get_task("t1")
        assert t1 is not None
        t1.status = SubTaskStatus.SKIPPED
        ready = g.ready_tasks()
        ready_ids = [t.id for t in ready]
        self.assertNotIn("t2", ready_ids)

    def test_empty_graph_returns_no_ready(self) -> None:
        g = TaskGraph()
        self.assertEqual(g.ready_tasks(), [])

    def test_multiple_nonexistent_deps_still_ready(self) -> None:
        g = TaskGraph()
        g.add_task(_task("t1", deps=("x", "y", "z")))
        ready = g.ready_tasks()
        self.assertEqual(len(ready), 1)


class MarkOperationsEdgeCasesTests(unittest.TestCase):
    def test_mark_completed_on_nonexistent_task_is_noop(self) -> None:
        g = TaskGraph()
        g.mark_completed("no-such-task", "result")
        # No exception, graph still empty
        self.assertEqual(g.task_count(), 0)

    def test_mark_failed_on_nonexistent_task_is_noop(self) -> None:
        g = TaskGraph()
        g.mark_failed("no-such-task")
        self.assertEqual(g.task_count(), 0)

    def test_mark_completed_updates_result(self) -> None:
        g = TaskGraph()
        g.add_task(_task("t1"))
        g.mark_completed("t1", "the answer")
        task = g.get_task("t1")
        assert task is not None
        self.assertEqual(task.result, "the answer")
        self.assertEqual(task.status, SubTaskStatus.COMPLETED)

    def test_mark_failed_sets_failed_status(self) -> None:
        g = TaskGraph()
        g.add_task(_task("t1"))
        g.mark_failed("t1")
        task = g.get_task("t1")
        assert task is not None
        self.assertEqual(task.status, SubTaskStatus.FAILED)


class IsCompleteEdgeCasesTests(unittest.TestCase):
    def test_empty_graph_is_complete(self) -> None:
        g = TaskGraph()
        self.assertTrue(g.is_complete())

    def test_skipped_tasks_count_as_done(self) -> None:
        g = TaskGraph()
        g.add_task(_task("t1"))
        g.add_task(_task("t2"))
        g.mark_completed("t1", "ok")
        t2 = g.get_task("t2")
        assert t2 is not None
        t2.status = SubTaskStatus.SKIPPED
        self.assertTrue(g.is_complete())

    def test_running_task_not_complete(self) -> None:
        g = TaskGraph()
        g.add_task(_task("t1"))
        t1 = g.get_task("t1")
        assert t1 is not None
        t1.status = SubTaskStatus.RUNNING
        self.assertFalse(g.is_complete())

    def test_mixed_completed_failed_skipped_is_complete(self) -> None:
        g = TaskGraph()
        for i in range(3):
            g.add_task(_task(f"t{i}"))
        g.mark_completed("t0", "ok")
        g.mark_failed("t1")
        t2 = g.get_task("t2")
        assert t2 is not None
        t2.status = SubTaskStatus.SKIPPED
        self.assertTrue(g.is_complete())


class TopologicalOrderEdgeCasesTests(unittest.TestCase):
    def test_single_task_order(self) -> None:
        g = TaskGraph()
        g.add_task(_task("t1"))
        self.assertEqual(g.topological_order(), ["t1"])

    def test_dep_on_nonexistent_task_not_in_order(self) -> None:
        """Non-existent deps are silently skipped in topological sort."""
        g = TaskGraph()
        g.add_task(_task("t1", deps=("ghost",)))
        order = g.topological_order()
        self.assertIn("t1", order)
        self.assertNotIn("ghost", order)

    def test_self_dependency_raises_cycle_error(self) -> None:
        g = TaskGraph()
        g.add_task(_task("t1", deps=("t1",)))
        with self.assertRaises(ValueError, msg="Cycle detected"):
            g.topological_order()

    def test_two_node_cycle_raises(self) -> None:
        g = TaskGraph()
        g.add_task(_task("a", deps=("b",)))
        g.add_task(_task("b", deps=("a",)))
        with self.assertRaises(ValueError):
            g.topological_order()

    def test_completed_count(self) -> None:
        g = TaskGraph()
        for i in range(4):
            g.add_task(_task(f"t{i}"))
        g.mark_completed("t0", "r")
        g.mark_completed("t2", "r")
        self.assertEqual(g.completed_count(), 2)


if __name__ == "__main__":
    unittest.main()
