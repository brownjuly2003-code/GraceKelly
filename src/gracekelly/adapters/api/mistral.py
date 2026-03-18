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
    ) -> None:
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            provider_label="Mistral",
        )
