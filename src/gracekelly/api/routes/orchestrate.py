from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Path, Query, Request, Response

from gracekelly.app_state import get_app_state
from gracekelly.core.contracts import ExecutionMode, FailureCode, TaskStatus
from gracekelly.core.models import resolve_model
from gracekelly.core.orchestrator import OrchestratorService, StorageUnavailableError
from gracekelly.logging_utils import log_message, trace_id_from_metadata
from gracekelly.schemas import ModelView, OrchestrateRequest, OrchestrateResponse, TaskListItem, TaskView
from gracekelly.storage.base import TaskEventRecord, TaskRecord, TaskStepRecord

router = APIRouter(prefix="/api/v1", tags=["orchestration"])
logger = logging.getLogger(__name__)


_SAFE_VALIDATION_PREFIXES = (
    "Unsupported model:",
    "Unsupported merge strategy:",
    "Unknown execution profile:",
    "Duplicate model request",
    "Duplicate requested model",
    "Quorum",
    "Cannot use",
    "Model",
    "Metadata",
    "merge_strategy=",
    "reasoning=",
)


def _sanitize_validation_error(exc: Exception) -> str:
    message = str(exc)
    for prefix in _SAFE_VALIDATION_PREFIXES:
        if message.startswith(prefix):
            return message
    return "Invalid request parameters."


def _storage_error_detail(exc: StorageUnavailableError) -> dict[str, str]:
    return {
        "code": FailureCode.STORAGE_FAILED.value,
        "message": f"Storage is temporarily unavailable (operation: {exc.operation}).",
    }


def _requested_models_from_request(payload: OrchestrateRequest) -> list[ModelView]:
    return [
        ModelView(id=model.id, display_name=model.display_name)
        for model in (resolve_model(item) for item in payload.requested_model_names())
    ]


