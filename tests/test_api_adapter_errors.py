from __future__ import annotations

import io
import json
import unittest
from http.client import HTTPResponse
from unittest.mock import MagicMock, patch
from urllib import error

from gracekelly.adapters.api.mistral import MistralApiAdapter
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
from gracekelly.core.models import MODEL_SPECS


def _mistral_spec():
    return next(s for s in MODEL_SPECS if s.id == "mistral-small")


def _openai_spec():
    return next(s for s in MODEL_SPECS if s.id == "gpt-5-4-api")


def _execution_request(model_spec) -> ExecutionRequest:
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


def _make_http_error(code: int) -> error.HTTPError:
    return error.HTTPError(
        url="https://api.test/v1/chat/completions",
        code=code,
        msg=f"HTTP {code}",
        hdrs={},  # type: ignore[arg-type]
        fp=io.BytesIO(b"{}"),
    )


def _api_response(content: str = "OK") -> dict:
    return {"choices": [{"message": {"content": content}}]}


class MistralErrorPathTests(unittest.TestCase):
    def _adapter(self, api_key: str | None = "test-key") -> MistralApiAdapter:
        return MistralApiAdapter(api_key=api_key, base_url="https://api.mistral.ai/v1")

    def test_missing_api_key(self) -> None:
        result = self._adapter(api_key=None).execute(_execution_request(_mistral_spec()))
        self.assertEqual(result.status, StepStatus.FAILED)
        self.assertEqual(result.failure_code, FailureCode.PROVIDER_UNAVAILABLE)
        self.assertIn("not configured", result.failure_message)

    @patch("gracekelly.adapters.api.base.request.urlopen")
    def test_timeout(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.side_effect = TimeoutError()
        result = self._adapter().execute(_execution_request(_mistral_spec()))
        self.assertEqual(result.failure_code, FailureCode.TIMEOUT)

    @patch("gracekelly.adapters.api.base.request.urlopen")
    def test_rate_limit_429(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.side_effect = _make_http_error(429)
        result = self._adapter().execute(_execution_request(_mistral_spec()))
        self.assertEqual(result.failure_code, FailureCode.RATE_LIMITED)

    @patch("gracekelly.adapters.api.base.request.urlopen")
    def test_server_error_500(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.side_effect = _make_http_error(500)
        result = self._adapter().execute(_execution_request(_mistral_spec()))
        self.assertEqual(result.failure_code, FailureCode.PROVIDER_UNAVAILABLE)
        self.assertIn("500", result.failure_message)

    @patch("gracekelly.adapters.api.base.request.urlopen")
    def test_network_error(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.side_effect = error.URLError("Connection refused")
        result = self._adapter().execute(_execution_request(_mistral_spec()))
        self.assertEqual(result.failure_code, FailureCode.PROVIDER_UNAVAILABLE)
        self.assertIn("network error", result.failure_message)

    @patch("gracekelly.adapters.api.base.request.urlopen")
    def test_empty_choices(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _mock_response({"choices": []})
        result = self._adapter().execute(_execution_request(_mistral_spec()))
        self.assertEqual(result.failure_code, FailureCode.UNKNOWN_ERROR)

    @patch("gracekelly.adapters.api.base.request.urlopen")
    def test_missing_message(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _mock_response({"choices": [{"index": 0}]})
        result = self._adapter().execute(_execution_request(_mistral_spec()))
        self.assertEqual(result.failure_code, FailureCode.UNKNOWN_ERROR)

    @patch("gracekelly.adapters.api.base.request.urlopen")
    def test_empty_content(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _mock_response({"choices": [{"message": {"content": ""}}]})
        result = self._adapter().execute(_execution_request(_mistral_spec()))
        self.assertEqual(result.failure_code, FailureCode.UNKNOWN_ERROR)

    @patch("gracekelly.adapters.api.base.request.urlopen")
    def test_success(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _mock_response(_api_response("Hello world"))
        result = self._adapter().execute(_execution_request(_mistral_spec()))
        self.assertEqual(result.status, StepStatus.COMPLETED)
        self.assertEqual(result.output_text, "Hello world")

    def test_healthcheck_configured(self) -> None:
        health = self._adapter().healthcheck()
        self.assertEqual(health["status"], "ok")
        self.assertTrue(health["configured"])

    def test_healthcheck_unconfigured(self) -> None:
        health = self._adapter(api_key=None).healthcheck()
        self.assertEqual(health["status"], "degraded")
        self.assertFalse(health["configured"])


class OpenAIErrorPathTests(unittest.TestCase):
    def _adapter(self, api_key: str | None = "test-key") -> OpenAICompatibleApiAdapter:
        return OpenAICompatibleApiAdapter(api_key=api_key, base_url="https://api.openai.com/v1")

    @patch("gracekelly.adapters.api.base.request.urlopen")
    def test_timeout(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.side_effect = TimeoutError()
        result = self._adapter().execute(_execution_request(_openai_spec()))
        self.assertEqual(result.failure_code, FailureCode.TIMEOUT)

    @patch("gracekelly.adapters.api.base.request.urlopen")
    def test_rate_limit_429(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.side_effect = _make_http_error(429)
        result = self._adapter().execute(_execution_request(_openai_spec()))
        self.assertEqual(result.failure_code, FailureCode.RATE_LIMITED)

    @patch("gracekelly.adapters.api.base.request.urlopen")
    def test_list_content_extracted(self, mock_urlopen: MagicMock) -> None:
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
        mock_urlopen.return_value = _mock_response(payload)
        result = self._adapter().execute(_execution_request(_openai_spec()))
        self.assertEqual(result.status, StepStatus.COMPLETED)
        self.assertEqual(result.output_text, "Part 1\nPart 2")

    @patch("gracekelly.adapters.api.base.request.urlopen")
    def test_list_content_empty_parts(self, mock_urlopen: MagicMock) -> None:
        payload = {
            "choices": [{
                "message": {
                    "content": [{"type": "image", "url": "http://example.com"}]
                }
            }]
        }
        mock_urlopen.return_value = _mock_response(payload)
        result = self._adapter().execute(_execution_request(_openai_spec()))
        self.assertEqual(result.failure_code, FailureCode.UNKNOWN_ERROR)

    @patch("gracekelly.adapters.api.base.request.urlopen")
    def test_non_json_response(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.side_effect = Exception("Unexpected error")
        result = self._adapter().execute(_execution_request(_openai_spec()))
        self.assertEqual(result.failure_code, FailureCode.UNKNOWN_ERROR)

    def test_missing_api_key(self) -> None:
        result = self._adapter(api_key=None).execute(_execution_request(_openai_spec()))
        self.assertEqual(result.failure_code, FailureCode.PROVIDER_UNAVAILABLE)


def _mock_response(data: dict) -> MagicMock:
    body = json.dumps(data).encode("utf-8")
    mock = MagicMock()
    mock.__enter__ = lambda s: s
    mock.__exit__ = MagicMock(return_value=False)
    mock.read.return_value = body
    return mock
