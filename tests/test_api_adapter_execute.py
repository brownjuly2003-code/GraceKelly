from __future__ import annotations

import asyncio
import threading
import unittest
import urllib.error
from collections.abc import Mapping
from http.client import HTTPMessage
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from gracekelly.adapters.api.base import BaseApiAdapter
from gracekelly.adapters.dry_run import DryRunExecutionAdapter
from gracekelly.core.contracts import (
    AdapterHint,
    ExecutionAdapter,
    ExecutionBackend,
    ExecutionMode,
    ExecutionPlan,
    ExecutionRequest,
    ExecutionResult,
    ExecutionStep,
    FailureCode,
    MergeStrategy,
    StepStatus,
)

pytestmark = pytest.mark.usefixtures("inject_shared_test_factories")

if TYPE_CHECKING:
    def _make_request(*, model_id: str = "m1", display_name: str = "M1") -> MagicMock: ...


def _adapter(*, api_key: str | None = "test-key", max_retries: int = 0) -> BaseApiAdapter:
    return BaseApiAdapter(
        api_key=api_key,
        base_url="https://api.example.com",
        timeout_seconds=10.0,
        provider_label="TestProvider",
        max_retries=max_retries,
        retry_backoff_seconds=0.0,
    )


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
    async def test_default_execute_async_wraps_execute_with_asyncio_to_thread(self) -> None:
        expected = ExecutionResult(
            adapter_name="thread-check",
            model_id="m1",
            model_display_name="M1",
            execution_mode=ExecutionMode.API,
            status=StepStatus.COMPLETED,
            output_text="wrapped",
        )

        class _ConcreteAdapter(ExecutionAdapter):
            name = "thread-check"

            def execute(self, request: ExecutionRequest) -> ExecutionResult:
                return expected

        adapter = _ConcreteAdapter()
        request = _make_request()
        with patch("asyncio.to_thread", AsyncMock(return_value=expected)) as mock_to_thread:
            result = await adapter.execute_async(request)
        self.assertIs(result, expected)
        mock_to_thread.assert_awaited_once()
        assert mock_to_thread.await_args is not None
        wrapped_call, wrapped_request = mock_to_thread.await_args.args
        self.assertIs(wrapped_call.__self__, adapter)
        self.assertIs(wrapped_call.__func__, _ConcreteAdapter.execute)
        self.assertIs(wrapped_request, request)

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

    async def test_dry_run_execute_async_accepts_real_execution_request(self) -> None:
        adapter = DryRunExecutionAdapter()
        model = MagicMock()
        model.id = "gpt-5-4-api"
        model.display_name = "GPT-5.4 API"
        step = ExecutionStep(
            model=model,
            backend=ExecutionBackend.API,
            provider="openai",
            provider_model_id="gpt-5.4",
            step_index=0,
        )
        plan = ExecutionPlan(
            steps=(step,),
            quorum=1,
            merge_strategy=MergeStrategy.FIRST_SUCCESS,
            dry_run=False,
            adapter_hint=AdapterHint.API,
            cancel_on_quorum=False,
        )
        request = ExecutionRequest(
            task_id="t1",
            prompt="hello",
            plan=plan,
            step=step,
            reasoning=False,
        )

        result = await adapter.execute_async(request)

        self.assertEqual(result.status, StepStatus.COMPLETED)
        self.assertEqual(result.execution_mode, ExecutionMode.DRY_RUN)
        self.assertIsNotNone(result.output_text)
        self.assertIn("[dry-run]", result.output_text or "")
        self.assertEqual(result.details["requested_models"], ["GPT-5.4 API"])

    async def test_default_execute_async_calls_execute_in_thread(self) -> None:
        class _ConcreteAdapter(ExecutionAdapter):
            name = "thread-check"

            def __init__(self) -> None:
                self.execute_thread_id: int | None = None
                self.executed_on_main_thread: bool | None = None

            def execute(self, request: ExecutionRequest) -> ExecutionResult:
                self.execute_thread_id = threading.get_ident()
                self.executed_on_main_thread = threading.current_thread() is threading.main_thread()
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
        self.assertIs(adapter.executed_on_main_thread, False)


class AsyncRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_batch_route_uses_execute_async_without_blocking_event_loop(self) -> None:
        from gracekelly.api.routes.batch import BatchRequest, run_batch

        execute_started = asyncio.Event()
        allow_finish = asyncio.Event()
        ticker_ran = asyncio.Event()
        state = {"async_calls": 0}

        class _AsyncOnlyAdapter(ExecutionAdapter):
            name = "async-only"

            def execute(self, request: ExecutionRequest) -> ExecutionResult:
                raise AssertionError("batch route should not call execute()")

            async def execute_async(self, request: ExecutionRequest) -> ExecutionResult:
                state["async_calls"] += 1
                execute_started.set()
                await allow_finish.wait()
                return ExecutionResult(
                    adapter_name=self.name,
                    model_id=request.step.model.id,
                    model_display_name=request.step.model.display_name,
                    execution_mode=ExecutionMode.API,
                    status=StepStatus.COMPLETED,
                    output_text=f"ok:{request.prompt}",
                )

        async def ticker() -> None:
            await execute_started.wait()
            await asyncio.sleep(0)
            ticker_ran.set()
            allow_finish.set()

        request = MagicMock()
        request.app.state.api_adapters = {"openai": _AsyncOnlyAdapter()}

        route_task = asyncio.create_task(
            run_batch(
                BatchRequest(prompts=["hello"], model="gpt-5-4-api"),
                request,
            )
        )
        ticker_task = asyncio.create_task(ticker())

        response = await asyncio.wait_for(route_task, timeout=1.0)
        await asyncio.wait_for(ticker_task, timeout=1.0)

        self.assertTrue(ticker_ran.is_set())
        self.assertEqual(state["async_calls"], 1)
        self.assertEqual(response.succeeded, 1)
        self.assertEqual(response.failed, 0)
        self.assertEqual(response.results[0].answer, "ok:hello")


class BaseApiAdapterUtilityTests(unittest.TestCase):
    def test_close_without_running_loop_uses_asyncio_run(self) -> None:
        adapter = _adapter()
        with (
            patch.object(adapter._http_client, "close") as mock_close,
            patch("gracekelly.adapters.api.base.asyncio.get_running_loop", side_effect=RuntimeError),
            patch(
                "gracekelly.adapters.api.base.asyncio.run",
                side_effect=lambda coro: coro.close(),
            ) as mock_run,
        ):
            adapter.close()
        mock_close.assert_called_once_with()
        mock_run.assert_called_once()

    def test_close_with_running_loop_schedules_async_close(self) -> None:
        adapter = _adapter()
        loop = MagicMock()
        with (
            patch.object(adapter._http_client, "close") as mock_close,
            patch("gracekelly.adapters.api.base.asyncio.get_running_loop", return_value=loop),
        ):
            adapter.close()
        mock_close.assert_called_once_with()
        loop.create_task.assert_called_once()
        loop.create_task.call_args.args[0].close()

    def test_has_api_key_reflects_truthiness(self) -> None:
        self.assertTrue(_adapter(api_key="token").has_api_key)
        self.assertFalse(_adapter(api_key="").has_api_key)

    def test_healthcheck_without_key_is_degraded(self) -> None:
        healthcheck = _adapter(api_key=None).healthcheck()
        self.assertEqual(healthcheck["status"], "degraded")
        self.assertEqual(healthcheck["configured"], False)

    def test_healthcheck_with_key_reports_configuration(self) -> None:
        healthcheck = _adapter().healthcheck()
        self.assertEqual(healthcheck["status"], "ok")
        self.assertEqual(healthcheck["configured"], True)
        self.assertNotIn("base_url", healthcheck)
        self.assertNotIn("default_timeout_seconds", healthcheck)
        self.assertNotIn("max_retries", healthcheck)
        self.assertNotIn("retry_backoff_seconds", healthcheck)

    def test_resolve_timeout_uses_default_for_nonpositive_model_timeout(self) -> None:
        adapter = _adapter()
        request = _make_request()
        request.step.model.timeout_seconds = 0
        self.assertEqual(adapter._resolve_timeout_seconds(request), 10.0)

    def test_resolve_timeout_prefers_model_timeout(self) -> None:
        adapter = _adapter()
        request = _make_request()
        request.step.model.timeout_seconds = 7
        self.assertEqual(adapter._resolve_timeout_seconds(request), 7.0)


