from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from gracekelly.adapters.api.anthropic import AnthropicApiAdapter
from gracekelly.adapters.api.base import BaseApiAdapter
from gracekelly.adapters.api.openai_compat import OpenAICompatibleApiAdapter


def _base(*, api_key: str | None = "key", max_retries: int = 0) -> BaseApiAdapter:
    return BaseApiAdapter(
        api_key=api_key,
        base_url="https://example.com",
        timeout_seconds=30.0,
        provider_label="Test",
        max_retries=max_retries,
    )


def _openai(*, api_key: str | None = "key") -> OpenAICompatibleApiAdapter:
    return OpenAICompatibleApiAdapter(
        api_key=api_key,
        base_url="https://api.openai.com",
    )


def _anthropic(*, api_key: str | None = "key") -> AnthropicApiAdapter:
    return AnthropicApiAdapter(api_key=api_key)


class BaseApiAdapterInitTests(unittest.TestCase):
    def test_has_api_key_true_when_set(self) -> None:
        self.assertTrue(_base(api_key="secret").has_api_key)

    def test_has_api_key_false_when_none(self) -> None:
        self.assertFalse(_base(api_key=None).has_api_key)

    def test_has_api_key_false_when_empty_string(self) -> None:
        self.assertFalse(_base(api_key="").has_api_key)

    def test_max_retries_clamped_to_zero_for_negative(self) -> None:
        adapter = BaseApiAdapter(
            api_key="k",
            base_url="https://x.com",
            timeout_seconds=10.0,
            provider_label="X",
            max_retries=-5,
        )
        self.assertEqual(adapter._max_retries, 0)

    def test_base_url_trailing_slash_stripped(self) -> None:
        adapter = BaseApiAdapter(
            api_key="k",
            base_url="https://api.com/",
            timeout_seconds=10.0,
            provider_label="X",
        )
        self.assertEqual(adapter._base_url, "https://api.com")

    def test_provider_label_stored(self) -> None:
        adapter = _base()
        self.assertEqual(adapter._provider_label, "Test")


class BaseApiAdapterExtractOutputTextTests(unittest.TestCase):
    def test_missing_choices_raises(self) -> None:
        with self.assertRaises(ValueError):
            _base()._extract_output_text({})

    def test_empty_choices_list_raises(self) -> None:
        with self.assertRaises(ValueError):
            _base()._extract_output_text({"choices": []})

    def test_non_list_choices_raises(self) -> None:
        with self.assertRaises(ValueError):
            _base()._extract_output_text({"choices": "bad"})

    def test_non_dict_first_choice_raises(self) -> None:
        with self.assertRaises(ValueError):
            _base()._extract_output_text({"choices": ["not-a-dict"]})

    def test_missing_message_in_choice_raises(self) -> None:
        with self.assertRaises(ValueError):
            _base()._extract_output_text({"choices": [{"no_message": True}]})

    def test_non_dict_message_raises(self) -> None:
        with self.assertRaises(ValueError):
            _base()._extract_output_text({"choices": [{"message": "string"}]})

    def test_valid_string_content_stripped_and_returned(self) -> None:
        payload = {"choices": [{"message": {"content": "  hello  "}}]}
        self.assertEqual(_base()._extract_output_text(payload), "hello")

    def test_whitespace_only_content_raises(self) -> None:
        payload = {"choices": [{"message": {"content": "   "}}]}
        with self.assertRaises(ValueError):
            _base()._extract_output_text(payload)

    def test_none_content_raises(self) -> None:
        payload = {"choices": [{"message": {"content": None}}]}
        with self.assertRaises(ValueError):
            _base()._extract_output_text(payload)


class BaseApiAdapterHealthcheckTests(unittest.TestCase):
    def test_no_api_key_returns_degraded_status(self) -> None:
        result = _base(api_key=None).healthcheck()
        self.assertEqual(result["status"], "degraded")
        self.assertFalse(result["configured"])

    def test_with_api_key_returns_ok_status(self) -> None:
        result = _base(api_key="secret").healthcheck()
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["configured"])

    def test_ok_healthcheck_includes_base_url(self) -> None:
        result = _base(api_key="k").healthcheck()
        self.assertIn("base_url", result)

    def test_ok_healthcheck_includes_max_retries(self) -> None:
        result = _base(api_key="k", max_retries=3).healthcheck()
        self.assertEqual(result["max_retries"], 3)

    def test_degraded_healthcheck_has_adapter_name(self) -> None:
        result = _base(api_key=None).healthcheck()
        self.assertIn("adapter_name", result)


