from __future__ import annotations

import threading
import unittest
from collections.abc import Mapping
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from gracekelly.adapters.api.base import BaseApiAdapter
from gracekelly.adapters.dry_run import DryRunExecutionAdapter
from gracekelly.core.contracts import (
    ExecutionAdapter,
    ExecutionMode,
    ExecutionRequest,
    ExecutionResult,
    FailureCode,
    StepStatus,
)


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


def _make_http_status_error(code: int) -> httpx.HTTPStatusError:
    response = MagicMock(spec=httpx.Response)
    response.status_code = code
    response.text = f"HTTP {code}"
    return httpx.HTTPStatusError(
        message=f"HTTP {code}",
        request=MagicMock(spec=httpx.Request),
        response=response,
    )


def _mock_httpx_response(content: Mapping[str, object]) -> MagicMock:
    mock = MagicMock(spec=httpx.Response)
    mock.status_code = 200
    mock.json.return_value = content
    mock.raise_for_status.return_value = None
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
        with patch("httpx.Client.post", return_value=_mock_httpx_response(_GOOD_RESPONSE)):
            result = _adapter().execute(_make_request())
        self.assertEqual(result.status, StepStatus.COMPLETED)

    def test_success_returns_output_text(self) -> None:
        with patch("httpx.Client.post", return_value=_mock_httpx_response(_GOOD_RESPONSE)):
            result = _adapter().execute(_make_request())
        self.assertEqual(result.output_text, "The answer is 42.")

    def test_success_details_has_attempts_one(self) -> None:
        with patch("httpx.Client.post", return_value=_mock_httpx_response(_GOOD_RESPONSE)):
            result = _adapter().execute(_make_request())
        self.assertEqual(result.details["attempts"], 1)

    def test_success_model_id_matches(self) -> None:
        with patch("httpx.Client.post", return_value=_mock_httpx_response(_GOOD_RESPONSE)):
            result = _adapter().execute(_make_request(model_id="gpt-5-4-api"))
        self.assertEqual(result.model_id, "gpt-5-4-api")


class ExecuteHttpErrorTests(unittest.TestCase):
    def test_429_without_retry_returns_rate_limited(self) -> None:
        with patch("httpx.Client.post", side_effect=_make_http_status_error(429)):
            result = _adapter(max_retries=0).execute(_make_request())
        self.assertEqual(result.failure_code, FailureCode.RATE_LIMITED)

    def test_503_without_retry_returns_provider_unavailable(self) -> None:
        with patch("httpx.Client.post", side_effect=_make_http_status_error(503)):
            result = _adapter(max_retries=0).execute(_make_request())
        self.assertEqual(result.failure_code, FailureCode.PROVIDER_UNAVAILABLE)

    def test_non_retryable_404_returns_provider_unavailable(self) -> None:
        with patch("httpx.Client.post", side_effect=_make_http_status_error(404)):
            result = _adapter(max_retries=2).execute(_make_request())
        self.assertEqual(result.failure_code, FailureCode.PROVIDER_UNAVAILABLE)

    def test_503_retry_succeeds_on_second_attempt(self) -> None:
        responses = [_make_http_status_error(503), _mock_httpx_response(_GOOD_RESPONSE)]
        with patch("httpx.Client.post", side_effect=responses):
            result = _adapter(max_retries=1).execute(_make_request())
        self.assertEqual(result.status, StepStatus.COMPLETED)
        self.assertEqual(result.details["attempts"], 2)

    def test_429_retry_then_success(self) -> None:
        responses = [_make_http_status_error(429), _mock_httpx_response(_GOOD_RESPONSE)]
        with patch("httpx.Client.post", side_effect=responses):
            result = _adapter(max_retries=1).execute(_make_request())
        self.assertEqual(result.status, StepStatus.COMPLETED)

    def test_exhausted_retries_503_returns_provider_unavailable(self) -> None:
        """After all retries are spent on 503, final result is PROVIDER_UNAVAILABLE."""
        with patch("httpx.Client.post", side_effect=_make_http_status_error(503)):
            result = _adapter(max_retries=2).execute(_make_request())
        self.assertEqual(result.failure_code, FailureCode.PROVIDER_UNAVAILABLE)


