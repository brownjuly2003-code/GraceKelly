from __future__ import annotations

import json
from urllib import error, request

from gracekelly.core.contracts import ExecutionAdapter, ExecutionMode, ExecutionRequest, ExecutionResult, FailureCode, StepStatus


class MistralApiAdapter(ExecutionAdapter):
    name = "api.mistral"

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._default_timeout_seconds = timeout_seconds

    def execute(self, request_model: ExecutionRequest) -> ExecutionResult:
        model = request_model.step.model
        timeout_seconds = self._resolve_timeout_seconds(request_model)
        if not self._api_key:
            return self._failure(
                model.id,
                model.display_name,
                FailureCode.PROVIDER_UNAVAILABLE,
                "Mistral API key is not configured.",
            )

        payload = {
            "model": request_model.step.provider_model_id,
            "messages": [
                {
                    "role": "user",
                    "content": request_model.prompt,
                }
            ],
        }

        try:
            response_data = self._post_json(
                "/chat/completions",
                payload,
                timeout_seconds=timeout_seconds,
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
                    "provider": "mistral",
                    "provider_model_id": request_model.step.provider_model_id,
                    "timeout_seconds": timeout_seconds,
                },
            )
        except TimeoutError:
            return self._failure(model.id, model.display_name, FailureCode.TIMEOUT, "Mistral request timed out.")
        except error.HTTPError as exc:
            if exc.code == 429:
                return self._failure(model.id, model.display_name, FailureCode.RATE_LIMITED, "Mistral rate limit reached.")
            return self._failure(
                model.id,
                model.display_name,
                FailureCode.PROVIDER_UNAVAILABLE,
                f"Mistral HTTP error: {exc.code}",
            )
        except error.URLError as exc:
            return self._failure(
                model.id,
                model.display_name,
                FailureCode.PROVIDER_UNAVAILABLE,
                f"Mistral network error: {exc.reason}",
            )
        except Exception as exc:
            return self._failure(
                model.id,
                model.display_name,
                FailureCode.UNKNOWN_ERROR,
                f"Mistral adapter error: {exc}",
            )

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
            raise ValueError("Missing choices in Mistral response.")
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise ValueError("Invalid choice payload from Mistral.")
        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise ValueError("Missing message payload from Mistral.")
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        raise ValueError("Missing content in Mistral response.")

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
            details={"provider": "mistral"},
        )

    def healthcheck(self) -> dict[str, object]:
        if not self._api_key:
            return {
                "status": "degraded",
                "adapter_name": self.name,
                "provider": "mistral",
                "configured": False,
            }
        return {
            "status": "ok",
            "adapter_name": self.name,
            "provider": "mistral",
            "configured": True,
            "base_url": self._base_url,
            "default_timeout_seconds": self._default_timeout_seconds,
        }
