from __future__ import annotations

import json
import unittest
from typing import Any
from unittest.mock import MagicMock, patch

import httpx

from gracekelly.adapters.api.anthropic import AnthropicApiAdapter
from gracekelly.adapters.api.openai_compat import OpenAICompatibleApiAdapter
from gracekelly.core.contracts import (
    AdapterHint,
    ExecutionBackend,
    ExecutionPlan,
    ExecutionRequest,
    ExecutionStep,
    FailureCode,
    MergeStrategy,
    StepStatus,
)
from gracekelly.core.models import MODEL_SPECS, ModelSpec


def _openai_spec() -> ModelSpec:
    return next(s for s in MODEL_SPECS if s.id == "gpt-5-4-api")


def _anthropic_spec() -> ModelSpec:
    return next(s for s in MODEL_SPECS if s.id == "claude-sonnet-4-6-api")


def _execution_request(model_spec: ModelSpec) -> ExecutionRequest:
    step = ExecutionStep(
        model=model_spec,
        backend=ExecutionBackend.API,
        provider=model_spec.provider,
        provider_model_id=model_spec.provider_model_id,
        step_index=1,
    )
    plan = ExecutionPlan(
        steps=(step,),
        quorum=1,
        merge_strategy=MergeStrategy.FIRST_SUCCESS,
        dry_run=False,
        adapter_hint=AdapterHint.AUTO,
        cancel_on_quorum=True,
    )
    return ExecutionRequest(task_id="t1", prompt="Hello", plan=plan, step=step, reasoning=False)


def _make_http_status_error(code: int) -> httpx.HTTPStatusError:
    response = MagicMock(spec=httpx.Response)
    response.status_code = code
    response.text = f"HTTP {code}"
    return httpx.HTTPStatusError(
        message=f"HTTP {code}",
        request=MagicMock(spec=httpx.Request),
        response=response,
    )


def _api_response(content: str = "OK") -> dict[str, Any]:
    return {"choices": [{"message": {"content": content}}]}


def _mock_httpx_response(data: dict[str, Any]) -> MagicMock:
    mock = MagicMock(spec=httpx.Response)
    mock.status_code = 200
    mock.json.return_value = data
    mock.raise_for_status.return_value = None
    return mock


# urllib mock for Anthropic adapter (still uses urllib internally)
def _mock_urllib_response(data: dict[str, Any]) -> MagicMock:
    body = json.dumps(data).encode("utf-8")
    mock = MagicMock()
    mock.__enter__ = lambda s: s
    mock.__exit__ = MagicMock(return_value=False)
    mock.read.return_value = body
    return mock


class OpenAIErrorPathTests(unittest.TestCase):
    def _adapter(self, api_key: str | None = "test-key") -> OpenAICompatibleApiAdapter:
        return OpenAICompatibleApiAdapter(api_key=api_key, base_url="https://api.openai.com/v1")

    @patch("httpx.Client.post")
    def test_timeout(self, mock_post: MagicMock) -> None:
        mock_post.side_effect = httpx.TimeoutException("timed out")
        result = self._adapter().execute(_execution_request(_openai_spec()))
        self.assertEqual(result.failure_code, FailureCode.TIMEOUT)

    @patch("httpx.Client.post")
    def test_rate_limit_429(self, mock_post: MagicMock) -> None:
        mock_post.side_effect = _make_http_status_error(429)
        result = self._adapter().execute(_execution_request(_openai_spec()))
        self.assertEqual(result.failure_code, FailureCode.RATE_LIMITED)

    @patch("httpx.Client.post")
    def test_list_content_extracted(self, mock_post: MagicMock) -> None:
        payload = {
            "choices": [{
                "message": {
                    "content": [
                        {"type": "text", "text": "Part 1"},
                        {"type": "text", "text": "Part 2"},
                    ]
                }
            }]
        }
        mock_post.return_value = _mock_httpx_response(payload)
        result = self._adapter().execute(_execution_request(_openai_spec()))
        self.assertEqual(result.status, StepStatus.COMPLETED)
        self.assertEqual(result.output_text, "Part 1\nPart 2")

    @patch("httpx.Client.post")
    def test_list_content_empty_parts(self, mock_post: MagicMock) -> None:
        payload = {
            "choices": [{
                "message": {
                    "content": [{"type": "image", "url": "http://example.com"}]
                }
            }]
        }
        mock_post.return_value = _mock_httpx_response(payload)
        result = self._adapter().execute(_execution_request(_openai_spec()))
        self.assertEqual(result.failure_code, FailureCode.UNKNOWN_ERROR)

    @patch("httpx.Client.post")
    def test_non_json_response(self, mock_post: MagicMock) -> None:
        mock_post.side_effect = Exception("Unexpected error")
        result = self._adapter().execute(_execution_request(_openai_spec()))
        self.assertEqual(result.failure_code, FailureCode.UNKNOWN_ERROR)

    def test_missing_api_key(self) -> None:
        result = self._adapter(api_key=None).execute(_execution_request(_openai_spec()))
        self.assertEqual(result.failure_code, FailureCode.PROVIDER_UNAVAILABLE)


