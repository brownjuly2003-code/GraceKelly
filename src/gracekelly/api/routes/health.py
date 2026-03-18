from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from gracekelly import __version__
from gracekelly.core.readiness import build_readiness_report
from gracekelly.logging_utils import log_message

router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


def _build_readiness_payload(
    *,
    environment: str,
    profile,
    repository,
    adapters,
    execution_router,
) -> dict[str, object]:
    return build_readiness_report(
        environment=environment,
        profile=profile,
        repository=repository,
        adapters=adapters,
        execution_router=execution_router,
    )


def _build_health_summary(
    *,
    environment: str,
    storage_backend: str,
    profile,
    repository,
    adapters,
    execution_router,
) -> dict[str, object]:
    readiness = _build_readiness_payload(
        environment=environment,
        profile=profile,
        repository=repository,
        adapters=adapters,
        execution_router=execution_router,
    )
    execution = next(item for item in readiness["components"] if item["kind"] == "execution")
    return {
        "status": readiness["status"],
        "service": "gracekelly",
        "version": __version__,
        "environment": environment,
        "storage_backend": storage_backend,
        "active_model_executions": execution["details"]["active_model_executions"],
        "saturated_models": execution["details"]["saturated_models"],
    }


def _prometheus_value(value: object) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


def _prometheus_labels(labels: dict[str, object] | None = None) -> str:
    if not labels:
        return ""
    items: list[str] = []
    for key, raw in sorted(labels.items()):
        value = str(raw).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')
        items.append(f'{key}="{value}"')
    return "{" + ",".join(items) + "}"


def _emit_help(lines: list[str], name: str, help_text: str, metric_type: str = "gauge") -> None:
    lines.append(f"# HELP {name} {help_text}")
    lines.append(f"# TYPE {name} {metric_type}")


def _emit_gauge(
    lines: list[str],
    name: str,
    value: object,
    *,
    labels: dict[str, object] | None = None,
) -> None:
    lines.append(f"{name}{_prometheus_labels(labels)} {_prometheus_value(value)}")


def _emit_one_hot(
    lines: list[str],
    name: str,
    *,
    label_name: str,
    actual: str,
    allowed: tuple[str, ...],
    labels: dict[str, object] | None = None,
) -> None:
    for candidate in allowed:
        series_labels = dict(labels or {})
        series_labels[label_name] = candidate
        _emit_gauge(lines, name, 1 if candidate == actual else 0, labels=series_labels)


