from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock, patch

import httpx

from gracekelly.adapters.api.base import BaseApiAdapter
from gracekelly.core.contracts import StepStatus


def _adapter(
    *,
    api_key: str | None = "test-key",
    timeout_seconds: float = 30.0,
    max_retries: int = 0,
) -> BaseApiAdapter:
    return BaseApiAdapter(
        api_key=api_key,
        base_url="https://api.example.com",
        timeout_seconds=timeout_seconds,
        provider_label="TestProvider",
        max_retries=max_retries,
        retry_backoff_seconds=0.0,
    )


def _make_request(*, model_timeout: int | None = 10) -> MagicMock:
    req = MagicMock()
    req.task_id = "t1"
    req.prompt = "Hello"
    req.reasoning = False
    req.step.model.id = "m1"
    req.step.model.display_name = "M1"
    req.step.model.timeout_seconds = model_timeout
    req.step.provider_model_id = "m1"
    return req


def _mock_httpx_response(content: dict[str, Any]) -> MagicMock:
    mock = MagicMock(spec=httpx.Response)
    mock.status_code = 200
    mock.json.return_value = content
    mock.raise_for_status.return_value = None
    return mock


class ResolveTimeoutSecondsTests(unittest.TestCase):
    """_resolve_timeout_seconds branches: model timeout > 0, == 0, None, negative."""

    def _resolver(self, model_timeout: int | None, default: float = 30.0) -> float:
        adapter = _adapter(timeout_seconds=default)
        req = _make_request(model_timeout=model_timeout)
        return adapter._resolve_timeout_seconds(req)

    def test_positive_model_timeout_used(self) -> None:
        result = self._resolver(model_timeout=45)
        self.assertEqual(result, 45.0)

    def test_zero_model_timeout_falls_back_to_default(self) -> None:
        result = self._resolver(model_timeout=0, default=30.0)
        self.assertEqual(result, 30.0)

    def test_none_model_timeout_falls_back_to_default(self) -> None:
        result = self._resolver(model_timeout=None, default=20.0)
        self.assertEqual(result, 20.0)

    def test_negative_model_timeout_falls_back_to_default(self) -> None:
        result = self._resolver(model_timeout=-5, default=15.0)
        self.assertEqual(result, 15.0)


class ExtractOutputTextBranchTests(unittest.TestCase):
    """_extract_output_text branches for malformed response payloads."""

    def _extract(self, payload: dict[str, Any]) -> str:
        return _adapter()._extract_output_text(payload)

    def test_choices_is_none_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            self._extract({"choices": None})

    def test_choices_is_string_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            self._extract({"choices": "oops"})

    def test_choices_is_integer_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            self._extract({"choices": 42})

    def test_choices_missing_key_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            self._extract({})

    def test_first_choice_not_dict_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            self._extract({"choices": ["not-a-dict"]})

    def test_first_choice_message_missing_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            self._extract({"choices": [{"index": 0}]})

    def test_message_not_dict_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            self._extract({"choices": [{"message": "plain-string"}]})

    def test_content_is_none_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            self._extract({"choices": [{"message": {"content": None}}]})

    def test_content_is_int_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            self._extract({"choices": [{"message": {"content": 123}}]})

    def test_content_is_whitespace_only_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            self._extract({"choices": [{"message": {"content": "   "}}]})

    def test_valid_content_returns_stripped_string(self) -> None:
        result = self._extract({"choices": [{"message": {"content": "  Hello  "}}]})
        self.assertEqual(result, "Hello")


class HealthcheckDetailsTests(unittest.TestCase):
    """healthcheck() returns all expected keys when api_key is set."""

    def test_healthcheck_includes_base_url(self) -> None:
        adapter = BaseApiAdapter(
            api_key="k",
            base_url="https://api.test.com",
            timeout_seconds=10.0,
            provider_label="TestProv",
        )
        health = adapter.healthcheck()
        self.assertEqual(health["base_url"], "https://api.test.com")

    def test_healthcheck_includes_default_timeout(self) -> None:
        adapter = BaseApiAdapter(
            api_key="k",
            base_url="https://api.test.com",
            timeout_seconds=25.0,
            provider_label="TestProv",
        )
        health = adapter.healthcheck()
        self.assertEqual(health["default_timeout_seconds"], 25.0)

    def test_healthcheck_includes_max_retries(self) -> None:
        adapter = BaseApiAdapter(
            api_key="k",
            base_url="https://api.test.com",
            timeout_seconds=10.0,
            provider_label="TestProv",
            max_retries=3,
        )
        health = adapter.healthcheck()
        self.assertEqual(health["max_retries"], 3)

    def test_healthcheck_no_key_omits_base_url(self) -> None:
        adapter = BaseApiAdapter(
            api_key=None,
            base_url="https://api.test.com",
            timeout_seconds=10.0,
            provider_label="TestProv",
        )
        health = adapter.healthcheck()
        self.assertNotIn("base_url", health)

    def test_healthcheck_no_key_status_degraded(self) -> None:
        adapter = BaseApiAdapter(
            api_key=None,
            base_url="https://api.test.com",
            timeout_seconds=10.0,
            provider_label="TestProv",
        )
        health = adapter.healthcheck()
        self.assertEqual(health["status"], "degraded")

    def test_execute_uses_model_timeout_over_default(self) -> None:
        """When model specifies timeout=5, adapter passes timeout=5.0 to httpx."""
        adapter = _adapter(timeout_seconds=30.0)
        req = _make_request(model_timeout=5)
        good_response = {"choices": [{"message": {"content": "ok"}}]}
        with patch("httpx.Client.post", return_value=_mock_httpx_response(good_response)) as mock_post:
            result = adapter.execute(req)
        call_kwargs = mock_post.call_args.kwargs
        self.assertEqual(call_kwargs.get("timeout"), 5.0)
        self.assertEqual(result.status, StepStatus.COMPLETED)


if __name__ == "__main__":
    unittest.main()
