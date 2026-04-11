from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Iterator

import httpx

from gracekelly.core.contracts import (
    ExecutionAdapter,
    ExecutionMode,
    ExecutionRequest,
    ExecutionResult,
    FailureCode,
    StepStatus,
    StreamChunk,
)

logger = logging.getLogger(__name__)

_RETRYABLE_HTTP_CODES = frozenset({429, 500, 502, 503, 504})


class BaseApiAdapter(ExecutionAdapter):
    name: str = "api.base"

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str,
        timeout_seconds: float,
        provider_label: str,
        max_retries: int = 0,
        retry_backoff_seconds: float = 1.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._default_timeout_seconds = timeout_seconds
        self._provider_label = provider_label
        self._max_retries = max(0, max_retries)
        self._retry_backoff_seconds = retry_backoff_seconds
        self._http_client = httpx.Client(
            timeout=None,  # nosec B113 — timeout is set per-request in _post_json
            follow_redirects=True,
        )
        self._async_http_client = httpx.AsyncClient(
            timeout=None,  # nosec B113 — timeout is set per-request in _async_post_json
            follow_redirects=True,
        )

    def close(self) -> None:
        self._http_client.close()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self.aclose())
        else:
            loop.create_task(self.aclose())

    async def aclose(self) -> None:
        await self._async_http_client.aclose()

    @property
    def has_api_key(self) -> bool:
        return bool(self._api_key)

    def execute(self, request_model: ExecutionRequest) -> ExecutionResult:
        model = request_model.step.model
        timeout_seconds = self._resolve_timeout_seconds(request_model)
        if not self._api_key:
            return self._failure(
                model.id,
                model.display_name,
                FailureCode.PROVIDER_UNAVAILABLE,
                f"{self._provider_label} API key is not configured.",
            )
        if request_model.attachments:
            logger.warning("API adapter ignores image attachments (not supported)")

        payload: dict[str, object] = {
            "model": request_model.step.provider_model_id,
            "messages": [{"role": "user", "content": request_model.prompt}],
        }

        last_error: Exception | None = None
        attempts = 1 + self._max_retries
        for attempt in range(1, attempts + 1):
            try:
                response_data = self._post_json(
                    "/chat/completions", payload, timeout_seconds=timeout_seconds,
                )
                output_text = self._extract_output_text(response_data)
                usage = response_data.get("usage", {})
                input_tokens = None
                output_tokens = None
                if isinstance(usage, dict):
                    input_tokens = usage.get("prompt_tokens") or usage.get("input_tokens")
                    output_tokens = usage.get("completion_tokens") or usage.get("output_tokens")
                return ExecutionResult(
                    adapter_name=self.name,
                    model_id=model.id,
                    model_display_name=model.display_name,
                    execution_mode=ExecutionMode.API,
                    status=StepStatus.COMPLETED,
                    output_text=output_text,
                    input_tokens=int(input_tokens) if input_tokens is not None else None,
                    output_tokens=int(output_tokens) if output_tokens is not None else None,
                    details={
                        "provider": self._provider_label.lower(),
                        "provider_model_id": request_model.step.provider_model_id,
                        "timeout_seconds": timeout_seconds,
                        "attempts": attempt,
                    },
                )
            except httpx.HTTPStatusError as exc:
                last_error = exc
                status_code = exc.response.status_code
                if status_code in _RETRYABLE_HTTP_CODES and attempt < attempts:
                    self._sleep_before_retry(attempt)
                    continue
                if status_code == 429:
                    return self._failure(
                        model.id, model.display_name, FailureCode.RATE_LIMITED,
                        f"{self._provider_label} rate limit reached.",
                    )
                return self._failure(
                    model.id, model.display_name, FailureCode.PROVIDER_UNAVAILABLE,
                    f"{self._provider_label} HTTP error: {status_code}",
                )
            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt < attempts:
                    self._sleep_before_retry(attempt)
                    continue
                return self._failure(
                    model.id, model.display_name, FailureCode.TIMEOUT,
                    f"{self._provider_label} request timed out.",
                )
            except httpx.RequestError as exc:
                last_error = exc
                if attempt < attempts:
                    self._sleep_before_retry(attempt)
                    continue
                return self._failure(
                    model.id, model.display_name, FailureCode.PROVIDER_UNAVAILABLE,
                    f"{self._provider_label} network error: {exc}",
                )
            except TimeoutError as exc:
                # Covers built-in TimeoutError raised by subclass adapters (e.g. urllib-based)
                last_error = exc
                if attempt < attempts:
                    self._sleep_before_retry(attempt)
                    continue
                return self._failure(
                    model.id, model.display_name, FailureCode.TIMEOUT,
                    f"{self._provider_label} request timed out.",
                )
            except OSError as exc:
                # Covers urllib.error.HTTPError / urllib.error.URLError from subclass adapters
                last_error = exc
                code = getattr(exc, "code", None)
                reason = getattr(exc, "reason", None)
                if isinstance(code, int):
                    if code in _RETRYABLE_HTTP_CODES and attempt < attempts:
                        self._sleep_before_retry(attempt)
                        continue
                    if code == 429:
                        return self._failure(
                            model.id, model.display_name, FailureCode.RATE_LIMITED,
                            f"{self._provider_label} rate limit reached.",
                        )
                    return self._failure(
                        model.id, model.display_name, FailureCode.PROVIDER_UNAVAILABLE,
                        f"{self._provider_label} HTTP error: {code}",
                    )
                if attempt < attempts:
                    self._sleep_before_retry(attempt)
                    continue
                return self._failure(
                    model.id, model.display_name, FailureCode.PROVIDER_UNAVAILABLE,
                    f"{self._provider_label} network error: {reason or exc}",
                )
            except Exception as exc:
                return self._failure(
                    model.id, model.display_name, FailureCode.UNKNOWN_ERROR,
                    f"{self._provider_label} adapter error: {exc}",
                )

        return self._failure(
            model.id, model.display_name, FailureCode.UNKNOWN_ERROR,
            f"{self._provider_label} failed after {attempts} attempts: {last_error}",
        )

    async def execute_async(self, request_model: ExecutionRequest) -> ExecutionResult:
        model = request_model.step.model
        timeout_seconds = self._resolve_timeout_seconds(request_model)
        if not self._api_key:
            return self._failure(
                model.id,
                model.display_name,
                FailureCode.PROVIDER_UNAVAILABLE,
                f"{self._provider_label} API key is not configured.",
            )
        if request_model.attachments:
            logger.warning("API adapter ignores image attachments (not supported)")

        payload: dict[str, object] = {
            "model": request_model.step.provider_model_id,
            "messages": [{"role": "user", "content": request_model.prompt}],
        }

        last_error: Exception | None = None
        attempts = 1 + self._max_retries
        for attempt in range(1, attempts + 1):
            try:
                response_data = await self._async_post_json(
                    "/chat/completions", payload, timeout_seconds=timeout_seconds,
                )
                output_text = self._extract_output_text(response_data)
                usage = response_data.get("usage", {})
                input_tokens = None
                output_tokens = None
                if isinstance(usage, dict):
                    input_tokens = usage.get("prompt_tokens") or usage.get("input_tokens")
                    output_tokens = usage.get("completion_tokens") or usage.get("output_tokens")
                return ExecutionResult(
                    adapter_name=self.name,
                    model_id=model.id,
                    model_display_name=model.display_name,
                    execution_mode=ExecutionMode.API,
                    status=StepStatus.COMPLETED,
                    output_text=output_text,
                    input_tokens=int(input_tokens) if input_tokens is not None else None,
                    output_tokens=int(output_tokens) if output_tokens is not None else None,
                    details={
                        "provider": self._provider_label.lower(),
                        "provider_model_id": request_model.step.provider_model_id,
                        "timeout_seconds": timeout_seconds,
                        "attempts": attempt,
                    },
                )
            except httpx.HTTPStatusError as exc:
                last_error = exc
                status_code = exc.response.status_code
                if status_code in _RETRYABLE_HTTP_CODES and attempt < attempts:
                    delay = self._retry_backoff_seconds * (2 ** (attempt - 1))
                    logger.info(
                        "%s retry attempt=%d delay=%.1fs",
                        self._provider_label, attempt + 1, delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                if status_code == 429:
                    return self._failure(
                        model.id, model.display_name, FailureCode.RATE_LIMITED,
                        f"{self._provider_label} rate limit reached.",
                    )
                return self._failure(
                    model.id, model.display_name, FailureCode.PROVIDER_UNAVAILABLE,
                    f"{self._provider_label} HTTP error: {status_code}",
                )
            except httpx.TimeoutException as exc:
                last_error = exc
                if attempt < attempts:
                    delay = self._retry_backoff_seconds * (2 ** (attempt - 1))
                    logger.info(
                        "%s retry attempt=%d delay=%.1fs",
                        self._provider_label, attempt + 1, delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                return self._failure(
                    model.id, model.display_name, FailureCode.TIMEOUT,
                    f"{self._provider_label} request timed out.",
                )
            except httpx.RequestError as exc:
                last_error = exc
                if attempt < attempts:
                    delay = self._retry_backoff_seconds * (2 ** (attempt - 1))
                    logger.info(
                        "%s retry attempt=%d delay=%.1fs",
                        self._provider_label, attempt + 1, delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                return self._failure(
                    model.id, model.display_name, FailureCode.PROVIDER_UNAVAILABLE,
                    f"{self._provider_label} network error: {exc}",
                )
            except TimeoutError as exc:
                last_error = exc
                if attempt < attempts:
                    delay = self._retry_backoff_seconds * (2 ** (attempt - 1))
                    logger.info(
                        "%s retry attempt=%d delay=%.1fs",
                        self._provider_label, attempt + 1, delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                return self._failure(
                    model.id, model.display_name, FailureCode.TIMEOUT,
                    f"{self._provider_label} request timed out.",
                )
            except OSError as exc:
                last_error = exc
                code = getattr(exc, "code", None)
                reason = getattr(exc, "reason", None)
                if isinstance(code, int):
                    if code in _RETRYABLE_HTTP_CODES and attempt < attempts:
                        delay = self._retry_backoff_seconds * (2 ** (attempt - 1))
                        logger.info(
                            "%s retry attempt=%d delay=%.1fs",
                            self._provider_label, attempt + 1, delay,
                        )
                        await asyncio.sleep(delay)
                        continue
                    if code == 429:
                        return self._failure(
                            model.id, model.display_name, FailureCode.RATE_LIMITED,
                            f"{self._provider_label} rate limit reached.",
                        )
                    return self._failure(
                        model.id, model.display_name, FailureCode.PROVIDER_UNAVAILABLE,
                        f"{self._provider_label} HTTP error: {code}",
                    )
                if attempt < attempts:
                    delay = self._retry_backoff_seconds * (2 ** (attempt - 1))
                    logger.info(
                        "%s retry attempt=%d delay=%.1fs",
                        self._provider_label, attempt + 1, delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                return self._failure(
                    model.id, model.display_name, FailureCode.PROVIDER_UNAVAILABLE,
                    f"{self._provider_label} network error: {reason or exc}",
                )
            except Exception as exc:
                return self._failure(
                    model.id, model.display_name, FailureCode.UNKNOWN_ERROR,
                    f"{self._provider_label} adapter error: {exc}",
                )

        return self._failure(
            model.id, model.display_name, FailureCode.UNKNOWN_ERROR,
            f"{self._provider_label} failed after {attempts} attempts: {last_error}",
        )

    def execute_stream(self, request_model: ExecutionRequest) -> Iterator[StreamChunk]:
        model = request_model.step.model
        timeout_seconds = self._resolve_timeout_seconds(request_model)
        if not self._api_key:
            yield StreamChunk(type="error", text=f"{self._provider_label} API key not configured.")
            return

        payload: dict[str, object] = {
            "model": request_model.step.provider_model_id,
            "messages": [{"role": "user", "content": request_model.prompt}],
            "stream": True,
            "stream_options": {"include_usage": True},
        }

        collected_text = ""
        input_tokens = None
        output_tokens = None
        start = time.monotonic()
        try:
            for raw_data in self._post_stream("/chat/completions", payload, timeout_seconds=timeout_seconds):
                if raw_data.strip() == "[DONE]":
                    break
                chunk_json = json.loads(raw_data)
                if not isinstance(chunk_json, dict):
                    continue
                usage = chunk_json.get("usage")
                if isinstance(usage, dict):
                    input_tokens = usage.get("prompt_tokens") or usage.get("input_tokens")
                    output_tokens = usage.get("completion_tokens") or usage.get("output_tokens")
                choices = chunk_json.get("choices")
                if not isinstance(choices, list) or not choices:
                    continue
                first_choice = choices[0]
                if not isinstance(first_choice, dict):
                    continue
                delta = first_choice.get("delta")
                if not isinstance(delta, dict):
                    continue
                content = delta.get("content", "")
                if isinstance(content, str) and content:
                    collected_text += content
                    yield StreamChunk(type="delta", text=content, model_id=model.id)

            duration_ms = int((time.monotonic() - start) * 1000)
            yield StreamChunk(
                type="complete",
                text=collected_text,
                model_id=model.id,
                details={
                    "duration_ms": duration_ms,
                    "provider": self._provider_label.lower(),
                    "input_tokens": int(input_tokens) if input_tokens is not None else None,
                    "output_tokens": int(output_tokens) if output_tokens is not None else None,
                },
            )
        except Exception as exc:
            yield StreamChunk(type="error", text=f"{self._provider_label} streaming error: {exc}")

    def _sleep_before_retry(self, attempt: int) -> None:
        delay = self._retry_backoff_seconds * (2 ** (attempt - 1))
        logger.info(
            "%s retry attempt=%d delay=%.1fs",
            self._provider_label, attempt + 1, delay,
        )
        time.sleep(delay)

    def _resolve_timeout_seconds(self, request_model: ExecutionRequest) -> float:
        model_timeout = request_model.step.model.timeout_seconds
        if model_timeout and model_timeout > 0:
            return float(model_timeout)
        return self._default_timeout_seconds

    def _post_stream(
        self,
        path: str,
        payload: dict[str, object],
        *,
        timeout_seconds: float,
    ) -> Iterator[str]:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        with self._http_client.stream(
            "POST",
            f"{self._base_url}{path}",
            json=payload,
            headers=headers,
            timeout=timeout_seconds,
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line.startswith("data: "):
                    yield line[6:]

    def _post_json(
        self,
        path: str,
        payload: dict[str, object],
        *,
        timeout_seconds: float,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, object]:
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        if extra_headers:
            headers.update(extra_headers)
        response = self._http_client.post(
            f"{self._base_url}{path}",
            json=payload,
            headers=headers,
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError(f"Expected dict response, got {type(result).__name__}")
        return result

    async def _async_post_json(
        self,
        path: str,
        payload: dict[str, object],
        *,
        timeout_seconds: float,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, object]:
        if type(self)._post_json is not BaseApiAdapter._post_json:
            return await asyncio.to_thread(
                self._post_json,
                path,
                payload,
                timeout_seconds=timeout_seconds,
                extra_headers=extra_headers,
            )
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }
        if extra_headers:
            headers.update(extra_headers)
        response = await self._async_http_client.post(
            f"{self._base_url}{path}",
            json=payload,
            headers=headers,
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError(f"Expected dict response, got {type(result).__name__}")
        return result

    def _extract_output_text(self, payload: dict[str, object]) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError(f"Missing choices in {self._provider_label} response.")
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise ValueError(f"Invalid choice payload from {self._provider_label}.")
        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise ValueError(f"Missing message payload from {self._provider_label}.")
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        raise ValueError(f"Missing content in {self._provider_label} response.")

    def _failure(
        self,
        model_id: str,
        model_display_name: str,
        failure_code: FailureCode,
        message: str,
    ) -> ExecutionResult:
        return ExecutionResult(
            adapter_name=self.name,
            model_id=model_id,
            model_display_name=model_display_name,
            execution_mode=ExecutionMode.API,
            status=StepStatus.FAILED,
            failure_code=failure_code,
            failure_message=message,
            details={"provider": self._provider_label.lower()},
        )

    def healthcheck(self) -> dict[str, object]:
        if not self._api_key:
            return {
                "status": "degraded",
                "adapter_name": self.name,
                "provider": self._provider_label.lower(),
                "configured": False,
            }
        return {
            "status": "ok",
            "adapter_name": self.name,
            "provider": self._provider_label.lower(),
            "configured": True,
            "base_url": self._base_url,
            "default_timeout_seconds": self._default_timeout_seconds,
            "max_retries": self._max_retries,
            "retry_backoff_seconds": self._retry_backoff_seconds,
        }