class BaseApiAdapterResolveTimeoutTests(unittest.TestCase):
    def test_positive_model_timeout_overrides_default(self) -> None:
        req = MagicMock()
        req.step.model.timeout_seconds = 999
        self.assertEqual(_base()._resolve_timeout_seconds(req), 999.0)

    def test_zero_model_timeout_falls_back_to_default(self) -> None:
        req = MagicMock()
        req.step.model.timeout_seconds = 0
        self.assertEqual(_base()._resolve_timeout_seconds(req), 30.0)

    def test_none_model_timeout_falls_back_to_default(self) -> None:
        req = MagicMock()
        req.step.model.timeout_seconds = None
        self.assertEqual(_base()._resolve_timeout_seconds(req), 30.0)

    def test_negative_model_timeout_falls_back_to_default(self) -> None:
        req = MagicMock()
        req.step.model.timeout_seconds = -10
        self.assertEqual(_base()._resolve_timeout_seconds(req), 30.0)


class OpenAICompatExtractOutputTextTests(unittest.TestCase):
    def test_string_content_returned_stripped(self) -> None:
        payload = {"choices": [{"message": {"content": "  answer  "}}]}
        self.assertEqual(_openai()._extract_output_text(payload), "answer")

    def test_list_content_text_blocks_joined_with_newline(self) -> None:
        payload = {"choices": [{"message": {"content": [
            {"type": "text", "text": "part one"},
            {"type": "text", "text": "part two"},
        ]}}]}
        self.assertEqual(_openai()._extract_output_text(payload), "part one\npart two")

    def test_list_content_non_text_blocks_ignored(self) -> None:
        payload = {"choices": [{"message": {"content": [
            {"type": "image", "url": "http://example.com/img.png"},
            {"type": "text", "text": "only text"},
        ]}}]}
        self.assertEqual(_openai()._extract_output_text(payload), "only text")

    def test_list_content_all_non_text_raises(self) -> None:
        payload = {"choices": [{"message": {"content": [
            {"type": "image", "url": "http://example.com/img.png"},
        ]}}]}
        with self.assertRaises(ValueError):
            _openai()._extract_output_text(payload)

    def test_empty_list_content_raises(self) -> None:
        payload = {"choices": [{"message": {"content": []}}]}
        with self.assertRaises(ValueError):
            _openai()._extract_output_text(payload)

    def test_missing_choices_raises(self) -> None:
        with self.assertRaises(ValueError):
            _openai()._extract_output_text({})

    def test_whitespace_only_text_block_skipped(self) -> None:
        payload = {"choices": [{"message": {"content": [
            {"type": "text", "text": "   "},
            {"type": "text", "text": "real content"},
        ]}}]}
        self.assertEqual(_openai()._extract_output_text(payload), "real content")

    def test_single_text_block_no_join(self) -> None:
        payload = {"choices": [{"message": {"content": [
            {"type": "text", "text": "only one"},
        ]}}]}
        self.assertEqual(_openai()._extract_output_text(payload), "only one")


class AnthropicExtractOutputTextTests(unittest.TestCase):
    def test_single_text_block_returned_stripped(self) -> None:
        payload = {"content": [{"type": "text", "text": "  Hello  "}]}
        self.assertEqual(_anthropic()._extract_output_text(payload), "Hello")

    def test_multiple_text_blocks_joined(self) -> None:
        payload = {"content": [
            {"type": "text", "text": "First"},
            {"type": "text", "text": "Second"},
        ]}
        self.assertEqual(_anthropic()._extract_output_text(payload), "First\nSecond")

    def test_non_text_blocks_ignored(self) -> None:
        payload = {"content": [
            {"type": "tool_use", "id": "toolu_abc"},
            {"type": "text", "text": "answer"},
        ]}
        self.assertEqual(_anthropic()._extract_output_text(payload), "answer")

    def test_missing_content_key_raises(self) -> None:
        with self.assertRaises(ValueError):
            _anthropic()._extract_output_text({})

    def test_non_list_content_raises(self) -> None:
        with self.assertRaises(ValueError):
            _anthropic()._extract_output_text({"content": "raw string"})

    def test_empty_content_list_raises(self) -> None:
        with self.assertRaises(ValueError):
            _anthropic()._extract_output_text({"content": []})

    def test_whitespace_only_text_block_skipped(self) -> None:
        payload = {"content": [
            {"type": "text", "text": "   "},
            {"type": "text", "text": "real"},
        ]}
        self.assertEqual(_anthropic()._extract_output_text(payload), "real")

    def test_all_whitespace_blocks_raises(self) -> None:
        payload = {"content": [{"type": "text", "text": "   "}]}
        with self.assertRaises(ValueError):
            _anthropic()._extract_output_text(payload)

    def test_default_anthropic_version(self) -> None:
        adapter = AnthropicApiAdapter(api_key="k")
        self.assertEqual(adapter._anthropic_version, "2023-06-01")

    def test_custom_anthropic_version_stored(self) -> None:
        adapter = AnthropicApiAdapter(api_key="k", anthropic_version="2024-01-01")
        self.assertEqual(adapter._anthropic_version, "2024-01-01")


if __name__ == "__main__":
    unittest.main()
