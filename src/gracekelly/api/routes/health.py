from __future__ import annotations

from fastapi import APIRouter, Request

from gracekelly import __version__
from gracekelly.core.readiness import build_readiness_report

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    profile = request.app.state.execution_profile
    repository = request.app.state.task_repository
    readiness = build_readiness_report(
        environment=settings.env,
        profile=profile,
        repository=repository,
        adapters=request.app.state.adapter_registry,
    )
    return {
        "status": readiness["status"],
        "service": "gracekelly",
        "version": __version__,
        "environment": settings.env,
        "storage_backend": repository.backend_name,
    }


@router.get("/api/v1/readiness")
async def readiness(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    profile = request.app.state.execution_profile
    repository = request.app.state.task_repository
    return build_readiness_report(
        environment=settings.env,
        profile=profile,
        repository=repository,
        adapters=request.app.state.adapter_registry,
    )