def _parse_before_cursor(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _load_task_list_items(
    service: OrchestratorService,
    *,
    limit: int,
    status: TaskStatus | None,
    execution_mode: ExecutionMode | None,
    dry_run: bool | None,
    failure_code: FailureCode | None,
    before: datetime | None = None,
) -> list[TaskListItem]:
    tasks = service.list_recent_tasks(
        limit,
        status=status,
        execution_mode=execution_mode,
        dry_run=dry_run,
        failure_code=failure_code,
        before=before,
    )
    if not tasks:
        return []
    task_ids = [task.task_id for task in tasks]
    steps_by_task = service.list_steps_batch(task_ids)
    events_by_task = service.list_events_batch(task_ids)
    return [
        TaskListItem.from_task(
            task,
            steps_by_task.get(task.task_id, []),
            events_by_task.get(task.task_id, []),
        )
        for task in tasks
    ]


def _load_task_view(service: OrchestratorService, task_id: str) -> TaskView:
    task = service.get_task(task_id)
    steps = service.list_task_steps(task_id)
    events = service.list_task_events(task_id)
    return TaskView.from_task(task, steps, events)


@router.post("/orchestrate", response_model=OrchestrateResponse, status_code=202)
async def orchestrate(payload: OrchestrateRequest, request: Request, response: Response) -> OrchestrateResponse:
    service = get_app_state(request).orchestrator_service
    trace_id = trace_id_from_metadata(payload.metadata)
    if trace_id:
        response.headers["x-trace-id"] = trace_id
    logger.info(
        log_message(
            "orchestrate.request",
            dry_run=payload.dry_run,
            reasoning=payload.reasoning,
            model_count=len(payload.requested_model_names()),
            quorum=payload.quorum,
            merge_strategy=payload.merge_strategy,
            adapter_hint=payload.adapter_hint,
            execution_mode="dry-run" if payload.dry_run else "live",
            prompt_length=len(payload.prompt),
            trace_id=trace_id,
        )
    )
    try:
        snapshot = await asyncio.to_thread(service.submit_snapshot, payload)
    except StorageUnavailableError as exc:
        logger.warning(
            log_message(
                "orchestrate.storage_failed",
                operation=exc.operation,
                dry_run=payload.dry_run,
                model_count=len(payload.requested_model_names()),
                message=str(exc),
                trace_id=trace_id,
            )
        )
        raise HTTPException(status_code=503, detail=_storage_error_detail(exc)) from exc
    except ValueError as exc:
        logger.warning(
            log_message(
                "orchestrate.rejected",
                code="validation_error",
                dry_run=payload.dry_run,
                message=str(exc),
                trace_id=trace_id,
            )
        )
        raise HTTPException(status_code=422, detail=_sanitize_validation_error(exc)) from exc
    except NotImplementedError as exc:
        logger.warning(
            log_message(
                "orchestrate.rejected",
                code="not_implemented",
                dry_run=payload.dry_run,
                message=str(exc),
                trace_id=trace_id,
            )
        )
        raise HTTPException(status_code=501, detail="Requested capability is not available.") from exc
    logger.info(
        log_message(
            "orchestrate.accepted",
            task_id=snapshot.task.task_id,
            status=snapshot.task.status,
            execution_mode=snapshot.task.execution_mode,
            adapter_hint=snapshot.task.adapter_hint,
            dry_run=snapshot.task.dry_run,
            model_count=snapshot.task.model_count,
            trace_id=trace_id,
        )
    )
    return OrchestrateResponse.from_task(
        snapshot.task,
        snapshot.steps,
        [],
        requested_models_override=_requested_models_from_request(payload),
    )


@router.get("/tasks", response_model=list[TaskListItem])
async def list_tasks(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    status: TaskStatus | None = Query(default=None),
    execution_mode: ExecutionMode | None = Query(default=None),
    dry_run: bool | None = Query(default=None),
    failure_code: FailureCode | None = Query(default=None),
    before: str | None = Query(default=None, description="Cursor: accepted_at ISO timestamp for pagination"),
) -> list[TaskListItem]:
    service = get_app_state(request).orchestrator_service
    before_dt = _parse_before_cursor(before)
    try:
        items = await asyncio.to_thread(
            _load_task_list_items,
            service,
            limit=limit,
            status=status,
            execution_mode=execution_mode,
            dry_run=dry_run,
            failure_code=failure_code,
            before=before_dt,
        )
        logger.info(
            log_message(
                "tasks.list",
                limit=limit,
                status=status,
                execution_mode=execution_mode,
                dry_run=dry_run,
                failure_code=failure_code,
                result_count=len(items),
            )
        )
        return items
    except StorageUnavailableError as exc:
        logger.warning(
            log_message(
                "tasks.list.storage_failed",
                limit=limit,
                status=status,
                execution_mode=execution_mode,
                dry_run=dry_run,
                failure_code=failure_code,
                operation=exc.operation,
                message=str(exc),
            )
        )
        raise HTTPException(status_code=503, detail=_storage_error_detail(exc)) from exc


_UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"


@router.get("/tasks/{task_id}", response_model=TaskView)
async def get_task(
    request: Request,
    task_id: str = Path(pattern=_UUID_PATTERN),
) -> TaskView:
    service = get_app_state(request).orchestrator_service
    try:
        view = await asyncio.to_thread(_load_task_view, service, task_id)
        logger.info(
            log_message(
                "task.get",
                task_id=task_id,
                status=view.status,
                step_count=len(view.steps),
                event_count=len(view.events),
                execution_mode=view.execution_mode,
            )
        )
        return view
    except StorageUnavailableError as exc:
        logger.warning(
            log_message(
                "task.get.storage_failed",
                task_id=task_id,
                operation=exc.operation,
                message=str(exc),
            )
        )
        raise HTTPException(status_code=503, detail=_storage_error_detail(exc)) from exc
    except KeyError as exc:
        logger.warning(log_message("task.get.not_found", task_id=task_id))
        raise HTTPException(status_code=404, detail="Task not found") from exc


@router.post("/tasks/{task_id}/retry", response_model=OrchestrateResponse, status_code=202)
async def retry_task(
    request: Request,
    task_id: str = Path(pattern=_UUID_PATTERN),
) -> OrchestrateResponse:
    service = get_app_state(request).orchestrator_service
    try:
        original = await asyncio.to_thread(service.get_task, task_id)
        original_steps = await asyncio.to_thread(service.list_task_steps, task_id)
        original_events = await asyncio.to_thread(service.list_task_events, task_id)
    except StorageUnavailableError as exc:
        raise HTTPException(status_code=503, detail=_storage_error_detail(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc

    if original.status not in (TaskStatus.FAILED, TaskStatus.CANCELLED):
        raise HTTPException(
            status_code=409,
            detail=f"Only failed or cancelled tasks can be retried. Current status: {original.status.value}",
        )

    retry_request = _build_retry_request(original, original_steps, original_events)
    logger.info(
        log_message(
            "task.retry.requested",
            original_task_id=task_id,
            model_count=len(retry_request.requested_model_names()),
        )
    )
    try:
        snapshot = await asyncio.to_thread(
            service.submit_snapshot, retry_request, retry_of_task_id=task_id
        )
    except StorageUnavailableError as exc:
        raise HTTPException(status_code=503, detail=_storage_error_detail(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=_sanitize_validation_error(exc)) from exc

    logger.info(
        log_message(
            "task.retry.accepted",
            original_task_id=task_id,
            retry_task_id=snapshot.task.task_id,
        )
    )
    return OrchestrateResponse.from_task(
        snapshot.task,
        snapshot.steps,
        [],
        requested_models_override=_requested_models_from_request(retry_request),
    )


def _build_retry_request(
    task: TaskRecord,
    steps: list[TaskStepRecord],
    events: list[TaskEventRecord],
) -> OrchestrateRequest:
    model_ids = sorted({step.model_id for step in steps}) if steps else []
    if not model_ids:
        model_ids = _models_from_accepted_event(events)
    return OrchestrateRequest(
        prompt=task.prompt,
        models=model_ids if len(model_ids) != 1 else [],
        model=model_ids[0] if len(model_ids) == 1 else None,
        adapter_hint=task.adapter_hint,
        quorum=task.quorum,
        merge_strategy=task.merge_strategy,
        cancel_on_quorum=task.cancel_on_quorum,
        reasoning=task.reasoning,
        metadata=task.metadata,
        dry_run=task.dry_run,
    )


def _models_from_accepted_event(events: list[TaskEventRecord]) -> list[str]:
    for event in events:
        if getattr(event, "event_type", None) == "task.accepted" or (
            hasattr(event, "event_type") and str(event.event_type) == "task.accepted"
        ):
            payload = getattr(event, "payload", {})
            plan = payload.get("execution_plan", {})
            steps = plan.get("steps", [])
            return sorted({step.get("model_id", "") for step in steps if step.get("model_id")})
    return []
