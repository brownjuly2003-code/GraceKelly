from __future__ import annotations

import unittest

from gracekelly.core.cross_pollination import (
    build_cross_pollination_prompt,
    cross_pollinate,
)


class TestCrossPollination(unittest.TestCase):
    def test_empty_returns_no_pollination(self) -> None:
        result = cross_pollinate("q", [], (), lambda x: x)
        self.assertEqual(result.num_pollinated, 0)
        self.assertEqual(result.refined_responses, ())

    def test_empty_clusters(self) -> None:
        result = cross_pollinate("q", ["a", "b"], (), lambda x: x)
        self.assertEqual(result.num_pollinated, 0)

    def test_all_one_cluster_no_pollination(self) -> None:
        clusters = ((0, 1, 2),)
        responses = ["a", "b", "c"]
        result = cross_pollinate("q", responses, clusters, lambda x: "refined")
        self.assertEqual(result.num_pollinated, 0)
        self.assertEqual(result.refined_responses, ("a", "b", "c"))

    def test_split_clusters_pollinate_non_top(self) -> None:
        clusters = ((0, 1), (2,))
        responses = ["top1", "top2", "other"]
        calls: list[str] = []

        def mock_fn(prompt: str) -> str:
            calls.append(prompt)
            return "refined_other"

        result = cross_pollinate("q", responses, clusters, mock_fn)
        self.assertEqual(result.num_pollinated, 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result.refined_responses[2], "refined_other")

    def test_top_cluster_not_modified(self) -> None:
        clusters = ((0, 1), (2,))
        responses = ["top1", "top2", "other"]
        result = cross_pollinate("q", responses, clusters, lambda x: "changed")
        self.assertEqual(result.refined_responses[0], "top1")
        self.assertEqual(result.refined_responses[1], "top2")

    def test_pollinated_count_matches_non_top(self) -> None:
        clusters = ((0,), (1,), (2,))
        responses = ["a", "b", "c"]
        result = cross_pollinate("q", responses, clusters, lambda x: "r")
        self.assertEqual(result.num_pollinated, 2)
        self.assertEqual(result.original_indices, (1, 2))

    def test_prompt_contains_all_parts(self) -> None:
        prompt = build_cross_pollination_prompt("q", "top", "other")
        self.assertIn("q", prompt)
        self.assertIn("top", prompt)
        self.assertIn("other", prompt)

    def test_multiple_non_top_clusters(self) -> None:
        clusters = ((0, 1), (2,), (3,))
        responses = ["a", "b", "c", "d"]
        calls: list[str] = []
        result = cross_pollinate(
            "q", responses, clusters, lambda x: (calls.append(x), "r")[1]
        )
        self.assertEqual(result.num_pollinated, 2)
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
