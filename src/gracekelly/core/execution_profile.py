from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExecutionProfile:
    name: str
    required_adapters: frozenset[str]
    optional_adapters: frozenset[str]
    storage_required: bool = True

    def is_required(self, adapter_name: str) -> bool:
        return adapter_name in self.required_adapters

    def is_known(self, adapter_name: str) -> bool:
        return adapter_name in self.required_adapters or adapter_name in self.optional_adapters


PROFILES: dict[str, ExecutionProfile] = {
    "dry-run": ExecutionProfile(
        name="dry-run",
        required_adapters=frozenset({"dry-run"}),
        optional_adapters=frozenset({"api.mistral", "api.openai", "api.anthropic", "browser.perplexity"}),
    ),
    "api-only": ExecutionProfile(
        name="api-only",
        required_adapters=frozenset({"dry-run", "api.mistral"}),
        optional_adapters=frozenset({"api.openai", "api.anthropic", "browser.perplexity"}),
    ),
    "hybrid": ExecutionProfile(
        name="hybrid",
        required_adapters=frozenset({"dry-run", "api.mistral", "browser.perplexity"}),
        optional_adapters=frozenset({"api.openai", "api.anthropic"}),
    ),
}


def resolve_execution_profile(name: str) -> ExecutionProfile:
    profile = PROFILES.get(name)
    if profile is None:
        raise ValueError(f"Unknown execution profile: {name}")
    return profile