def _build_metrics_payload(
    *,
    environment: str,
    storage_backend: str,
    profile,
    repository,
    adapters,
    execution_router,
) -> str:
    readiness = _build_readiness_payload(
        environment=environment,
        profile=profile,
        repository=repository,
        adapters=adapters,
        execution_router=execution_router,
    )
    storage = next(item for item in readiness["components"] if item["kind"] == "storage")
    execution = next(item for item in readiness["components"] if item["kind"] == "execution")
    lines: list[str] = []

    _emit_help(lines, "gracekelly_build_info", "Static build and runtime identity labels.")
    _emit_gauge(
        lines,
        "gracekelly_build_info",
        1,
        labels={
            "version": __version__,
            "environment": environment,
            "storage_backend": storage_backend,
            "execution_profile": profile.name,
        },
    )

    _emit_help(lines, "gracekelly_readiness_state", "Service readiness state as one-hot status labels.")
    _emit_one_hot(
        lines,
        "gracekelly_readiness_state",
        label_name="status",
        actual=readiness["status"],
        allowed=("ok", "degraded", "failed", "unknown"),
    )

    _emit_help(lines, "gracekelly_component_state", "Readiness component state as one-hot status labels.")
    for component in readiness["components"]:
        _emit_one_hot(
            lines,
            "gracekelly_component_state",
            label_name="status",
            actual=component["status"],
            allowed=("ok", "degraded", "failed", "unknown"),
            labels={
                "name": component["name"],
                "kind": component["kind"],
                "required": str(component["required"]).lower(),
            },
        )

    execution_details = execution["details"]
    _emit_help(lines, "gracekelly_execution_active_model_executions", "Current in-process active model executions.")
    _emit_gauge(
        lines,
        "gracekelly_execution_active_model_executions",
        execution_details["active_model_executions"],
    )

    _emit_help(lines, "gracekelly_execution_model_active", "Current active executions per model.")
    active_by_model = execution_details.get("active_by_model", {})
    for model_id, active in sorted(active_by_model.items()):
        _emit_gauge(lines, "gracekelly_execution_model_active", active, labels={"model_id": model_id})

    _emit_help(lines, "gracekelly_execution_model_limit", "Configured concurrency limit per model.")
    for model_id, limit in sorted(execution_details.get("model_limits", {}).items()):
        _emit_gauge(lines, "gracekelly_execution_model_limit", limit, labels={"model_id": model_id})

    _emit_help(lines, "gracekelly_execution_model_saturated", "Whether a model is currently saturated (1 or 0).")
    saturated_models = set(execution_details.get("saturated_models", []))
    for model_id in sorted(execution_details.get("model_limits", {})):
        _emit_gauge(
            lines,
            "gracekelly_execution_model_saturated",
            1 if model_id in saturated_models else 0,
            labels={"model_id": model_id},
        )

    storage_details = storage["details"]
    if "task_count" in storage_details:
        _emit_help(lines, "gracekelly_storage_task_count", "Current task records visible to the active repository.")
        _emit_gauge(lines, "gracekelly_storage_task_count", storage_details["task_count"])
    if "step_count" in storage_details:
        _emit_help(lines, "gracekelly_storage_step_count", "Current task-step records visible to the active repository.")
        _emit_gauge(lines, "gracekelly_storage_step_count", storage_details["step_count"])
    if "event_count" in storage_details:
        _emit_help(lines, "gracekelly_storage_event_count", "Current task-event records visible to the active repository.")
        _emit_gauge(lines, "gracekelly_storage_event_count", storage_details["event_count"])

    _emit_help(lines, "gracekelly_browser_circuit_breaker_state", "Browser circuit breaker state as one-hot labels.")
    breaker_found = False
    for component in readiness["components"]:
        if component["kind"] != "adapter":
            continue
        breaker = component["details"].get("circuit_breaker")
        if not isinstance(breaker, dict):
            continue
        breaker_found = True
        _emit_one_hot(
            lines,
            "gracekelly_browser_circuit_breaker_state",
            label_name="state",
            actual=str(breaker.get("state", "unknown")),
            allowed=("disabled", "closed", "open", "half-open", "unknown"),
            labels={"adapter_name": component["name"]},
        )
        _emit_gauge(
            lines,
            "gracekelly_browser_circuit_breaker_consecutive_failures",
            breaker.get("consecutive_failures", 0),
            labels={"adapter_name": component["name"]},
        )
        _emit_gauge(
            lines,
            "gracekelly_browser_circuit_breaker_open_count",
            breaker.get("open_count", 0),
            labels={"adapter_name": component["name"]},
        )
        _emit_gauge(
            lines,
            "gracekelly_browser_circuit_breaker_fail_fast_rejections",
            breaker.get("fail_fast_rejections", 0),
            labels={"adapter_name": component["name"]},
        )
    if not breaker_found:
        _emit_one_hot(
            lines,
            "gracekelly_browser_circuit_breaker_state",
            label_name="state",
            actual="disabled",
            allowed=("disabled", "closed", "open", "half-open", "unknown"),
            labels={"adapter_name": "browser.perplexity"},
        )
        _emit_gauge(
            lines,
            "gracekelly_browser_circuit_breaker_consecutive_failures",
            0,
            labels={"adapter_name": "browser.perplexity"},
        )
        _emit_gauge(
            lines,
            "gracekelly_browser_circuit_breaker_open_count",
            0,
            labels={"adapter_name": "browser.perplexity"},
        )
        _emit_gauge(
            lines,
            "gracekelly_browser_circuit_breaker_fail_fast_rejections",
            0,
            labels={"adapter_name": "browser.perplexity"},
        )

    return "\n".join(lines) + "\n"


@router.get("/health")
async def health(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    profile = request.app.state.execution_profile
    repository = request.app.state.task_repository
    payload = await asyncio.to_thread(
        _build_health_summary,
        environment=settings.env,
        storage_backend=repository.backend_name,
        profile=profile,
        repository=repository,
        adapters=request.app.state.adapter_registry,
        execution_router=request.app.state.execution_router,
    )
    if payload["status"] != "ok" or payload["saturated_models"]:
        logger.warning(
            log_message(
                "health.snapshot",
                status=payload["status"],
                storage_backend=payload["storage_backend"],
                active_model_executions=payload["active_model_executions"],
                saturated_models=",".join(payload["saturated_models"]),
            )
        )
    return payload


@router.get("/api/v1/readiness")
async def readiness(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    profile = request.app.state.execution_profile
    repository = request.app.state.task_repository
    payload = await asyncio.to_thread(
        _build_readiness_payload,
        environment=settings.env,
        profile=profile,
        repository=repository,
        adapters=request.app.state.adapter_registry,
        execution_router=request.app.state.execution_router,
    )
    if payload["status"] != "ok":
        logger.warning(
            log_message(
                "readiness.snapshot",
                status=payload["status"],
                component_count=len(payload["components"]),
                execution_profile=payload["execution_profile"],
            )
        )
    return payload


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics(request: Request) -> PlainTextResponse:
    settings = request.app.state.settings
    profile = request.app.state.execution_profile
    repository = request.app.state.task_repository
    payload = await asyncio.to_thread(
        _build_metrics_payload,
        environment=settings.env,
        storage_backend=repository.backend_name,
        profile=profile,
        repository=repository,
        adapters=request.app.state.adapter_registry,
        execution_router=request.app.state.execution_router,
    )
    return PlainTextResponse(payload, media_type="text/plain; version=0.0.4; charset=utf-8")
