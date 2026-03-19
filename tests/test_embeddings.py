from __future__ import annotations

import hashlib
import json
import threading
import unittest
from unittest.mock import MagicMock, patch

from gracekelly.core.embeddings import EmbeddingsClient


def _mock_response(embedding: list[float]):
    response_data = {"data": [{"embedding": embedding}]}
    mock_resp = unittest.mock.MagicMock()
    mock_resp.read.return_value = json.dumps(response_data).encode("utf-8")
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = unittest.mock.MagicMock(return_value=False)
    return mock_resp


class EmbeddingsTests(unittest.TestCase):
    def test_embed_returns_list_of_floats(self) -> None:
        client = EmbeddingsClient(api_key="test-key")
        with patch("gracekelly.core.embeddings.request.urlopen", return_value=_mock_response([0.1, 0.2, 0.3])):
            result = client.embed("hello")
        self.assertEqual(result, [0.1, 0.2, 0.3])

    def test_embed_caches_result(self) -> None:
        client = EmbeddingsClient(api_key="test-key")
        with patch("gracekelly.core.embeddings.request.urlopen", return_value=_mock_response([0.1, 0.2, 0.3])) as mock_urlopen:
            client.embed("hello")
            client.embed("hello")
        self.assertEqual(mock_urlopen.call_count, 1)

    def test_embed_different_texts_not_cached(self) -> None:
        client = EmbeddingsClient(api_key="test-key")
        with patch("gracekelly.core.embeddings.request.urlopen", return_value=_mock_response([0.1, 0.2, 0.3])) as mock_urlopen:
            client.embed("a")
            client.embed("b")
        self.assertEqual(mock_urlopen.call_count, 2)

    def test_embed_batch_returns_list_of_lists(self) -> None:
        client = EmbeddingsClient(api_key="test-key")
        response = _mock_response([0.1, 0.2, 0.3])
        with patch("gracekelly.core.embeddings.request.urlopen", return_value=response):
            result = client.embed_batch(["a", "b"])
        self.assertEqual(result, [[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]])

    def test_cache_size_starts_at_zero(self) -> None:
        client = EmbeddingsClient(api_key="test-key")
        self.assertEqual(client.cache_size(), 0)

    def test_cache_size_after_embed(self) -> None:
        client = EmbeddingsClient(api_key="test-key")
        with patch("gracekelly.core.embeddings.request.urlopen", return_value=_mock_response([0.1, 0.2, 0.3])):
            client.embed("test")
        self.assertEqual(client.cache_size(), 1)

    def test_clear_cache(self) -> None:
        client = EmbeddingsClient(api_key="test-key")
        with patch("gracekelly.core.embeddings.request.urlopen", return_value=_mock_response([0.1, 0.2, 0.3])):
            client.embed("test")
        client.clear_cache()
        self.assertEqual(client.cache_size(), 0)

    def test_cache_key_is_sha256(self) -> None:
        client = EmbeddingsClient(api_key="test-key")
        text = "same text"
        expected_key = hashlib.sha256(text.encode("utf-8")).hexdigest()
        with patch("gracekelly.core.embeddings.request.urlopen", return_value=_mock_response([0.1, 0.2, 0.3])):
            client.embed(text)
        self.assertIn(expected_key, client._cache)

    def test_request_has_bearer_auth(self) -> None:
        client = EmbeddingsClient(api_key="secret-key")
        with patch("gracekelly.core.embeddings.request.urlopen", return_value=_mock_response([0.1, 0.2, 0.3])) as mock_urlopen:
            client.embed("hello")
        request_obj = mock_urlopen.call_args.args[0]
        self.assertEqual(request_obj.headers["Authorization"], "Bearer secret-key")

    def test_request_posts_to_embeddings_endpoint(self) -> None:
        client = EmbeddingsClient(api_key="test-key")
        with patch("gracekelly.core.embeddings.request.urlopen", return_value=_mock_response([0.1, 0.2, 0.3])) as mock_urlopen:
            client.embed("hello")
        request_obj = mock_urlopen.call_args.args[0]
        self.assertTrue(request_obj.full_url.endswith("/embeddings"))

    def test_request_sends_correct_model(self) -> None:
        client = EmbeddingsClient(api_key="test-key")
        with patch("gracekelly.core.embeddings.request.urlopen", return_value=_mock_response([0.1, 0.2, 0.3])) as mock_urlopen:
            client.embed("hello")
        request_obj = mock_urlopen.call_args.args[0]
        payload = json.loads(request_obj.data.decode("utf-8"))
        self.assertEqual(payload["model"], "mistral-embed")

    def test_thread_safety(self) -> None:
        client = EmbeddingsClient(api_key="test-key")
        errors: list[Exception] = []

        def worker(text: str) -> None:
            try:
                client.embed(text)
            except Exception as exc:
                errors.append(exc)

        with patch("gracekelly.core.embeddings.request.urlopen", return_value=_mock_response([0.1, 0.2, 0.3])):
            threads = [threading.Thread(target=worker, args=(f"text-{i}",)) for i in range(5)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        self.assertEqual(errors, [])
        self.assertLessEqual(client.cache_size(), 5)


if __name__ == "__main__":
    unittest.main()
