from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gracekelly.core.execution_profile import ExecutionProfile
from gracekelly.storage.base import TaskRepository


@dataclass(frozen=True, slots=True)
class ComponentStatus:
    name: str
    kind: str
    status: str
    required: bool
    details: dict[str, Any] = field(default_factory=dict)


def build_readiness_report(
    *,
    environment: str,
    profile: ExecutionProfile,
    repository: TaskRepository,
    adapters: dict[str, object],
    execution_router: object | None = None,
) -> dict[str, Any]:
    components = [storage_component_status(repository, required=profile.storage_required)]
    if execution_router is not None:
        components.append(execution_component_status(execution_router))
    components.extend(
        adapter_component_status(name, adapter, required=profile.is_required(name))
        for name, adapter in adapters.items()
        if profile.is_known(name)
    )

    overall_status = "ok"
    required_components = [item for item in components if item["required"]]
    if any(item["status"] == "failed" for item in required_components):
        overall_status = "failed"
    elif any(item["status"] == "degraded" for item in required_components):
        overall_status = "degraded"

    return {
        "status": overall_status,
        "environment": environment,
        "execution_profile": profile.name,
        "components": components,
    }


def storage_component_status(repository: TaskRepository, *, required: bool) -> dict[str, Any]:
    health = repository.healthcheck()
    schema = repository.schema_report()
    status = health.get("status", "unknown")
    schema_status = schema.get("status", "unknown")
    if "failed" in {status, schema_status}:
        status = "failed"
    elif "degraded" in {status, schema_status}:
        status = "degraded"
    details = dict(health)
    details["schema"] = schema
    return {
        "name": repository.backend_name,
        "kind": "storage",
        "status": status,
        "required": required,
        "details": details,
    }


def execution_component_status(execution_router: object) -> dict[str, Any]:
    if hasattr(execution_router, "healthcheck"):
        raw = execution_router.healthcheck()
    else:
        raw = {"status": "unknown"}
    return {
        "name": "execution-router",
        "kind": "execution",
        "status": raw.get("status", "unknown"),
        "required": True,
        "details": raw,
    }


def adapter_component_status(name: str, adapter: object, *, required: bool) -> dict[str, Any]:
    if hasattr(adapter, "healthcheck"):
        raw = adapter.healthcheck()
    else:
        raw = {"status": "unknown"}
    return {
        "name": name,
        "kind": "adapter",
        "status": raw.get("status", "unknown"),
        "required": required,
        "details": raw,
    }
