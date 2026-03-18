from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Query, Request

from gracekelly.core.contracts import ExecutionMode, FailureCode, TaskStatus
from gracekelly.core.models import resolve_model
from gracekelly.core.orchestrator import StorageUnavailableError
from gracekelly.logging_utils import log_message
from gracekelly.schemas import ModelView, OrchestrateRequest, OrchestrateResponse, TaskListItem, TaskView

router = APIRouter(prefix="/api/v1", tags=["orchestration"])
logger = logging.getLogger(__name__)


def _storage_error_detail(exc: StorageUnavailableError) -> dict[str, str]:
    return {
        "code": FailureCode.STORAGE_FAILED.value,
        "message": str(exc),
    }


def _requested_models_from_request(payload: OrchestrateRequest) -> list[ModelView]:
    return [
        ModelView(id=model.id, display_name=model.display_name)
        for model in (resolve_model(item) for item in payload.requested_model_names())
    ]


def _load_task_list_items(
    service,
    *,
    limit: int,
    status: TaskStatus | None,
    execution_mode: ExecutionMode | None,
    dry_run: bool | None,
    failure_code: FailureCode | None,
) -> list[TaskListItem]:
    tasks = service.list_recent_tasks(
        limit,
        status=status,
        execution_mode=execution_mode,
        dry_run=dry_run,
        failure_code=failure_code,
    )
    return [
        TaskListItem.from_task(
            task,
            service.list_task_steps(task.task_id),
            service.list_task_events(task.task_id),
        )
        for task in tasks
    ]


def _load_task_view(service, task_id: str) -> TaskView:
    task = service.get_task(task_id)
    steps = service.list_task_steps(task_id)
    events = service.list_task_events(task_id)
    return TaskView.from_task(task, steps, events)


@router.post("/orchestrate", response_model=OrchestrateResponse, status_code=202)
async def orchestrate(payload: OrchestrateRequest, request: Request) -> OrchestrateResponse:
    service = request.app.state.orchestrator_service
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
            )
        )
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except NotImplementedError as exc:
        logger.warning(
            log_message(
                "orchestrate.rejected",
                code="not_implemented",
                dry_run=payload.dry_run,
                message=str(exc),
            )
        )
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    logger.info(
        log_message(
            "orchestrate.accepted",
            task_id=snapshot.task.task_id,
            status=snapshot.task.status,
            execution_mode=snapshot.task.execution_mode,
            adapter_hint=snapshot.task.adapter_hint,
            dry_run=snapshot.task.dry_run,
            model_count=snapshot.task.model_count,
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
) -> list[TaskListItem]:
    service = request.app.state.orchestrator_service
    try:
        items = await asyncio.to_thread(
            _load_task_list_items,
            service,
            limit=limit,
            status=status,
            execution_mode=execution_mode,
            dry_run=dry_run,
            failure_code=failure_code,
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


@router.get("/tasks/{task_id}", response_model=TaskView)
async def get_task(task_id: str, request: Request) -> TaskView:
    service = request.app.state.orchestrator_service
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
