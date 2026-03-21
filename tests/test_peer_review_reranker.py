from __future__ import annotations

import unittest

from gracekelly.core.peer_review_reranker import (
    PeerRanking,
    build_review_prompt,
    parse_rankings,
    rerank_cluster,
)


class TestBuildReviewPrompt(unittest.TestCase):
    def test_contains_all_responses(self) -> None:
        prompt = build_review_prompt("question?", ["resp1", "resp2", "resp3"])
        self.assertIn("resp1", prompt)
        self.assertIn("resp2", prompt)
        self.assertIn("resp3", prompt)

    def test_contains_original_prompt(self) -> None:
        prompt = build_review_prompt("my question", ["a"])
        self.assertIn("my question", prompt)

    def test_answer_labels(self) -> None:
        prompt = build_review_prompt("q", ["a", "b"])
        self.assertIn("[Answer 1]", prompt)
        self.assertIn("[Answer 2]", prompt)

    def test_truncates_long_responses(self) -> None:
        long_resp = "x" * 1000
        prompt = build_review_prompt("q", [long_resp])
        self.assertNotIn("x" * 1000, prompt)
        self.assertIn("x" * 500, prompt)


class TestParseRankings(unittest.TestCase):
    def test_standard_ranking(self) -> None:
        self.assertEqual(parse_rankings("2,1,3", 3), [1, 0, 2])

    def test_with_spaces(self) -> None:
        self.assertEqual(parse_rankings("1, 3, 2", 3), [0, 2, 1])

    def test_malformed_fills_missing(self) -> None:
        result = parse_rankings("garbage", 3)
        self.assertEqual(len(result), 3)
        self.assertEqual(sorted(result), [0, 1, 2])

    def test_duplicates_ignored(self) -> None:
        result = parse_rankings("1,1,2,3", 3)
        self.assertEqual(len(result), 3)
        self.assertEqual(len(set(result)), 3)

    def test_out_of_range_ignored(self) -> None:
        result = parse_rankings("5,1,2", 3)
        self.assertIn(0, result)
        self.assertIn(1, result)
        self.assertEqual(len(result), 3)

    def test_partial_ranking_filled(self) -> None:
        result = parse_rankings("2", 3)
        self.assertEqual(result[0], 1)
        self.assertEqual(len(result), 3)


class TestReRankCluster(unittest.TestCase):
    def test_clear_winner_rank_one(self) -> None:
        rankings = [[1, 0, 2], [1, 0, 2], [1, 0, 2]]
        result = rerank_cluster(["a", "b", "c"], rankings)
        self.assertEqual(result[0].response_index, 1)
        self.assertEqual(result[0].rank, 1)

    def test_tie_stable_ordering(self) -> None:
        rankings = [[0, 1], [1, 0]]
        result = rerank_cluster(["a", "b"], rankings)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0].rank, 1)
        self.assertEqual(result[1].rank, 2)
        self.assertEqual(result[0].score, result[1].score)
        self.assertLess(result[0].response_index, result[1].response_index)

    def test_single_response(self) -> None:
        result = rerank_cluster(["only"], [[0]])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].rank, 1)
        self.assertEqual(result[0].response_index, 0)

    def test_empty_responses(self) -> None:
        result = rerank_cluster([], [])
        self.assertEqual(result, [])

    def test_borda_scoring(self) -> None:
        rankings = [[0, 1, 2]]
        result = rerank_cluster(["a", "b", "c"], rankings)
        first = next(r for r in result if r.response_index == 0)
        second = next(r for r in result if r.response_index == 1)
        third = next(r for r in result if r.response_index == 2)
        self.assertAlmostEqual(first.score, 3.0)
        self.assertAlmostEqual(second.score, 2.0)
        self.assertAlmostEqual(third.score, 1.0)

    def test_multiple_rankings_aggregated(self) -> None:
        rankings = [[0, 1, 2], [2, 1, 0]]
        result = rerank_cluster(["a", "b", "c"], rankings)
        scores = {r.response_index: r.score for r in result}
        self.assertAlmostEqual(scores[0], 3.0 + 1.0)
        self.assertAlmostEqual(scores[1], 2.0 + 2.0)
        self.assertAlmostEqual(scores[2], 1.0 + 3.0)

    def test_result_is_peer_ranking(self) -> None:
        result = rerank_cluster(["a"], [[0]])
        self.assertIsInstance(result[0], PeerRanking)

    def test_ranks_are_sequential(self) -> None:
        rankings = [[2, 0, 1]]
        result = rerank_cluster(["a", "b", "c"], rankings)
        ranks = [r.rank for r in result]
        self.assertEqual(sorted(ranks), [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
