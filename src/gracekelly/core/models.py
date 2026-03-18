from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModelSpec:
    id: str
    display_name: str
    aliases: tuple[str, ...]
    adapter_kind: str
    provider: str
    provider_model_id: str
    timeout_seconds: int
    expected_latency_class: str
    concurrency_limit: int
    reasoning_capable: bool = False

    def normalized_names(self) -> set[str]:
        names = {self.id, self.display_name, *self.aliases}
        return {normalize_model_name(name) for name in names}


def normalize_model_name(value: str) -> str:
    normalized = value.lower().strip()
    normalized = normalized.replace(".", " ")
    normalized = normalized.replace("-", " ")
    normalized = normalized.replace("_", " ")
    normalized = normalized.replace(" thinking", "")
    normalized = normalized.replace(" with reasoning", "")
    return " ".join(normalized.split())


MODEL_SPECS: tuple[ModelSpec, ...] = (
    ModelSpec(
        id="best",
        display_name="Best",
        aliases=("Best",),
        adapter_kind="browser",
        provider="perplexity",
        provider_model_id="Best",
        timeout_seconds=60,
        expected_latency_class="slow",
        concurrency_limit=1,
        reasoning_capable=True,
    ),
    ModelSpec(
        id="sonar",
        display_name="Sonar",
        aliases=("Sonar",),
        adapter_kind="browser",
        provider="perplexity",
        provider_model_id="Sonar",
        timeout_seconds=60,
        expected_latency_class="slow",
        concurrency_limit=1,
        reasoning_capable=True,
    ),
    ModelSpec(
        id="claude-sonnet-4-6",
        display_name="Claude Sonnet 4.6",
        aliases=("Claude Sonnet 4.6", "Claude 4.6", "Claude Sonnet"),
        adapter_kind="browser",
        provider="perplexity",
        provider_model_id="Claude Sonnet 4.6",
        timeout_seconds=60,
        expected_latency_class="slow",
        concurrency_limit=1,
        reasoning_capable=True,
    ),
    ModelSpec(
        id="gpt-5-4",
        display_name="GPT-5.4",
        aliases=("GPT-5.4", "GPT 5.4", "GPT-5"),
        adapter_kind="browser",
        provider="perplexity",
        provider_model_id="GPT-5.4",
        timeout_seconds=60,
        expected_latency_class="slow",
        concurrency_limit=1,
        reasoning_capable=True,
    ),
    ModelSpec(
        id="gemini-3-1-pro",
        display_name="Gemini 3.1 Pro",
        aliases=("Gemini 3.1 Pro", "Gemini Pro 3.1", "Gemini Pro"),
        adapter_kind="browser",
        provider="perplexity",
        provider_model_id="Gemini 3.1 Pro",
        timeout_seconds=60,
        expected_latency_class="slow",
        concurrency_limit=1,
        reasoning_capable=True,
    ),
    ModelSpec(
        id="kimi-k2-5",
        display_name="Kimi K2.5",
        aliases=("Kimi K2.5", "Kimi K2", "Kimi", "Kimi K2 Thinking"),
        adapter_kind="browser",
        provider="perplexity",
        provider_model_id="Kimi K2.5",
        timeout_seconds=60,
        expected_latency_class="slow",
        concurrency_limit=1,
        reasoning_capable=True,
    ),
    ModelSpec(
        id="claude-opus-4-6",
        display_name="Claude Opus 4.6",
        aliases=("Claude Opus 4.6", "Claude Opus"),
        adapter_kind="browser",
        provider="perplexity",
        provider_model_id="Claude Opus 4.6",
        timeout_seconds=60,
        expected_latency_class="slow",
        concurrency_limit=1,
        reasoning_capable=True,
    ),
    ModelSpec(
        id="thinking",
        display_name="Thinking",
        aliases=("Thinking",),
        adapter_kind="browser",
        provider="perplexity",
        provider_model_id="Thinking",
        timeout_seconds=120,
        expected_latency_class="slow",
        concurrency_limit=1,
        reasoning_capable=True,
    ),
    ModelSpec(
        id="max",
        display_name="Max",
        aliases=("Max",),
        adapter_kind="browser",
        provider="perplexity",
        provider_model_id="Max",
        timeout_seconds=60,
        expected_latency_class="slow",
        concurrency_limit=1,
        reasoning_capable=True,
    ),
    ModelSpec(
        id="nemotron-3-super",
        display_name="Nemotron 3 Super",
        aliases=("Nemotron 3 Super", "Nemotron 3"),
        adapter_kind="browser",
        provider="perplexity",
        provider_model_id="Nemotron 3 Super",
        timeout_seconds=60,
        expected_latency_class="slow",
        concurrency_limit=1,
        reasoning_capable=True,
    ),
    ModelSpec(
        id="mistral-small",
        display_name="Mistral Small",
        aliases=("Mistral Small", "Mistral", "Mistral API"),
        adapter_kind="api",
        provider="mistral",
        provider_model_id="mistral-small-latest",
        timeout_seconds=30,
        expected_latency_class="medium",
        concurrency_limit=4,
        reasoning_capable=False,
    ),
    ModelSpec(
        id="gpt-5-4-api",
        display_name="GPT-5.4 API",
        aliases=("GPT-5.4 API", "GPT 5.4 API", "OpenAI GPT-5.4"),
        adapter_kind="api",
        provider="openai",
        provider_model_id="gpt-5.4",
        timeout_seconds=60,
        expected_latency_class="slow",
        concurrency_limit=4,
        reasoning_capable=True,
    ),
)


def list_models() -> tuple[ModelSpec, ...]:
    return MODEL_SPECS


def resolve_model(value: str) -> ModelSpec:
    normalized = normalize_model_name(value)
    for spec in MODEL_SPECS:
        if normalized in spec.normalized_names():
            return spec
    raise ValueError(f"Unsupported model: {value}")


def models_equivalent(left: str, right: str) -> bool:
    try:
        return resolve_model(left).id == resolve_model(right).id
    except ValueError:
        return False