class AnthropicErrorPathTests(unittest.TestCase):
    def _adapter(self, api_key: str | None = "test-key") -> AnthropicApiAdapter:
        return AnthropicApiAdapter(api_key=api_key, base_url="https://api.anthropic.com")

    def test_missing_api_key(self) -> None:
        result = self._adapter(api_key=None).execute(_execution_request(_anthropic_spec()))
        self.assertEqual(result.failure_code, FailureCode.PROVIDER_UNAVAILABLE)

    @patch("gracekelly.adapters.api.anthropic.urllib_request.urlopen")
    def test_timeout(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.side_effect = TimeoutError()
        result = self._adapter().execute(_execution_request(_anthropic_spec()))
        self.assertEqual(result.failure_code, FailureCode.TIMEOUT)

    @patch("gracekelly.adapters.api.anthropic.urllib_request.urlopen")
    def test_success_with_text_content(self, mock_urlopen: MagicMock) -> None:
        payload = {"content": [{"type": "text", "text": "Hello from Claude"}]}
        mock_urlopen.return_value = _mock_urllib_response(payload)
        result = self._adapter().execute(_execution_request(_anthropic_spec()))
        self.assertEqual(result.status, StepStatus.COMPLETED)
        self.assertEqual(result.output_text, "Hello from Claude")

    @patch("gracekelly.adapters.api.anthropic.urllib_request.urlopen")
    def test_multi_block_content(self, mock_urlopen: MagicMock) -> None:
        payload = {
            "content": [
                {"type": "text", "text": "Part A"},
                {"type": "text", "text": "Part B"},
            ]
        }
        mock_urlopen.return_value = _mock_urllib_response(payload)
        result = self._adapter().execute(_execution_request(_anthropic_spec()))
        self.assertEqual(result.output_text, "Part A\nPart B")

    @patch("gracekelly.adapters.api.anthropic.urllib_request.urlopen")
    def test_empty_content_fails(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _mock_urllib_response({"content": []})
        result = self._adapter().execute(_execution_request(_anthropic_spec()))
        self.assertEqual(result.failure_code, FailureCode.UNKNOWN_ERROR)

    @patch("gracekelly.adapters.api.anthropic.urllib_request.urlopen")
    def test_rate_limit_429(self, mock_urlopen: MagicMock) -> None:
        from io import BytesIO
        from urllib import error as urllib_error
        exc = urllib_error.HTTPError(
            url="https://api.anthropic.com/v1/messages",
            code=429,
            msg="Too Many Requests",
            hdrs={},  # type: ignore[arg-type]
            fp=BytesIO(b"{}"),
        )
        mock_urlopen.side_effect = exc
        result = self._adapter().execute(_execution_request(_anthropic_spec()))
        self.assertEqual(result.failure_code, FailureCode.RATE_LIMITED)

    def test_healthcheck_configured(self) -> None:
        health = self._adapter().healthcheck()
        self.assertEqual(health["status"], "ok")
        self.assertTrue(health["configured"])

    def test_healthcheck_unconfigured(self) -> None:
        health = self._adapter(api_key=None).healthcheck()
        self.assertEqual(health["status"], "degraded")
        self.assertFalse(health["configured"])

    @patch("gracekelly.adapters.api.anthropic.urllib_request.urlopen")
    def test_uses_x_api_key_header(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _mock_urllib_response({"content": [{"type": "text", "text": "ok"}]})
        self._adapter().execute(_execution_request(_anthropic_spec()))
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        self.assertEqual(req.get_header("X-api-key"), "test-key")
        self.assertIn("anthropic-version", {k.lower(): v for k, v in req.header_items()})