class BaseApiAdapterPostJsonTests(unittest.IsolatedAsyncioTestCase):
    async def test_aclose_closes_async_client(self) -> None:
        adapter = _adapter()
        with patch.object(adapter._async_http_client, "aclose", AsyncMock()) as mock_aclose:
            await adapter.aclose()
        mock_aclose.assert_awaited_once_with()

    def test_post_json_merges_extra_headers(self) -> None:
        adapter = _adapter()
        response = _mock_httpx_response(_GOOD_RESPONSE)
        with patch.object(adapter._http_client, "post", return_value=response) as mock_post:
            result = adapter._post_json(
                "/chat/completions",
                {"hello": "world"},
                timeout_seconds=12.0,
                extra_headers={"X-Test": "1"},
            )
        self.assertEqual(result, _GOOD_RESPONSE)
        self.assertEqual(mock_post.call_args.kwargs["headers"]["X-Test"], "1")
        self.assertEqual(mock_post.call_args.kwargs["headers"]["Authorization"], "Bearer test-key")

    def test_post_json_rejects_non_dict_response(self) -> None:
        adapter = _adapter()
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.return_value = ["not", "a", "dict"]
        response.raise_for_status.return_value = None
        with patch.object(adapter._http_client, "post", return_value=response):
            with self.assertRaisesRegex(ValueError, "Expected dict response"):
                adapter._post_json("/chat/completions", {}, timeout_seconds=3.0)

    async def test_async_post_json_uses_to_thread_when_sync_post_is_overridden(self) -> None:
        class _OverriddenPostAdapter(BaseApiAdapter):
            def _post_json(
                self,
                path: str,
                payload: dict[str, object],
                *,
                timeout_seconds: float,
                extra_headers: dict[str, str] | None = None,
            ) -> dict[str, object]:
                return {"choices": [{"message": {"content": "threaded"}}]}

        adapter = _OverriddenPostAdapter(
            api_key="test-key",
            base_url="https://api.example.com",
            timeout_seconds=10.0,
            provider_label="TestProvider",
            retry_backoff_seconds=0.0,
        )
        with patch(
            "gracekelly.adapters.api.base.asyncio.to_thread",
            AsyncMock(return_value=_GOOD_RESPONSE),
        ) as mock_to_thread:
            result = await adapter._async_post_json("/chat/completions", {}, timeout_seconds=5.0)
        self.assertEqual(result, _GOOD_RESPONSE)
        mock_to_thread.assert_awaited_once()

    async def test_async_post_json_merges_extra_headers(self) -> None:
        adapter = _adapter()
        response = _mock_httpx_response(_GOOD_RESPONSE)
        with patch.object(adapter._async_http_client, "post", AsyncMock(return_value=response)) as mock_post:
            result = await adapter._async_post_json(
                "/chat/completions",
                {"hello": "world"},
                timeout_seconds=12.0,
                extra_headers={"X-Test": "1"},
            )
        self.assertEqual(result, _GOOD_RESPONSE)
        self.assertEqual(mock_post.call_args.kwargs["headers"]["X-Test"], "1")
        self.assertEqual(mock_post.call_args.kwargs["headers"]["Authorization"], "Bearer test-key")

    async def test_async_post_json_rejects_non_dict_response(self) -> None:
        adapter = _adapter()
        response = MagicMock(spec=httpx.Response)
        response.status_code = 200
        response.json.return_value = ["not", "a", "dict"]
        response.raise_for_status.return_value = None
        with patch.object(adapter._async_http_client, "post", AsyncMock(return_value=response)):
            with self.assertRaisesRegex(ValueError, "Expected dict response"):
                await adapter._async_post_json("/chat/completions", {}, timeout_seconds=3.0)


