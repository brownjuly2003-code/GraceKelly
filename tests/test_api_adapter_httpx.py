"""Tests for httpx integration in BaseApiAdapter."""
from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock, patch

import httpx

from gracekelly.adapters.api.base import BaseApiAdapter
from gracekelly.core.contracts import FailureCode, StepStatus


def _adapter(*, max_retries: int = 0) -> BaseApiAdapter:
    return BaseApiAdapter(
        api_key="test-key",
        base_url="https://api.example.com",
        timeout_seconds=30.0,
        provider_label="TestProvider",
        max_retries=max_retries,
        retry_backoff_seconds=0.0,
    )


def _make_request(*, model_timeout: int = 10) -> MagicMock:
    req = MagicMock()
    req.task_id = "t1"
    req.prompt = "Hello"
    req.reasoning = False
    req.step.model.id = "m1"
    req.step.model.display_name = "M1"
    req.step.model.timeout_seconds = model_timeout
    req.step.provider_model_id = "m1"
    return req


def _mock_httpx_response(data: dict[str, Any]) -> MagicMock:
    mock = MagicMock(spec=httpx.Response)
    mock.status_code = 200
    mock.json.return_value = data
    mock.raise_for_status.return_value = None
    return mock


def _make_http_status_error(code: int) -> httpx.HTTPStatusError:
    response = MagicMock(spec=httpx.Response)
    response.status_code = code
    response.text = f"HTTP {code} error body"
    return httpx.HTTPStatusError(
        message=f"HTTP {code}",
        request=MagicMock(spec=httpx.Request),
        response=response,
    )


_GOOD_RESPONSE = {"choices": [{"message": {"content": "ok"}}]}


class HttpxClientCreatedOnInitTests(unittest.TestCase):
    def test_http_client_is_httpx_client(self) -> None:
        adapter = _adapter()
        self.assertIsInstance(adapter._http_client, httpx.Client)

    def test_http_client_follows_redirects(self) -> None:
        adapter = _adapter()
        self.assertTrue(adapter._http_client.follow_redirects)

    def test_close_closes_http_client(self) -> None:
        adapter = _adapter()
        with patch.object(adapter._http_client, "close") as mock_close:
            adapter.close()
        mock_close.assert_called_once()


class HttpxStatusError429Tests(unittest.TestCase):
    def test_429_returns_rate_limited(self) -> None:
        with patch("httpx.Client.post", side_effect=_make_http_status_error(429)):
            result = _adapter().execute(_make_request())
        self.assertEqual(result.status, StepStatus.FAILED)
        self.assertEqual(result.failure_code, FailureCode.RATE_LIMITED)

    def test_429_message_contains_provider_label(self) -> None:
        with patch("httpx.Client.post", side_effect=_make_http_status_error(429)):
            result = _adapter().execute(_make_request())
        assert result.failure_message is not None
        self.assertIn("TestProvider", result.failure_message)


class HttpxTimeoutExceptionTests(unittest.TestCase):
    def test_timeout_returns_timeout_failure(self) -> None:
        with patch("httpx.Client.post", side_effect=httpx.TimeoutException("timed out")):
            result = _adapter().execute(_make_request())
        self.assertEqual(result.status, StepStatus.FAILED)
        self.assertEqual(result.failure_code, FailureCode.TIMEOUT)

    def test_read_timeout_returns_timeout_failure(self) -> None:
        with patch("httpx.Client.post", side_effect=httpx.ReadTimeout("read timed out")):
            result = _adapter().execute(_make_request())
        self.assertEqual(result.failure_code, FailureCode.TIMEOUT)

    def test_connect_timeout_returns_timeout_failure(self) -> None:
        with patch("httpx.Client.post", side_effect=httpx.ConnectTimeout("connect timed out")):
            result = _adapter().execute(_make_request())
        self.assertEqual(result.failure_code, FailureCode.TIMEOUT)


class HttpxRequestErrorTests(unittest.TestCase):
    def test_connect_error_returns_network_error(self) -> None:
        with patch("httpx.Client.post", side_effect=httpx.ConnectError("refused")):
            result = _adapter().execute(_make_request())
        self.assertEqual(result.status, StepStatus.FAILED)
        self.assertEqual(result.failure_code, FailureCode.PROVIDER_UNAVAILABLE)

    def test_network_error_message_contains_provider(self) -> None:
        with patch("httpx.Client.post", side_effect=httpx.ConnectError("refused")):
            result = _adapter().execute(_make_request())
        assert result.failure_message is not None
        self.assertIn("TestProvider", result.failure_message)

    def test_remote_protocol_error_returns_network_error(self) -> None:
        with patch("httpx.Client.post", side_effect=httpx.RemoteProtocolError("bad proto")):
            result = _adapter().execute(_make_request())
        self.assertEqual(result.failure_code, FailureCode.PROVIDER_UNAVAILABLE)


