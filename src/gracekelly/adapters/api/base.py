from __future__ import annotations

import json
import logging
import time
from urllib import error, request

from gracekelly.core.contracts import (
    ExecutionAdapter,
    ExecutionMode,
    ExecutionRequest,
    ExecutionResult,
    FailureCode,
    StepStatus,
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
                return ExecutionResult(
                    adapter_name=self.name,
                    model_id=model.id,
                    model_display_name=model.display_name,
                    execution_mode=ExecutionMode.API,
                    status=StepStatus.COMPLETED,
                    output_text=output_text,
                    details={
                        "provider": self._provider_label.lower(),
                        "provider_model_id": request_model.step.provider_model_id,
                        "timeout_seconds": timeout_seconds,
                        "attempts": attempt,
                    },
                )
            except error.HTTPError as exc:
                last_error = exc
                if exc.code in _RETRYABLE_HTTP_CODES and attempt < attempts:
                    self._sleep_before_retry(attempt)
                    continue
                if exc.code == 429:
                    return self._failure(
                        model.id, model.display_name, FailureCode.RATE_LIMITED,
                        f"{self._provider_label} rate limit reached.",
                    )
                return self._failure(
                    model.id, model.display_name, FailureCode.PROVIDER_UNAVAILABLE,
                    f"{self._provider_label} HTTP error: {exc.code}",
                )
            except (TimeoutError, error.URLError) as exc:
                last_error = exc
                if attempt < attempts:
                    self._sleep_before_retry(attempt)
                    continue
                if isinstance(exc, TimeoutError):
                    return self._failure(
                        model.id, model.display_name, FailureCode.TIMEOUT,
                        f"{self._provider_label} request timed out.",
                    )
                return self._failure(
                    model.id, model.display_name, FailureCode.PROVIDER_UNAVAILABLE,
                    f"{self._provider_label} network error: {exc.reason}",
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

    def _post_json(
        self,
        path: str,
        payload: dict[str, object],
        *,
        timeout_seconds: float,
    ) -> dict[str, object]:
        body = json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            f"{self._base_url}{path}",
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        with request.urlopen(http_request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

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
