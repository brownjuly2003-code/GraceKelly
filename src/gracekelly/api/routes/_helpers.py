from __future__ import annotations

from typing import cast

from gracekelly.app_state import AppState
from gracekelly.core.contracts import ExecutionAdapter, ExecutionBackend
from gracekelly.core.models import ModelSpec


def resolve_execution_adapter(
    state: AppState,
    model_spec: ModelSpec,
    dry_run: bool,
) -> tuple[ExecutionAdapter, ExecutionBackend]:
    backend = (
        ExecutionBackend.BROWSER
        if model_spec.adapter_kind == "browser"
        else ExecutionBackend.API
    )
    if dry_run:
        return cast(ExecutionAdapter, state.dry_run_adapter), backend

    if backend == ExecutionBackend.BROWSER:
        adapter = cast(ExecutionAdapter | None, getattr(state, "browser_adapter", None))
        if adapter is None:
            raise ValueError(f"No browser adapter for provider '{model_spec.provider}'.")
        return adapter, backend

    adapter = state.api_adapters.get(model_spec.provider)
    if adapter is None:
        raise ValueError(f"No API adapter for provider '{model_spec.provider}'.")
    return adapter, backend
