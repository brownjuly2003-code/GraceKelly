from __future__ import annotations

import unittest

from hypothesis import given, settings
from hypothesis import strategies as st


class SimilarityPropertiesTests(unittest.TestCase):
    @given(st.integers(min_value=1, max_value=20), st.data())
    @settings(max_examples=50, deadline=2000)
    def test_cosine_similarity_symmetry(self, size: int, data: st.DataObject) -> None:
        from gracekelly.core.similarity import cosine_similarity

        a = data.draw(
            st.lists(
                st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
                min_size=size,
                max_size=size,
            ),
            label="a",
        )
        b = data.draw(
            st.lists(
                st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
                min_size=size,
                max_size=size,
            ),
            label="b",
        )

        score_ab = cosine_similarity(a, b)
        score_ba = cosine_similarity(b, a)
        self.assertAlmostEqual(score_ab, score_ba, places=10)

    @given(
        st.lists(
            st.floats(min_value=1e-6, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=20,
        )
    )
    @settings(max_examples=50, deadline=2000)
    def test_self_similarity_is_one_for_non_zero_vector(self, vector: list[float]) -> None:
        from gracekelly.core.similarity import cosine_similarity

        score = cosine_similarity(vector, vector)
        self.assertAlmostEqual(score, 1.0, places=6)

    @given(
        st.lists(
            st.text(min_size=0, max_size=200),
            min_size=0,
            max_size=20,
        )
    )
    @settings(max_examples=50, deadline=2000)
    def test_batch_confidence_scores_stay_normalized(self, texts: list[str]) -> None:
        from gracekelly.core.confidence import extract_batch_confidence

        scores = extract_batch_confidence(texts)
        self.assertEqual(len(scores), len(texts))
        for score in scores:
            self.assertGreaterEqual(score.normalized_score, 0.0)
            self.assertLessEqual(score.normalized_score, 1.0)


if __name__ == "__main__":
    unittest.main()
