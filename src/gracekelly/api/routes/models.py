from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request

from gracekelly.app_state import get_app_state
from gracekelly.core.models import ModelCatalogSnapshot, ModelSpec, list_models_for_snapshot, models_equivalent
from gracekelly.schemas import ModelCatalogItem

router = APIRouter(prefix="/api/v1", tags=["models"])


def _browser_menu_observation(
    browser_adapter: object | None,
) -> tuple[list[str], datetime | None, str | None, dict[str, datetime], datetime | None]:
    if browser_adapter is None:
        return [], None, None, {}, None
    healthcheck = getattr(browser_adapter, "healthcheck", None)
    if not callable(healthcheck):
        return [], None, None, {}, None
    payload = healthcheck()
    if not isinstance(payload, dict):
        return [], None, None, {}, None
    automation = payload.get("automation")
    if not isinstance(automation, dict):
        return [], None, None, {}, None
    observed = automation.get("observed_model_menu")
    if not isinstance(observed, list):
        return [], None, None, {}, None
    labels = [str(item).strip() for item in observed if str(item).strip()]
    checked_at = automation.get("observed_model_menu_at")
    checked_at = checked_at if isinstance(checked_at, datetime) else None
    source = automation.get("observed_model_menu_source")
    source = source if isinstance(source, str) else None
    verified_payload = automation.get("verified_model_labels_at")
    verified_labels_at: dict[str, datetime] = {}
    if isinstance(verified_payload, dict):
        for label, value in verified_payload.items():
            if isinstance(label, str) and isinstance(value, datetime):
                verified_labels_at[label] = value
    picker_unavailable_at = automation.get("last_model_picker_unavailable_at")
    picker_unavailable_at = picker_unavailable_at if isinstance(picker_unavailable_at, datetime) else None
    return labels, checked_at, source, verified_labels_at, picker_unavailable_at


def _is_observed_browser_model_available(provider_model_id: str, observed_labels: list[str]) -> bool:
    return any(
        observed_label == provider_model_id or models_equivalent(provider_model_id, observed_label)
        for observed_label in observed_labels
    )


def _last_verified_at(provider_model_id: str, verified_labels_at: dict[str, datetime]) -> datetime | None:
    for observed_label, verified_at in verified_labels_at.items():
        if observed_label == provider_model_id or models_equivalent(provider_model_id, observed_label):
            return verified_at
    return None


def _is_newer(left: datetime | None, right: datetime | None) -> bool:
    return left is not None and (right is None or left > right)


def _model_catalog_item(
    spec: ModelSpec,
    *,
    observed_browser_labels: list[str],
    observed_browser_checked_at: datetime | None,
    observed_browser_source: str | None,
    verified_browser_labels_at: dict[str, datetime],
    last_model_picker_unavailable_at: datetime | None,
) -> ModelCatalogItem:
    available: bool | None = None
    availability_status = "static"
    availability_checked_at: datetime | None = None
    availability_source: str | None = None
    last_verified_at: datetime | None = None
    if spec.adapter_kind == "browser":
        availability_checked_at = observed_browser_checked_at
        availability_source = observed_browser_source
        picker_newer_than_observation = _is_newer(last_model_picker_unavailable_at, observed_browser_checked_at)
        if observed_browser_labels:
            available = _is_observed_browser_model_available(spec.provider_model_id, observed_browser_labels)
            last_verified_at = _last_verified_at(spec.provider_model_id, verified_browser_labels_at)
            if available:
                picker_newer_than_verification = _is_newer(last_model_picker_unavailable_at, last_verified_at)
                if last_verified_at is not None and not picker_newer_than_verification:
                    availability_status = "observed_available"
                else:
                    availability_status = "observed_unverified"
                if picker_newer_than_observation:
                    availability_checked_at = last_model_picker_unavailable_at
            else:
                availability_status = "observed_unavailable"
        else:
            availability_status = "unknown"
            availability_checked_at = last_model_picker_unavailable_at or observed_browser_checked_at

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
        last_verified_at=last_verified_at,
    )


def _catalog_snapshot_from_state(request: Request) -> ModelCatalogSnapshot | None:
    state = get_app_state(request)
    task_repository = getattr(state, "task_repository", None)
    if task_repository is None:
        return None
    getter = getattr(task_repository, "get_model_catalog_snapshot", None)
    if not callable(getter):
        return None
    snapshot = getter()
    return snapshot if isinstance(snapshot, ModelCatalogSnapshot) else None


def _catalog_response_from_snapshot(
    snapshot: ModelCatalogSnapshot,
    *,
    browser_adapter: object | None,
) -> dict[str, object]:
    (
        observed_browser_labels,
        observed_browser_checked_at,
        observed_browser_source,
        verified_browser_labels_at,
        last_model_picker_unavailable_at,
    ) = _browser_menu_observation(browser_adapter)
    if not observed_browser_labels:
        observed_browser_labels = [spec.provider_model_id for spec in snapshot.models]
    if observed_browser_checked_at is None:
        observed_browser_checked_at = snapshot.checked_at
    if observed_browser_source is None:
        observed_browser_source = snapshot.source
    catalog_specs = list_models_for_snapshot(snapshot)
    catalog = [
        _model_catalog_item(
            spec,
            observed_browser_labels=observed_browser_labels,
            observed_browser_checked_at=observed_browser_checked_at,
            observed_browser_source=observed_browser_source,
            verified_browser_labels_at=verified_browser_labels_at,
            last_model_picker_unavailable_at=last_model_picker_unavailable_at,
        )
        for spec in catalog_specs
    ]
    return {
        "last_checked": snapshot.checked_at,
        "source": snapshot.source,
        "models": [item.model_dump() for item in catalog],
    }


@router.get(
    "/models",
    summary="List all registered models",
    description=(
        "Returns the full model catalog with availability status. "
        "Browser-backed models include live observation metadata: "
        "when the model menu was last checked and whether the model label was confirmed."
    ),
    response_description="Model catalog with adapter kind, provider, availability status, and observation timestamps",
)
async def models(request: Request) -> dict[str, object]:
    snapshot = _catalog_snapshot_from_state(request)
    if snapshot is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "model_catalog_unavailable",
                "message": "Browser model catalog is unavailable. No stored snapshot exists yet.",
            },
        )
    return _catalog_response_from_snapshot(
        snapshot,
        browser_adapter=getattr(get_app_state(request), "browser_adapter", None),
    )


@router.post(
    "/models/refresh",
    summary="Refresh model catalog",
    description=(
        "Returns the current model catalog snapshot with a refreshed_at timestamp. "
        "Browser model availability reflects the last Playwright observation. "
        "A live Perplexity query is needed to update the model menu itself."
    ),
)
async def refresh_models(request: Request) -> dict[str, object]:
    snapshot = _catalog_snapshot_from_state(request)
    if snapshot is None:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "model_catalog_unavailable",
                "message": "Browser model catalog is unavailable. No stored snapshot exists yet.",
            },
        )
    payload = _catalog_response_from_snapshot(
        snapshot,
        browser_adapter=getattr(get_app_state(request), "browser_adapter", None),
    )
    payload["refreshed_at"] = datetime.now(UTC).isoformat()
    return payload
