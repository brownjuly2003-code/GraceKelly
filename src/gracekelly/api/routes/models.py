from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Request

from gracekelly.core.models import list_models, models_equivalent
from gracekelly.schemas import ModelCatalogItem

router = APIRouter(prefix="/api/v1", tags=["models"])


def _browser_menu_observation(browser_adapter: object | None) -> tuple[list[str], datetime | None, str | None]:
    if browser_adapter is None:
        return [], None, None
    healthcheck = getattr(browser_adapter, "healthcheck", None)
    if not callable(healthcheck):
        return [], None, None
    payload = healthcheck()
    if not isinstance(payload, dict):
        return [], None, None
    automation = payload.get("automation")
    if not isinstance(automation, dict):
        return [], None, None
    observed = automation.get("observed_model_menu")
    if not isinstance(observed, list):
        return [], None, None
    labels = [str(item).strip() for item in observed if str(item).strip()]
    checked_at = automation.get("observed_model_menu_at")
    checked_at = checked_at if isinstance(checked_at, datetime) else None
    source = automation.get("observed_model_menu_source")
    source = source if isinstance(source, str) else None
    return labels, checked_at, source


def _is_observed_browser_model_available(provider_model_id: str, observed_labels: list[str]) -> bool:
    return any(
        observed_label == provider_model_id or models_equivalent(provider_model_id, observed_label)
        for observed_label in observed_labels
    )


def _model_catalog_item(
    spec,
    *,
    observed_browser_labels: list[str],
    observed_browser_checked_at: datetime | None,
    observed_browser_source: str | None,
) -> ModelCatalogItem:
    available: bool | None = None
    availability_status = "static"
    availability_checked_at: datetime | None = None
    availability_source: str | None = None
    if spec.adapter_kind == "browser":
        availability_checked_at = observed_browser_checked_at
        availability_source = observed_browser_source
        if observed_browser_labels:
            available = _is_observed_browser_model_available(spec.provider_model_id, observed_browser_labels)
            availability_status = "observed_available" if available else "observed_unavailable"
        else:
            availability_status = "unknown"

    return ModelCatalogItem(
        id=spec.id,
        display_name=spec.display_name,
        aliases=list(spec.aliases),
        adapter_kind=spec.adapter_kind,
        provider=spec.provider,
        reasoning_capable=spec.reasoning_capable,
        timeout_seconds=spec.timeout_seconds,
        expected_latency_class=spec.expected_latency_class,
        concurrency_limit=spec.concurrency_limit,
        available=available,
        availability_status=availability_status,
        availability_checked_at=availability_checked_at,
        availability_source=availability_source,
    )


@router.get("/models", response_model=list[ModelCatalogItem])
async def models(request: Request) -> list[ModelCatalogItem]:
    observed_browser_labels, observed_browser_checked_at, observed_browser_source = _browser_menu_observation(
        getattr(request.app.state, "browser_adapter", None)
    )
    return [
        _model_catalog_item(
            spec,
            observed_browser_labels=observed_browser_labels,
            observed_browser_checked_at=observed_browser_checked_at,
            observed_browser_source=observed_browser_source,
        )
        for spec in list_models()
    ]
