from __future__ import annotations

from collections.abc import Iterator
from dataclasses import asdict, dataclass
from datetime import datetime


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
    fallback_model_id: str | None = None

    def normalized_names(self) -> set[str]:
        names = {self.id, self.display_name, *self.aliases}
        return {normalize_model_name(name) for name in names}


@dataclass(frozen=True, slots=True)
class ModelCatalogSnapshot:
    checked_at: datetime
    source: str
    models: tuple[ModelSpec, ...]


DEFAULT_BROWSER_CATALOG_KEY = "browser.perplexity"

_BROWSER_COMPATIBILITY_ALIASES: dict[str, tuple[str, ...]] = {
    "best": ("Best",),
    "sonar": ("Sonar",),
    "claude-sonnet-4-6": ("Claude Sonnet 4.6", "Claude 4.6", "Claude Sonnet"),
    "gpt-5-4": ("GPT-5.4", "GPT 5.4", "GPT-5"),
    "gemini-3-1-pro": ("Gemini 3.1 Pro", "Gemini Pro 3.1", "Gemini Pro"),
    "kimi-k2-5": ("Kimi K2.5", "Kimi K2", "Kimi", "Kimi K2 Thinking"),
    "claude-opus-4-6": ("Claude Opus 4.6", "Claude Opus"),
    "max": ("Max",),
    "nemotron-3-super": ("Nemotron 3 Super", "Nemotron 3"),
}

_API_MODEL_SPECS: tuple[ModelSpec, ...] = (
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
    ModelSpec(
        id="claude-sonnet-4-6-api",
        display_name="Claude Sonnet 4.6 API",
        aliases=("Claude Sonnet 4.6 API", "Claude API", "Anthropic Claude"),
        adapter_kind="api",
        provider="anthropic",
        provider_model_id="claude-sonnet-4-6-20250514",
        timeout_seconds=120,
        expected_latency_class="slow",
        concurrency_limit=4,
        reasoning_capable=True,
    ),
)

MODEL_PRICING: dict[str, tuple[float, float]] = {
    "mistral-small": (0.0001, 0.0003),
    "gpt-5-4-api": (0.005, 0.015),
    "claude-sonnet-4-6-api": (0.003, 0.015),
}

_browser_catalog_snapshot: ModelCatalogSnapshot | None = None


def _compose_model_specs(snapshot: ModelCatalogSnapshot | None) -> tuple[ModelSpec, ...]:
    browser_models = snapshot.models if snapshot is not None else ()
    return tuple((*browser_models, *_API_MODEL_SPECS))


class _DynamicModelSpecs(tuple):  # type: ignore[type-arg]
    def __new__(cls) -> _DynamicModelSpecs:
        return super().__new__(cls, ())

    def _items(self) -> tuple[ModelSpec, ...]:
        return list_models_for_snapshot(_browser_catalog_snapshot)

    def __getitem__(self, index: int | slice) -> ModelSpec | tuple[ModelSpec, ...]:  # type: ignore[override]
        return self._items()[index]

    def __iter__(self) -> Iterator[ModelSpec]:
        return iter(self._items())

    def __len__(self) -> int:
        return len(self._items())

    def __repr__(self) -> str:
        return repr(self._items())


MODEL_SPECS: tuple[ModelSpec, ...] = _DynamicModelSpecs()


def normalize_model_name(value: str) -> str:
    normalized = value.lower().strip()
    normalized = normalized.replace(".", " ")
    normalized = normalized.replace("-", " ")
    normalized = normalized.replace("_", " ")
    normalized = normalized.replace(" thinking", "")
    normalized = normalized.replace(" with reasoning", "")
    return " ".join(normalized.split())


def _slugify_model_name(value: str) -> str:
    normalized = normalize_model_name(value)
    return "-".join(part for part in normalized.split(" ") if part)


def _browser_catalog_aliases(canonical_id: str, display_name: str) -> tuple[str, ...]:
    aliases = (display_name, canonical_id, *_BROWSER_COMPATIBILITY_ALIASES.get(canonical_id, ()))
    deduped: list[str] = []
    for alias in aliases:
        if alias and alias not in deduped:
            deduped.append(alias)
    return tuple(deduped)


def build_browser_model_spec(label: str) -> ModelSpec:
    display_name = str(label).strip()
    canonical_id = _slugify_model_name(display_name)
    if not canonical_id:
        raise ValueError(f"Unsupported browser model label: {label!r}")
    fallback_model_id = (
        "claude-sonnet-4-6-api" if canonical_id == "claude-sonnet-4-6"
        else "gpt-5-4-api" if canonical_id == "gpt-5-4"
        else None
    )

    return ModelSpec(
        id=canonical_id,
        display_name=display_name,
        aliases=_browser_catalog_aliases(canonical_id, display_name),
        adapter_kind="browser",
        provider="perplexity",
        provider_model_id=display_name,
        timeout_seconds=60,
        expected_latency_class="fast" if canonical_id == "sonar" else "slow",
        concurrency_limit=1,
        reasoning_capable=canonical_id != "sonar",
        fallback_model_id=fallback_model_id,
    )


