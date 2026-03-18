from __future__ import annotations

from gracekelly.adapters.api.base import BaseApiAdapter


class OpenAICompatibleApiAdapter(BaseApiAdapter):
    name = "api.openai"

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str,
        timeout_seconds: float = 60.0,
    ) -> None:
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            provider_label="OpenAI-compatible",
        )

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
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())
            if parts:
                return "\n".join(parts)
        raise ValueError(f"Missing content in {self._provider_label} response.")