class BaseApiAdapterStreamTests(unittest.TestCase):
    def test_post_stream_filters_non_data_lines(self) -> None:
        adapter = _adapter()
        response = MagicMock(spec=httpx.Response)
        response.iter_lines.return_value = ["event: ping", "data: first", "data: second"]
        context_manager = MagicMock()
        context_manager.__enter__.return_value = response
        context_manager.__exit__.return_value = None
        with patch.object(adapter._http_client, "stream", return_value=context_manager):
            chunks = list(adapter._post_stream("/chat/completions", {}, timeout_seconds=4.0))
        self.assertEqual(chunks, ["first", "second"])

    def test_execute_stream_without_api_key_yields_error_chunk(self) -> None:
        chunks = list(_adapter(api_key=None).execute_stream(_make_request()))
        self.assertEqual([chunk.type for chunk in chunks], ["error"])
        self.assertIn("API key not configured", chunks[0].text)

    def test_execute_stream_emits_deltas_and_complete_with_usage(self) -> None:
        adapter = _adapter()
        with patch.object(
            adapter,
            "_post_stream",
            return_value=iter(
                [
                    '{"usage":{"prompt_tokens":5,"completion_tokens":2}}',
                    "[]",
                    '{"choices":[1]}',
                    '{"choices":[{"delta":null}]}',
                    '{"choices":[{"delta":{"content":"Hel"}}]}',
                    '{"choices":[{"delta":{"content":"lo"}}]}',
                    "[DONE]",
                ],
            ),
        ):
            chunks = list(adapter.execute_stream(_make_request()))
        self.assertEqual([chunk.type for chunk in chunks], ["delta", "delta", "complete"])
        self.assertEqual([chunk.text for chunk in chunks[:2]], ["Hel", "lo"])
        self.assertEqual(chunks[2].text, "Hello")
        self.assertEqual(chunks[2].details["input_tokens"], 5)
        self.assertEqual(chunks[2].details["output_tokens"], 2)

    def test_execute_stream_yields_error_chunk_on_exception(self) -> None:
        adapter = _adapter()
        with patch.object(adapter, "_post_stream", side_effect=RuntimeError("boom")):
            chunks = list(adapter.execute_stream(_make_request()))
        self.assertEqual([chunk.type for chunk in chunks], ["error"])
        self.assertIn("streaming error", chunks[0].text)


class BaseApiAdapterExtractOutputTests(unittest.TestCase):
    def test_extract_output_text_requires_choices(self) -> None:
        with self.assertRaisesRegex(ValueError, "Missing choices"):
            _adapter()._extract_output_text({})

    def test_extract_output_text_requires_choice_dict(self) -> None:
        with self.assertRaisesRegex(ValueError, "Invalid choice payload"):
            _adapter()._extract_output_text({"choices": ["bad"]})

    def test_extract_output_text_requires_message_dict(self) -> None:
        with self.assertRaisesRegex(ValueError, "Missing message payload"):
            _adapter()._extract_output_text({"choices": [{}]})

    def test_extract_output_text_requires_nonempty_content(self) -> None:
        with self.assertRaisesRegex(ValueError, "Missing content"):
            _adapter()._extract_output_text({"choices": [{"message": {"content": "   "}}]})


class BaseApiAdapterSyncEdgeCaseTests(unittest.TestCase):
    def test_builtin_timeout_error_returns_timeout(self) -> None:
        with patch("httpx.Client.post", side_effect=TimeoutError("timed out")):
            result = _adapter(max_retries=0).execute(_make_request())
        self.assertEqual(result.failure_code, FailureCode.TIMEOUT)

    def test_http_error_429_returns_rate_limited(self) -> None:
        with patch(
            "httpx.Client.post",
            side_effect=urllib.error.HTTPError(
                "https://api.example.com",
                429,
                "rate limit",
                HTTPMessage(),
                None,
            ),
        ):
            result = _adapter(max_retries=0).execute(_make_request())
        self.assertEqual(result.failure_code, FailureCode.RATE_LIMITED)

    def test_url_error_returns_provider_unavailable(self) -> None:
        with patch("httpx.Client.post", side_effect=urllib.error.URLError("offline")):
            result = _adapter(max_retries=0).execute(_make_request())
        self.assertEqual(result.failure_code, FailureCode.PROVIDER_UNAVAILABLE)
        assert result.failure_message is not None
        self.assertIn("offline", result.failure_message)


