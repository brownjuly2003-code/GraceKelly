from __future__ import annotations

from fastapi import APIRouter

from gracekelly.core.models import list_models
from gracekelly.schemas import ModelCatalogItem

router = APIRouter(prefix="/api/v1", tags=["models"])


@router.get("/models", response_model=list[ModelCatalogItem])
async def models() -> list[ModelCatalogItem]:
    return [
        ModelCatalogItem(
            id=spec.id,
            display_name=spec.display_name,
            aliases=list(spec.aliases),
            reasoning_capable=spec.reasoning_capable,
        )
        for spec in list_models()
    ]