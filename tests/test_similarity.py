from __future__ import annotations

import unittest

from gracekelly.core.similarity import (
    cosine_similarity,
    find_clusters_greedy,
    pairwise_similarity_matrix,
)


class SimilarityTests(unittest.TestCase):
    def test_identical_vectors(self) -> None:
        self.assertEqual(cosine_similarity([1, 0, 0], [1, 0, 0]), 1.0)

    def test_orthogonal_vectors(self) -> None:
        self.assertEqual(cosine_similarity([1, 0], [0, 1]), 0.0)

    def test_opposite_vectors(self) -> None:
        self.assertEqual(cosine_similarity([1, 0], [-1, 0]), -1.0)

    def test_similar_vectors(self) -> None:
        self.assertGreater(cosine_similarity([1, 2, 3], [1, 2, 4]), 0.99)

    def test_length_mismatch_raises(self) -> None:
        with self.assertRaises(ValueError):
            cosine_similarity([1, 2], [1, 2, 3])

    def test_zero_vector_returns_zero(self) -> None:
        self.assertEqual(cosine_similarity([0, 0, 0], [1, 2, 3]), 0.0)

    def test_pairwise_matrix_diagonal_is_ones(self) -> None:
        matrix = pairwise_similarity_matrix([[1, 0], [0, 1], [1, 1]])
        self.assertEqual([matrix[i][i] for i in range(3)], [1.0, 1.0, 1.0])

    def test_pairwise_matrix_is_symmetric(self) -> None:
        matrix = pairwise_similarity_matrix([[1, 0], [0, 1], [1, 1]])
        for i in range(3):
            for j in range(3):
                self.assertEqual(matrix[i][j], matrix[j][i])

    def test_pairwise_matrix_size(self) -> None:
        matrix = pairwise_similarity_matrix([[1, 0], [0, 1], [1, 1]])
        self.assertEqual(len(matrix), 3)
        self.assertEqual(len(matrix[0]), 3)

    def test_find_clusters_identical(self) -> None:
        clusters = find_clusters_greedy([[1, 0], [1, 0], [1, 0]])
        self.assertEqual(len(clusters), 1)
        self.assertEqual(len(clusters[0]), 3)

    def test_find_clusters_distinct(self) -> None:
        clusters = find_clusters_greedy([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
        self.assertEqual(len(clusters), 3)
        self.assertEqual([len(cluster) for cluster in clusters], [1, 1, 1])

    def test_find_clusters_empty(self) -> None:
        self.assertEqual(find_clusters_greedy([]), [])

    def test_find_clusters_threshold(self) -> None:
        clusters = find_clusters_greedy([[1.0, 0.0], [0.9, 0.1], [0.0, 1.0]], threshold=0.85)
        self.assertEqual(len(clusters), 2)
        self.assertEqual(sorted(len(cluster) for cluster in clusters), [1, 2])

    def test_find_clusters_all_assigned(self) -> None:
        vectors = [[1.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.0, 1.0]]
        clusters = find_clusters_greedy(vectors)
        self.assertEqual(sum(len(cluster) for cluster in clusters), len(vectors))


if __name__ == "__main__":
    unittest.main()
