from __future__ import annotations

import unittest

from hypothesis import given, settings
from hypothesis import strategies as st


class HacClusterPropertiesTests(unittest.TestCase):
    @given(
        st.lists(
            st.lists(
                st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
                min_size=3,
                max_size=3,
            ),
            min_size=1,
            max_size=10,
        ),
        st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=50, deadline=5000)
    def test_cluster_count_in_valid_range(self, vectors: list[list[float]], threshold: float) -> None:
        from gracekelly.core.clustering_hac import hac_cluster
        from gracekelly.core.similarity import pairwise_similarity_matrix

        matrix = pairwise_similarity_matrix(vectors)
        result = hac_cluster(matrix, threshold)
        self.assertGreaterEqual(result.num_clusters, 1)
        self.assertLessEqual(result.num_clusters, len(vectors))

    @given(
        st.lists(
            st.lists(
                st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
                min_size=3,
                max_size=3,
            ),
            min_size=1,
            max_size=10,
        ),
        st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=50, deadline=5000)
    def test_all_indices_appear_in_some_cluster(self, vectors: list[list[float]], threshold: float) -> None:
        from gracekelly.core.clustering_hac import hac_cluster
        from gracekelly.core.similarity import pairwise_similarity_matrix

        matrix = pairwise_similarity_matrix(vectors)
        result = hac_cluster(matrix, threshold)
        all_clustered = {index for cluster in result.clusters for index in cluster}
        self.assertEqual(all_clustered, set(range(len(vectors))))

    @given(
        st.lists(
            st.lists(
                st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
                min_size=3,
                max_size=3,
            ),
            min_size=1,
            max_size=10,
        ),
        st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=50, deadline=5000)
    def test_cluster_confidence_stays_in_range(self, vectors: list[list[float]], threshold: float) -> None:
        from gracekelly.core.cluster_confidence import compute_cluster_confidence
        from gracekelly.core.clustering_hac import hac_cluster
        from gracekelly.core.similarity import pairwise_similarity_matrix

        matrix = pairwise_similarity_matrix(vectors)
        result = hac_cluster(matrix, threshold)
        confidence = compute_cluster_confidence(result.clusters, matrix)
        self.assertGreaterEqual(confidence.confidence, 0.0)
        self.assertLessEqual(confidence.confidence, 1.0 + 1e-9)


if __name__ == "__main__":
    unittest.main()
