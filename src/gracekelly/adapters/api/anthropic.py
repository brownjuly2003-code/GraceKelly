from __future__ import annotations

import json
from typing import cast
from urllib import request as urllib_request

from gracekelly.adapters.api.base import BaseApiAdapter


class AnthropicApiAdapter(BaseApiAdapter):
    name = "api.anthropic"

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str = "https://api.anthropic.com",
        timeout_seconds: float = 120.0,
        max_retries: int = 0,
        retry_backoff_seconds: float = 1.0,
        anthropic_version: str = "2023-06-01",
    ) -> None:
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            provider_label="Anthropic",
            max_retries=max_retries,
            retry_backoff_seconds=retry_backoff_seconds,
        )
        self._anthropic_version = anthropic_version

    def _post_json(
        self,
        path: str,
        payload: dict[str, object],
        *,
        timeout_seconds: float,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, object]:
        body = json.dumps(payload).encode("utf-8")
        http_request = urllib_request.Request(
            f"{self._base_url}{path}",
            data=body,
            headers={
                "x-api-key": self._api_key or "",
                "anthropic-version": self._anthropic_version,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        with urllib_request.urlopen(http_request, timeout=timeout_seconds) as response:  # nosec B310 — URL is always self._base_url (anthropic.com), never user-controlled
            return cast(dict[str, object], json.loads(response.read().decode("utf-8")))

    def _extract_output_text(self, payload: dict[str, object]) -> str:
        content = payload.get("content")
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = block.get("text")
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())
            if parts:
                return "\n".join(parts)
        raise ValueError(f"Missing content in {self._provider_label} response.")
