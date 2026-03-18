from __future__ import annotations

from gracekelly.adapters.api.base import BaseApiAdapter


class MistralApiAdapter(BaseApiAdapter):
    name = "api.mistral"

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str,
        timeout_seconds: float = 30.0,
        max_retries: int = 0,
        retry_backoff_seconds: float = 1.0,
    ) -> None:
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            provider_label="Mistral",
            max_retries=max_retries,
            retry_backoff_seconds=retry_backoff_seconds,
        )
