from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from gracekelly.core.embeddings import EmbeddingsClient


def _mock_response(embedding: list[float]):  # type: ignore[no-untyped-def]
    response_data = {"data": [{"embedding": embedding}]}
    mock_resp = unittest.mock.MagicMock()
    mock_resp.read.return_value = json.dumps(response_data).encode("utf-8")
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = unittest.mock.MagicMock(return_value=False)
    return mock_resp


class EmbeddingsClientHasApiKeyTests(unittest.TestCase):
    def test_has_api_key_true_when_set(self) -> None:
        client = EmbeddingsClient(api_key="sk-key")
        self.assertTrue(client.has_api_key)

    def test_has_api_key_false_when_empty_string(self) -> None:
        client = EmbeddingsClient(api_key="")
        self.assertFalse(client.has_api_key)


class EmbeddingsClientNoApiKeyTests(unittest.TestCase):
    def test_embed_raises_without_api_key(self) -> None:
        client = EmbeddingsClient(api_key="")
        with self.assertRaises(RuntimeError) as ctx:
            client.embed("hello")
        self.assertIn("not configured", str(ctx.exception))

    def test_embed_batch_raises_without_api_key(self) -> None:
        """embed_batch calls embed internally, so it should also raise."""
        client = EmbeddingsClient(api_key="")
        with self.assertRaises(RuntimeError):
            client.embed_batch(["hello"])


class EmbeddingsClientCustomConfigTests(unittest.TestCase):
    def test_custom_base_url_used_in_request(self) -> None:
        client = EmbeddingsClient(
            api_key="key",
            base_url="https://custom.example.com/v1",
        )
        with patch(
            "gracekelly.core.embeddings.request.urlopen",
            return_value=_mock_response([0.5]),
        ) as mock_urlopen:
            client.embed("test")
        req = mock_urlopen.call_args.args[0]
        self.assertIn("custom.example.com", req.full_url)

    def test_trailing_slash_stripped_from_base_url(self) -> None:
        client = EmbeddingsClient(
            api_key="key",
            base_url="https://api.example.com/v1/",
        )
        with patch(
            "gracekelly.core.embeddings.request.urlopen",
            return_value=_mock_response([0.1]),
        ) as mock_urlopen:
            client.embed("text")
        req = mock_urlopen.call_args.args[0]
        self.assertFalse(req.full_url.endswith("//embeddings"))

    def test_custom_model_sent_in_payload(self) -> None:
        client = EmbeddingsClient(api_key="key", model="custom-embed-v2")
        with patch(
            "gracekelly.core.embeddings.request.urlopen",
            return_value=_mock_response([0.1, 0.2]),
        ) as mock_urlopen:
            client.embed("hi")
        req = mock_urlopen.call_args.args[0]
        payload = json.loads(req.data.decode("utf-8"))
        self.assertEqual(payload["model"], "custom-embed-v2")


class EmbeddingsClientBatchEdgeCasesTests(unittest.TestCase):
    def test_empty_batch_returns_empty_list(self) -> None:
        client = EmbeddingsClient(api_key="key")
        with patch("gracekelly.core.embeddings.request.urlopen"):
            result = client.embed_batch([])
        self.assertEqual(result, [])

    def test_single_item_batch(self) -> None:
        client = EmbeddingsClient(api_key="key")
        with patch(
            "gracekelly.core.embeddings.request.urlopen",
            return_value=_mock_response([0.1, 0.2]),
        ):
            result = client.embed_batch(["hello"])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], [0.1, 0.2])


if __name__ == "__main__":
    unittest.main()