class BaseApiAdapterAsyncEdgeCaseTests(unittest.IsolatedAsyncioTestCase):
    async def test_execute_async_missing_key_returns_provider_unavailable(self) -> None:
        result = await _adapter(api_key=None).execute_async(_make_request())
        self.assertEqual(result.failure_code, FailureCode.PROVIDER_UNAVAILABLE)

    async def test_execute_async_500_without_retry_returns_provider_unavailable(self) -> None:
        adapter = _adapter(max_retries=0)
        with patch.object(
            adapter,
            "_async_post_json",
            AsyncMock(side_effect=_make_http_status_error(500)),
            create=True,
        ) as mock_post:
            result = await adapter.execute_async(_make_request())
        self.assertEqual(result.status, StepStatus.FAILED)
        self.assertEqual(result.failure_code, FailureCode.PROVIDER_UNAVAILABLE)
        self.assertEqual(mock_post.await_count, 1)

    async def test_execute_async_503_without_retry_returns_provider_unavailable(self) -> None:
        adapter = _adapter(max_retries=0)
        with patch.object(
            adapter,
            "_async_post_json",
            AsyncMock(side_effect=_make_http_status_error(503)),
            create=True,
        ):
            result = await adapter.execute_async(_make_request())
        self.assertEqual(result.failure_code, FailureCode.PROVIDER_UNAVAILABLE)

    async def test_execute_async_429_without_retry_returns_rate_limited(self) -> None:
        adapter = _adapter(max_retries=0)
        with patch.object(
            adapter,
            "_async_post_json",
            AsyncMock(side_effect=_make_http_status_error(429)),
            create=True,
        ):
            result = await adapter.execute_async(_make_request())
        self.assertEqual(result.failure_code, FailureCode.RATE_LIMITED)

    async def test_execute_async_request_error_returns_provider_unavailable(self) -> None:
        adapter = _adapter(max_retries=0)
        with patch.object(
            adapter,
            "_async_post_json",
            AsyncMock(side_effect=httpx.ConnectError("offline")),
            create=True,
        ):
            result = await adapter.execute_async(_make_request())
        self.assertEqual(result.failure_code, FailureCode.PROVIDER_UNAVAILABLE)

    async def test_execute_async_network_error_returns_provider_unavailable(self) -> None:
        adapter = _adapter(max_retries=0)
        with patch.object(
            adapter,
            "_async_post_json",
            AsyncMock(side_effect=httpx.NetworkError("offline")),
            create=True,
        ) as mock_post:
            result = await adapter.execute_async(_make_request())
        self.assertEqual(result.failure_code, FailureCode.PROVIDER_UNAVAILABLE)
        self.assertEqual(mock_post.await_count, 1)

    async def test_execute_async_timeout_retries_then_succeeds(self) -> None:
        adapter = _adapter(max_retries=1)
        with patch.object(
            adapter,
            "_async_post_json",
            AsyncMock(side_effect=[httpx.TimeoutException("timed out"), _GOOD_RESPONSE]),
            create=True,
        ) as mock_post:
            result = await adapter.execute_async(_make_request())
        self.assertEqual(result.status, StepStatus.COMPLETED)
        self.assertEqual(result.details["attempts"], 2)
        self.assertEqual(mock_post.await_count, 2)

    async def test_execute_async_builtin_timeout_error_returns_timeout(self) -> None:
        adapter = _adapter(max_retries=0)
        with patch.object(
            adapter,
            "_async_post_json",
            AsyncMock(side_effect=TimeoutError("timed out")),
            create=True,
        ):
            result = await adapter.execute_async(_make_request())
        self.assertEqual(result.failure_code, FailureCode.TIMEOUT)

    async def test_execute_async_url_error_returns_provider_unavailable(self) -> None:
        adapter = _adapter(max_retries=0)
        with patch.object(
            adapter,
            "_async_post_json",
            AsyncMock(side_effect=urllib.error.URLError("offline")),
            create=True,
        ):
            result = await adapter.execute_async(_make_request())
        self.assertEqual(result.failure_code, FailureCode.PROVIDER_UNAVAILABLE)

    async def test_execute_async_unexpected_exception_returns_unknown_error(self) -> None:
        adapter = _adapter(max_retries=0)
        with patch.object(
            adapter,
            "_async_post_json",
            AsyncMock(side_effect=RuntimeError("boom")),
            create=True,
        ):
            result = await adapter.execute_async(_make_request())
        self.assertEqual(result.failure_code, FailureCode.UNKNOWN_ERROR)


if __name__ == "__main__":
    unittest.main()