class ExecuteTimeoutAndNetworkErrorTests(unittest.TestCase):
    def test_timeout_returns_timeout_failure_code(self) -> None:
        with patch("httpx.Client.post", side_effect=httpx.TimeoutException("timed out")):
            result = _adapter(max_retries=0).execute(_make_request())
        self.assertEqual(result.failure_code, FailureCode.TIMEOUT)

    def test_connect_error_returns_provider_unavailable(self) -> None:
        with patch("httpx.Client.post", side_effect=httpx.ConnectError("name resolution failed")):
            result = _adapter(max_retries=0).execute(_make_request())
        self.assertEqual(result.failure_code, FailureCode.PROVIDER_UNAVAILABLE)

    def test_timeout_retry_succeeds(self) -> None:
        responses: list[object] = [httpx.TimeoutException("timed out"), _mock_httpx_response(_GOOD_RESPONSE)]
        with patch("httpx.Client.post", side_effect=responses):
            result = _adapter(max_retries=1).execute(_make_request())
        self.assertEqual(result.status, StepStatus.COMPLETED)

    def test_connect_error_retry_succeeds(self) -> None:
        responses: list[object] = [httpx.ConnectError("conn"), _mock_httpx_response(_GOOD_RESPONSE)]
        with patch("httpx.Client.post", side_effect=responses):
            result = _adapter(max_retries=1).execute(_make_request())
        self.assertEqual(result.status, StepStatus.COMPLETED)

    def test_exhausted_timeout_retries_returns_timeout(self) -> None:
        with patch("httpx.Client.post", side_effect=httpx.TimeoutException("timed out")):
            result = _adapter(max_retries=2).execute(_make_request())
        self.assertEqual(result.failure_code, FailureCode.TIMEOUT)


class ExecuteUnexpectedExceptionTests(unittest.TestCase):
    def test_unexpected_exception_returns_unknown_error(self) -> None:
        with patch("httpx.Client.post", side_effect=RuntimeError("something broke")):
            result = _adapter().execute(_make_request())
        self.assertEqual(result.failure_code, FailureCode.UNKNOWN_ERROR)

    def test_unexpected_exception_not_retried(self) -> None:
        call_count = 0

        def explode(*_args: object, **_kwargs: object) -> None:
            nonlocal call_count
            call_count += 1
            raise RuntimeError("boom")

        with patch("httpx.Client.post", side_effect=explode):
            _adapter(max_retries=3).execute(_make_request())
        self.assertEqual(call_count, 1)


class ExecuteAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_execute_async_returns_result(self) -> None:
        adapter = _adapter()
        self.assertTrue(hasattr(adapter, "execute_async"))
        with patch.object(
            adapter,
            "_async_post_json",
            AsyncMock(return_value=_GOOD_RESPONSE),
            create=True,
        ) as mock_post:
            result = await adapter.execute_async(_make_request())
        self.assertEqual(result.status, StepStatus.COMPLETED)
        self.assertEqual(result.output_text, "The answer is 42.")
        self.assertEqual(mock_post.await_count, 1)

    async def test_execute_async_retries_on_429(self) -> None:
        adapter = _adapter(max_retries=1)
        self.assertTrue(hasattr(adapter, "execute_async"))
        with patch.object(
            adapter,
            "_async_post_json",
            AsyncMock(side_effect=[_make_http_status_error(429), _GOOD_RESPONSE]),
            create=True,
        ) as mock_post:
            result = await adapter.execute_async(_make_request())
        self.assertEqual(result.status, StepStatus.COMPLETED)
        self.assertEqual(result.details["attempts"], 2)
        self.assertEqual(mock_post.await_count, 2)

    async def test_execute_async_timeout(self) -> None:
        adapter = _adapter(max_retries=0)
        self.assertTrue(hasattr(adapter, "execute_async"))
        with patch.object(
            adapter,
            "_async_post_json",
            AsyncMock(side_effect=httpx.TimeoutException("timed out")),
            create=True,
        ):
            result = await adapter.execute_async(_make_request())
        self.assertEqual(result.failure_code, FailureCode.TIMEOUT)

    async def test_dry_run_execute_async_matches_execute(self) -> None:
        adapter = DryRunExecutionAdapter()
        request = _make_request()
        request.models = (request.step.model,)
        self.assertTrue(hasattr(adapter, "execute_async"))
        sync_result = adapter.execute(request)
        async_result = await adapter.execute_async(request)
        self.assertEqual(async_result.status, StepStatus.COMPLETED)
        self.assertEqual(async_result.execution_mode, ExecutionMode.DRY_RUN)
        self.assertEqual(async_result.output_text, sync_result.output_text)
        self.assertEqual(async_result.details, sync_result.details)

    async def test_default_execute_async_calls_execute_in_thread(self) -> None:
        class _ConcreteAdapter(ExecutionAdapter):
            name = "thread-check"

            def __init__(self) -> None:
                self.execute_thread_id: int | None = None

            def execute(self, request: ExecutionRequest) -> ExecutionResult:
                self.execute_thread_id = threading.get_ident()
                return ExecutionResult(
                    adapter_name=self.name,
                    model_id="m1",
                    model_display_name="M1",
                    execution_mode=ExecutionMode.API,
                    status=StepStatus.COMPLETED,
                    output_text=request.prompt,
                )

        adapter = _ConcreteAdapter()
        request = _make_request()
        self.assertTrue(hasattr(adapter, "execute_async"))
        caller_thread_id = threading.get_ident()
        result = await adapter.execute_async(request)
        self.assertEqual(result.output_text, "Hello")
        self.assertIsNotNone(adapter.execute_thread_id)
        self.assertNotEqual(adapter.execute_thread_id, caller_thread_id)


if __name__ == "__main__":
    unittest.main()
