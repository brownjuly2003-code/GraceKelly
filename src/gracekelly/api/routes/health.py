from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request

from gracekelly import __version__
from gracekelly.core.readiness import build_readiness_report

router = APIRouter(tags=["health"])


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


@router.get("/health")
async def health(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    profile = request.app.state.execution_profile
    repository = request.app.state.task_repository
    return await asyncio.to_thread(
        _build_health_summary,
        environment=settings.env,
        storage_backend=repository.backend_name,
        profile=profile,
        repository=repository,
        adapters=request.app.state.adapter_registry,
        execution_router=request.app.state.execution_router,
    )


@router.get("/api/v1/readiness")
async def readiness(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    profile = request.app.state.execution_profile
    repository = request.app.state.task_repository
    return await asyncio.to_thread(
        _build_readiness_payload,
        environment=settings.env,
        profile=profile,
        repository=repository,
        adapters=request.app.state.adapter_registry,
        execution_router=request.app.state.execution_router,
    )
