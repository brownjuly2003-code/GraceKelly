from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from gracekelly.adapters.api.anthropic import AnthropicApiAdapter
from gracekelly.adapters.api.mistral import MistralApiAdapter
from gracekelly.adapters.api.openai_compat import OpenAICompatibleApiAdapter
from gracekelly.core.contracts import StepStatus


def _mock_response(content: dict) -> MagicMock:
    mock = MagicMock()
    mock.read.return_value = json.dumps(content).encode("utf-8")
    mock.__enter__ = lambda s: s
    mock.__exit__ = MagicMock(return_value=False)
    return mock


def _make_request(model_id: str = "m1") -> MagicMock:
    req = MagicMock()
    req.task_id = "t1"
    req.prompt = "test"
    req.reasoning = False
    req.step.model.id = model_id
    req.step.model.display_name = "M1"
    req.step.model.timeout_seconds = 10
    req.step.provider_model_id = model_id
    return req


_ANTHROPIC_OK = {"content": [{"type": "text", "text": "hello"}]}
_OPENAI_OK = {"choices": [{"message": {"content": "hello"}}]}


class AnthropicAdapterNameTests(unittest.TestCase):
    def test_adapter_name(self) -> None:
        adapter = AnthropicApiAdapter(api_key="key")
        self.assertEqual(adapter.name, "api.anthropic")

    def test_default_base_url(self) -> None:
        adapter = AnthropicApiAdapter(api_key="key")
        self.assertIn("anthropic.com", adapter._base_url)

    def test_anthropic_version_stored(self) -> None:
        adapter = AnthropicApiAdapter(api_key="key", anthropic_version="2024-01-01")
        self.assertEqual(adapter._anthropic_version, "2024-01-01")

    def test_default_anthropic_version(self) -> None:
        adapter = AnthropicApiAdapter(api_key="key")
        self.assertTrue(adapter._anthropic_version.startswith("20"))


class AnthropicPostJsonHeadersTests(unittest.TestCase):
    """Verify that _post_json uses x-api-key (not Authorization: Bearer)."""

    def test_uses_x_api_key_header(self) -> None:
        adapter = AnthropicApiAdapter(api_key="sk-ant-test")
        with patch(
            "gracekelly.adapters.api.anthropic.urllib_request.urlopen",
            return_value=_mock_response(_ANTHROPIC_OK),
        ) as mock_urlopen:
            adapter._post_json("/messages", {}, timeout_seconds=5.0)
        req = mock_urlopen.call_args.args[0]
        # urllib capitalises header names: "x-api-key" → "X-api-key"
        self.assertIn("X-api-key", req.headers)

    def test_x_api_key_value_is_api_key(self) -> None:
        adapter = AnthropicApiAdapter(api_key="sk-ant-test")
        with patch(
            "gracekelly.adapters.api.anthropic.urllib_request.urlopen",
            return_value=_mock_response(_ANTHROPIC_OK),
        ) as mock_urlopen:
            adapter._post_json("/messages", {}, timeout_seconds=5.0)
        req = mock_urlopen.call_args.args[0]
        self.assertEqual(req.headers.get("X-api-key"), "sk-ant-test")

    def test_anthropic_version_header_present(self) -> None:
        adapter = AnthropicApiAdapter(api_key="key", anthropic_version="2024-02-01")
        with patch(
            "gracekelly.adapters.api.anthropic.urllib_request.urlopen",
            return_value=_mock_response(_ANTHROPIC_OK),
        ) as mock_urlopen:
            adapter._post_json("/messages", {}, timeout_seconds=5.0)
        req = mock_urlopen.call_args.args[0]
        self.assertEqual(req.headers.get("Anthropic-version"), "2024-02-01")

    def test_no_authorization_bearer_header(self) -> None:
        """Anthropic adapter must NOT send Authorization: Bearer."""
        adapter = AnthropicApiAdapter(api_key="key")
        with patch(
            "gracekelly.adapters.api.anthropic.urllib_request.urlopen",
            return_value=_mock_response(_ANTHROPIC_OK),
        ) as mock_urlopen:
            adapter._post_json("/messages", {}, timeout_seconds=5.0)
        req = mock_urlopen.call_args.args[0]
        auth = req.headers.get("Authorization") or req.headers.get("authorization") or ""
        self.assertNotIn("Bearer", auth)


class AnthropicExecuteTests(unittest.TestCase):
    def test_success_returns_completed(self) -> None:
        adapter = AnthropicApiAdapter(api_key="key")
        with patch(
            "gracekelly.adapters.api.anthropic.urllib_request.urlopen",
            return_value=_mock_response(_ANTHROPIC_OK),
        ):
            result = adapter.execute(_make_request())
        self.assertEqual(result.status, StepStatus.COMPLETED)
        self.assertEqual(result.output_text, "hello")


class MistralAdapterTests(unittest.TestCase):
    def test_adapter_name(self) -> None:
        adapter = MistralApiAdapter(api_key="key", base_url="https://api.mistral.ai")
        self.assertEqual(adapter.name, "api.mistral")

    def test_provider_label_in_healthcheck(self) -> None:
        adapter = MistralApiAdapter(api_key="key", base_url="https://api.mistral.ai")
        hc = adapter.healthcheck()
        self.assertEqual(hc["provider"], "mistral")

    def test_default_timeout(self) -> None:
        adapter = MistralApiAdapter(api_key="key", base_url="https://api.mistral.ai")
        self.assertEqual(adapter._default_timeout_seconds, 30.0)

    def test_success_execute(self) -> None:
        adapter = MistralApiAdapter(api_key="key", base_url="https://api.mistral.ai")
        with patch.object(adapter, "_post_json", return_value=_OPENAI_OK):
            result = adapter.execute(_make_request())
        self.assertEqual(result.status, StepStatus.COMPLETED)


class OpenAICompatAdapterTests(unittest.TestCase):
    def test_adapter_name(self) -> None:
        adapter = OpenAICompatibleApiAdapter(api_key="key", base_url="https://api.openai.com")
        self.assertEqual(adapter.name, "api.openai")

    def test_provider_label_in_healthcheck(self) -> None:
        adapter = OpenAICompatibleApiAdapter(api_key="key", base_url="https://api.openai.com")
        hc = adapter.healthcheck()
        self.assertEqual(hc["provider"], "openai-compatible")

    def test_default_timeout(self) -> None:
        adapter = OpenAICompatibleApiAdapter(api_key="key", base_url="https://api.openai.com")
        self.assertEqual(adapter._default_timeout_seconds, 60.0)

    def test_success_execute(self) -> None:
        adapter = OpenAICompatibleApiAdapter(api_key="key", base_url="https://api.openai.com")
        with patch.object(adapter, "_post_json", return_value=_OPENAI_OK):
            result = adapter.execute(_make_request())
        self.assertEqual(result.status, StepStatus.COMPLETED)


if __name__ == "__main__":
    unittest.main()
