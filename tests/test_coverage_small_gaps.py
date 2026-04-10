"""Tests for small remaining coverage gaps: main and core modules."""

from __future__ import annotations

import unittest
from unittest.mock import patch


# ---------------------------------------------------------------------------
# main.py — _get_version exception branch (lines 71-72)
# ---------------------------------------------------------------------------
class GetVersionTests(unittest.TestCase):
    def test_returns_dev_version_when_importlib_fails(self) -> None:
        with patch("importlib.metadata.version", side_effect=Exception("not installed")):
            from gracekelly.main import _get_version

            result = _get_version()
            self.assertEqual(result, "0.0.0-dev")


# ---------------------------------------------------------------------------
# core/similarity.py — skip-assigned in cluster_indices (line 52)
# ---------------------------------------------------------------------------
class SimilaritySkipAssignedTests(unittest.TestCase):
    def test_already_assigned_item_skipped(self) -> None:
        from gracekelly.core.similarity import find_clusters_greedy

        # Vectors where 0,1 are similar; 1,2 are similar; 0,2 are NOT similar
        # Item 1 gets assigned with item 0 first → skip when processing item 2
        # Using unit vectors: [1,0], [0.9,0.44], [0,1]
        # cosine(v0,v1) ≈ 0.9, cosine(v1,v2) ≈ 0.44, cosine(v0,v2) = 0
        vectors = [[1.0, 0.0], [0.9, 0.436], [0.0, 1.0]]
        clusters = find_clusters_greedy(vectors, threshold=0.8)
        # Item 1 is already assigned to cluster [0,1], so cluster starting at 2
        # checks j=... → already assigned → skip → cluster [2] alone
        self.assertEqual(len(clusters), 2)
        self.assertIn(0, clusters[0])
        self.assertIn(1, clusters[0])
        self.assertEqual(clusters[1], [2])


# ---------------------------------------------------------------------------
# core/task_graph_executor.py — skip None task (line 29)
# ---------------------------------------------------------------------------
class TaskGraphExecutorSkipNoneTests(unittest.TestCase):
    def test_missing_task_in_graph_skipped(self) -> None:
        from gracekelly.core.task_graph import SubTask, TaskGraph
        from gracekelly.core.task_graph_executor import execute_graph

        graph = TaskGraph()
        graph.add_task(SubTask(id="t1", prompt="hello"))

        # Mock topological_order to return an extra non-existent task
        with patch.object(graph, "topological_order", return_value=["nonexistent", "t1"]):
            result = execute_graph(
                graph,
                execute_fn=lambda prompt: f"result: {prompt}",
            )
        # Only t1 should have a result
        self.assertIn("t1", result.results)
        self.assertNotIn("nonexistent", result.results)