def build_browser_catalog(
    labels: tuple[str, ...] | list[str],
    *,
    checked_at: datetime,
    source: str,
) -> ModelCatalogSnapshot:
    seen_ids: set[str] = set()
    models: list[ModelSpec] = []
    for raw_label in labels:
        label = str(raw_label).strip()
        if not label:
            continue
        spec = build_browser_model_spec(label)
        if spec.id in seen_ids:
            continue
        seen_ids.add(spec.id)
        models.append(spec)
    return ModelCatalogSnapshot(
        checked_at=checked_at,
        source=source,
        models=tuple(models),
    )


def install_browser_catalog(snapshot: ModelCatalogSnapshot | None) -> None:
    global _browser_catalog_snapshot
    _browser_catalog_snapshot = snapshot


def clear_browser_catalog() -> None:
    install_browser_catalog(None)


def get_browser_catalog() -> ModelCatalogSnapshot | None:
    return _browser_catalog_snapshot


def serialize_model_spec(spec: ModelSpec) -> dict[str, object]:
    return asdict(spec)


def deserialize_model_spec(payload: dict[str, object]) -> ModelSpec:
    aliases = payload.get("aliases")
    return ModelSpec(
        id=str(payload["id"]),
        display_name=str(payload["display_name"]),
        aliases=tuple(str(item) for item in aliases) if isinstance(aliases, list | tuple) else (),
        adapter_kind=str(payload["adapter_kind"]),
        provider=str(payload["provider"]),
        provider_model_id=str(payload["provider_model_id"]),
        timeout_seconds=int(str(payload["timeout_seconds"])),
        expected_latency_class=str(payload["expected_latency_class"]),
        concurrency_limit=int(str(payload["concurrency_limit"])),
        reasoning_capable=bool(payload.get("reasoning_capable", False)),
        fallback_model_id=(
            str(payload["fallback_model_id"])
            if payload.get("fallback_model_id") is not None
            else None
        ),
    )


def serialize_model_catalog_snapshot(snapshot: ModelCatalogSnapshot) -> dict[str, object]:
    return {
        "checked_at": snapshot.checked_at.isoformat(),
        "source": snapshot.source,
        "models": [serialize_model_spec(spec) for spec in snapshot.models],
    }


def deserialize_model_catalog_snapshot(payload: dict[str, object]) -> ModelCatalogSnapshot:
    models = payload.get("models")
    if not isinstance(models, list):
        raise ValueError("Model catalog payload must include a models list.")
    return ModelCatalogSnapshot(
        checked_at=datetime.fromisoformat(str(payload["checked_at"])),
        source=str(payload["source"]),
        models=tuple(
            deserialize_model_spec(item)
            for item in models
            if isinstance(item, dict)
        ),
    )


def estimate_cost_usd(model_id: str, input_tokens: int | None, output_tokens: int | None) -> float | None:
    pricing = MODEL_PRICING.get(model_id)
    if pricing is None or input_tokens is None or output_tokens is None:
        return None
    input_cost, output_cost = pricing
    return (input_tokens / 1000) * input_cost + (output_tokens / 1000) * output_cost


def list_models() -> tuple[ModelSpec, ...]:
    return MODEL_SPECS


def list_models_for_snapshot(snapshot: ModelCatalogSnapshot | None) -> tuple[ModelSpec, ...]:
    return _compose_model_specs(snapshot)


def _resolve_browser_compatibility_alias(normalized: str) -> str | None:
    for canonical_id, aliases in _BROWSER_COMPATIBILITY_ALIASES.items():
        candidates = (canonical_id, *aliases)
        if any(normalized == normalize_model_name(candidate) for candidate in candidates):
            return canonical_id
    return None


def resolve_model(value: str) -> ModelSpec:
    normalized = normalize_model_name(value)
    for spec in list_models():
        if normalized in spec.normalized_names():
            return spec

    canonical_browser_id = _resolve_browser_compatibility_alias(normalized)
    if canonical_browser_id is not None and _browser_catalog_snapshot is not None:
        for spec in _browser_catalog_snapshot.models:
            if spec.id == canonical_browser_id:
                return spec

    raise ValueError(f"Unsupported model: {value}")


def models_equivalent(left: str, right: str) -> bool:
    try:
        return resolve_model(left).id == resolve_model(right).id
    except ValueError:
        return False
