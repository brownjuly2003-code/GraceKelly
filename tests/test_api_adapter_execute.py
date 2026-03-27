from __future__ import annotations

import json
import unittest
from io import BytesIO
from unittest.mock import MagicMock, patch
from urllib import error

from gracekelly.adapters.api.base import BaseApiAdapter
from gracekelly.core.contracts import FailureCode, StepStatus


def _adapter(*, api_key: str | None = "test-key", max_retries: int = 0) -> BaseApiAdapter:
    return BaseApiAdapter(
        api_key=api_key,
        base_url="https://api.example.com",
        timeout_seconds=10.0,
        provider_label="TestProvider",
        max_retries=max_retries,
        retry_backoff_seconds=0.0,
    )


def _make_request(*, model_id: str = "m1", display_name: str = "M1") -> MagicMock:
    req = MagicMock()
    req.task_id = "t1"
    req.prompt = "Hello"
    req.reasoning = False
    req.step.model.id = model_id
    req.step.model.display_name = display_name
    req.step.model.timeout_seconds = 10
    req.step.provider_model_id = model_id
    return req


def _mock_response(content: dict) -> MagicMock:
    mock = MagicMock()
    mock.read.return_value = json.dumps(content).encode("utf-8")
    mock.__enter__ = lambda s: s
    mock.__exit__ = MagicMock(return_value=False)
    return mock


_GOOD_RESPONSE = {
    "choices": [{"message": {"content": "The answer is 42."}}]
}


class ExecuteNoApiKeyTests(unittest.TestCase):
    def test_missing_key_returns_provider_unavailable(self) -> None:
        result = _adapter(api_key=None).execute(_make_request())
        self.assertEqual(result.failure_code, FailureCode.PROVIDER_UNAVAILABLE)
        self.assertEqual(result.status, StepStatus.FAILED)

    def test_empty_key_returns_provider_unavailable(self) -> None:
        result = _adapter(api_key="").execute(_make_request())
        self.assertEqual(result.failure_code, FailureCode.PROVIDER_UNAVAILABLE)

    def test_missing_key_message_contains_provider_label(self) -> None:
        result = _adapter(api_key=None).execute(_make_request())
        assert result.failure_message is not None
        self.assertIn("TestProvider", result.failure_message)


class ExecuteSuccessTests(unittest.TestCase):
    def test_success_returns_completed(self) -> None:
        with patch(
            "gracekelly.adapters.api.base.request.urlopen",
            return_value=_mock_response(_GOOD_RESPONSE),
        ):
            result = _adapter().execute(_make_request())
        self.assertEqual(result.status, StepStatus.COMPLETED)

    def test_success_returns_output_text(self) -> None:
        with patch(
            "gracekelly.adapters.api.base.request.urlopen",
            return_value=_mock_response(_GOOD_RESPONSE),
        ):
            result = _adapter().execute(_make_request())
        self.assertEqual(result.output_text, "The answer is 42.")

    def test_success_details_has_attempts_one(self) -> None:
        with patch(
            "gracekelly.adapters.api.base.request.urlopen",
            return_value=_mock_response(_GOOD_RESPONSE),
        ):
            result = _adapter().execute(_make_request())
        self.assertEqual(result.details["attempts"], 1)

    def test_success_model_id_matches(self) -> None:
        with patch(
            "gracekelly.adapters.api.base.request.urlopen",
            return_value=_mock_response(_GOOD_RESPONSE),
        ):
            result = _adapter().execute(_make_request(model_id="gpt-5-4-api"))
        self.assertEqual(result.model_id, "gpt-5-4-api")