class HttpxStatus500Tests(unittest.TestCase):
    def test_500_returns_provider_error(self) -> None:
        with patch("httpx.Client.post", side_effect=_make_http_status_error(500)):
            result = _adapter().execute(_make_request())
        self.assertEqual(result.status, StepStatus.FAILED)
        self.assertEqual(result.failure_code, FailureCode.PROVIDER_UNAVAILABLE)

    def test_500_message_contains_status_code(self) -> None:
        with patch("httpx.Client.post", side_effect=_make_http_status_error(500)):
            result = _adapter().execute(_make_request())
        assert result.failure_message is not None
        self.assertIn("500", result.failure_message)

    def test_502_returns_provider_error(self) -> None:
        with patch("httpx.Client.post", side_effect=_make_http_status_error(502)):
            result = _adapter().execute(_make_request())
        self.assertEqual(result.failure_code, FailureCode.PROVIDER_UNAVAILABLE)

    def test_504_returns_provider_error(self) -> None:
        with patch("httpx.Client.post", side_effect=_make_http_status_error(504)):
            result = _adapter().execute(_make_request())
        self.assertEqual(result.failure_code, FailureCode.PROVIDER_UNAVAILABLE)


class HttpxRetriesOn503Tests(unittest.TestCase):
    @patch("httpx.Client.post")
    def test_retries_on_503_then_succeeds(self, mock_post: MagicMock) -> None:
        mock_post.side_effect = [
            _make_http_status_error(503),
            _mock_httpx_response(_GOOD_RESPONSE),
        ]
        result = _adapter(max_retries=1).execute(_make_request())
        self.assertEqual(result.status, StepStatus.COMPLETED)
        self.assertEqual(mock_post.call_count, 2)

    @patch("httpx.Client.post")
    def test_exhausted_503_retries_returns_provider_error(self, mock_post: MagicMock) -> None:
        mock_post.side_effect = _make_http_status_error(503)
        result = _adapter(max_retries=2).execute(_make_request())
        self.assertEqual(result.failure_code, FailureCode.PROVIDER_UNAVAILABLE)
        self.assertEqual(mock_post.call_count, 3)

    @patch("httpx.Client.post")
    def test_retries_on_timeout_then_succeeds(self, mock_post: MagicMock) -> None:
        mock_post.side_effect = [
            httpx.TimeoutException("timed out"),
            _mock_httpx_response(_GOOD_RESPONSE),
        ]
        result = _adapter(max_retries=1).execute(_make_request())
        self.assertEqual(result.status, StepStatus.COMPLETED)

    @patch("httpx.Client.post")
    def test_retries_on_connect_error_then_succeeds(self, mock_post: MagicMock) -> None:
        mock_post.side_effect = [
            httpx.ConnectError("refused"),
            _mock_httpx_response(_GOOD_RESPONSE),
        ]
        result = _adapter(max_retries=1).execute(_make_request())
        self.assertEqual(result.status, StepStatus.COMPLETED)


class HttpxPostJsonCallTests(unittest.TestCase):
    @patch("httpx.Client.post")
    def test_post_called_with_correct_url(self, mock_post: MagicMock) -> None:
        mock_post.return_value = _mock_httpx_response(_GOOD_RESPONSE)
        _adapter().execute(_make_request())
        url = mock_post.call_args.args[0]
        self.assertEqual(url, "https://api.example.com/chat/completions")

    @patch("httpx.Client.post")
    def test_post_called_with_json_payload(self, mock_post: MagicMock) -> None:
        mock_post.return_value = _mock_httpx_response(_GOOD_RESPONSE)
        _adapter().execute(_make_request())
        call_kwargs = mock_post.call_args.kwargs
        self.assertIn("json", call_kwargs)
        self.assertEqual(call_kwargs["json"]["messages"][0]["content"], "Hello")

    @patch("httpx.Client.post")
    def test_post_called_with_bearer_auth_header(self, mock_post: MagicMock) -> None:
        mock_post.return_value = _mock_httpx_response(_GOOD_RESPONSE)
        _adapter().execute(_make_request())
        call_kwargs = mock_post.call_args.kwargs
        headers = call_kwargs.get("headers", {})
        self.assertEqual(headers.get("Authorization"), "Bearer test-key")

    @patch("httpx.Client.post")
    def test_post_called_with_model_timeout(self, mock_post: MagicMock) -> None:
        mock_post.return_value = _mock_httpx_response(_GOOD_RESPONSE)
        _adapter().execute(_make_request(model_timeout=7))
        call_kwargs = mock_post.call_args.kwargs
        self.assertEqual(call_kwargs.get("timeout"), 7.0)


if __name__ == "__main__":
    unittest.main()
