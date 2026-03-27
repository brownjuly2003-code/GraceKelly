from __future__ import annotations

from importlib import import_module

__all__ = [
    "ExecutionAdapter",
    "ExecutionBackend",
    "ExecutionBatchResult",
    "ExecutionPlan",
    "ExecutionRequest",
    "ExecutionResult",
    "ExecutionRouter",
    "ExecutionStep",
    "FailureCode",
    "ModelSpec",
    "OrchestratorService",
    "build_execution_plan",
    "list_models",
    "models_equivalent",
    "resolve_model",
]

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "ExecutionAdapter": ("gracekelly.core.contracts", "ExecutionAdapter"),
    "ExecutionBackend": ("gracekelly.core.contracts", "ExecutionBackend"),
    "ExecutionBatchResult": ("gracekelly.core.contracts", "ExecutionBatchResult"),
    "ExecutionPlan": ("gracekelly.core.contracts", "ExecutionPlan"),
    "ExecutionRequest": ("gracekelly.core.contracts", "ExecutionRequest"),
    "ExecutionResult": ("gracekelly.core.contracts", "ExecutionResult"),
    "ExecutionRouter": ("gracekelly.core.router", "ExecutionRouter"),
    "ExecutionStep": ("gracekelly.core.contracts", "ExecutionStep"),
    "FailureCode": ("gracekelly.core.contracts", "FailureCode"),
    "ModelSpec": ("gracekelly.core.models", "ModelSpec"),
    "OrchestratorService": ("gracekelly.core.orchestrator", "OrchestratorService"),
    "build_execution_plan": ("gracekelly.core.planning", "build_execution_plan"),
    "list_models": ("gracekelly.core.models", "list_models"),
    "models_equivalent": ("gracekelly.core.models", "models_equivalent"),
    "resolve_model": ("gracekelly.core.models", "resolve_model"),
}


def __getattr__(name: str) -> object:
    try:
        module_name, attr_name = _LAZY_EXPORTS[name]
    except KeyError as exc:  # pragma: no cover
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    module = import_module(module_name)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