class ExecuteHttpErrorTests(unittest.TestCase):
    def _http_error(self, code: int) -> error.HTTPError:
        return error.HTTPError(
            url="https://api.example.com/chat/completions",
            code=code,
            msg=f"HTTP {code}",
            hdrs=MagicMock(),  # type: ignore[arg-type]
            fp=BytesIO(b""),
        )

    def test_429_without_retry_returns_rate_limited(self) -> None:
        with patch(
            "gracekelly.adapters.api.base.request.urlopen",
            side_effect=self._http_error(429),
        ):
            result = _adapter(max_retries=0).execute(_make_request())
        self.assertEqual(result.failure_code, FailureCode.RATE_LIMITED)

    def test_503_without_retry_returns_provider_unavailable(self) -> None:
        with patch(
            "gracekelly.adapters.api.base.request.urlopen",
            side_effect=self._http_error(503),
        ):
            result = _adapter(max_retries=0).execute(_make_request())
        self.assertEqual(result.failure_code, FailureCode.PROVIDER_UNAVAILABLE)

    def test_non_retryable_404_returns_provider_unavailable(self) -> None:
        with patch(
            "gracekelly.adapters.api.base.request.urlopen",
            side_effect=self._http_error(404),
        ):
            result = _adapter(max_retries=2).execute(_make_request())
        self.assertEqual(result.failure_code, FailureCode.PROVIDER_UNAVAILABLE)

    def test_503_retry_succeeds_on_second_attempt(self) -> None:
        responses = [self._http_error(503), _mock_response(_GOOD_RESPONSE)]
        with patch(
            "gracekelly.adapters.api.base.request.urlopen",
            side_effect=responses,
        ):
            result = _adapter(max_retries=1).execute(_make_request())
        self.assertEqual(result.status, StepStatus.COMPLETED)
        self.assertEqual(result.details["attempts"], 2)

    def test_429_retry_then_success(self) -> None:
        responses = [self._http_error(429), _mock_response(_GOOD_RESPONSE)]
        with patch(
            "gracekelly.adapters.api.base.request.urlopen",
            side_effect=responses,
        ):
            result = _adapter(max_retries=1).execute(_make_request())
        self.assertEqual(result.status, StepStatus.COMPLETED)

    def test_exhausted_retries_503_returns_provider_unavailable(self) -> None:
        """After all retries are spent on 503, final result is PROVIDER_UNAVAILABLE."""
        with patch(
            "gracekelly.adapters.api.base.request.urlopen",
            side_effect=self._http_error(503),
        ):
            result = _adapter(max_retries=2).execute(_make_request())
        self.assertEqual(result.failure_code, FailureCode.PROVIDER_UNAVAILABLE)


class ExecuteTimeoutAndNetworkErrorTests(unittest.TestCase):
    def test_timeout_returns_timeout_failure_code(self) -> None:
        with patch(
            "gracekelly.adapters.api.base.request.urlopen",
            side_effect=TimeoutError("timed out"),
        ):
            result = _adapter(max_retries=0).execute(_make_request())
        self.assertEqual(result.failure_code, FailureCode.TIMEOUT)

    def test_url_error_returns_provider_unavailable(self) -> None:
        with patch(
            "gracekelly.adapters.api.base.request.urlopen",
            side_effect=error.URLError("name resolution failed"),
        ):
            result = _adapter(max_retries=0).execute(_make_request())
        self.assertEqual(result.failure_code, FailureCode.PROVIDER_UNAVAILABLE)

    def test_timeout_retry_succeeds(self) -> None:
        responses: list = [TimeoutError(), _mock_response(_GOOD_RESPONSE)]
        with patch(
            "gracekelly.adapters.api.base.request.urlopen",
            side_effect=responses,
        ):
            result = _adapter(max_retries=1).execute(_make_request())
        self.assertEqual(result.status, StepStatus.COMPLETED)

    def test_url_error_retry_succeeds(self) -> None:
        responses: list = [error.URLError("conn"), _mock_response(_GOOD_RESPONSE)]
        with patch(
            "gracekelly.adapters.api.base.request.urlopen",
            side_effect=responses,
        ):
            result = _adapter(max_retries=1).execute(_make_request())
        self.assertEqual(result.status, StepStatus.COMPLETED)

    def test_exhausted_timeout_retries_returns_timeout(self) -> None:
        with patch(
            "gracekelly.adapters.api.base.request.urlopen",
            side_effect=TimeoutError("timed out"),
        ):
            result = _adapter(max_retries=2).execute(_make_request())
        self.assertEqual(result.failure_code, FailureCode.TIMEOUT)


class ExecuteUnexpectedExceptionTests(unittest.TestCase):
    def test_unexpected_exception_returns_unknown_error(self) -> None:
        with patch(
            "gracekelly.adapters.api.base.request.urlopen",
            side_effect=RuntimeError("something broke"),
        ):
            result = _adapter().execute(_make_request())
        self.assertEqual(result.failure_code, FailureCode.UNKNOWN_ERROR)

    def test_unexpected_exception_not_retried(self) -> None:
        call_count = 0

        def explode(*_args: object, **_kwargs: object) -> None:
            nonlocal call_count
            call_count += 1
            raise RuntimeError("boom")

        with patch("gracekelly.adapters.api.base.request.urlopen", side_effect=explode):
            _adapter(max_retries=3).execute(_make_request())
        self.assertEqual(call_count, 1)


if __name__ == "__main__":
    unittest.main()
