from __future__ import annotations

import time

from fastapi import APIRouter, Request
from pydantic import BaseModel

from gracekelly.app_state import get_app_state

router = APIRouter(prefix="/api/v1", tags=["health"])
_start_time = time.time()


class AdapterStatus(BaseModel):
    name: str
    status: str


class EmbeddingsStatus(BaseModel):
    status: str
    cache_size: int


class DetailedHealthResponse(BaseModel):
    status: str
    uptime_seconds: int
    adapters: list[AdapterStatus]
    embeddings: EmbeddingsStatus
    total_adapters: int


@router.get("/health/detailed", response_model=DetailedHealthResponse)
def health_detailed(request: Request) -> DetailedHealthResponse:
    state = get_app_state(request)
    api_adapters = state.api_adapters
    embeddings_client = state.embeddings_client

    adapter_statuses: list[AdapterStatus] = []
    for name, adapter in api_adapters.items():
        adapter_statuses.append(AdapterStatus(
            name=name,
            status="ok" if getattr(adapter, "has_api_key", False) else "no_key",
        ))

    embed_status = EmbeddingsStatus(status="unavailable", cache_size=0)
    if embeddings_client is not None:
        embed_status = EmbeddingsStatus(
            status="ok" if embeddings_client.has_api_key else "no_key",
            cache_size=embeddings_client.cache_size(),
        )

    all_ok = all(a.status == "ok" for a in adapter_statuses)
    overall = "healthy" if all_ok and embed_status.status == "ok" else "degraded"

    return DetailedHealthResponse(
        status=overall,
        uptime_seconds=int(time.time() - _start_time),
        adapters=adapter_statuses,
        embeddings=embed_status,
        total_adapters=len(adapter_statuses),
    )
