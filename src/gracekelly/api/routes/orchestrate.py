from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Query, Request

from gracekelly.core.contracts import ExecutionMode, FailureCode, TaskStatus
from gracekelly.core.models import resolve_model
from gracekelly.core.orchestrator import StorageUnavailableError
from gracekelly.schemas import ModelView, OrchestrateRequest, OrchestrateResponse, TaskListItem, TaskView

router = APIRouter(prefix="/api/v1", tags=["orchestration"])


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
    try:
        snapshot = await asyncio.to_thread(service.submit_snapshot, payload)
    except StorageUnavailableError as exc:
        raise HTTPException(status_code=503, detail=_storage_error_detail(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
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
        return await asyncio.to_thread(
            _load_task_list_items,
            service,
            limit=limit,
            status=status,
            execution_mode=execution_mode,
            dry_run=dry_run,
            failure_code=failure_code,
        )
    except StorageUnavailableError as exc:
        raise HTTPException(status_code=503, detail=_storage_error_detail(exc)) from exc


@router.get("/tasks/{task_id}", response_model=TaskView)
async def get_task(task_id: str, request: Request) -> TaskView:
    service = request.app.state.orchestrator_service
    try:
        return await asyncio.to_thread(_load_task_view, service, task_id)
    except StorageUnavailableError as exc:
        raise HTTPException(status_code=503, detail=_storage_error_detail(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc
