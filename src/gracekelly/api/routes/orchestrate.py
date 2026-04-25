from __future__ import annotations

import asyncio
import functools
import io
import json
import logging
from datetime import datetime
from pathlib import Path as FilePath
from typing import cast
from uuid import uuid4

from fastapi import APIRouter, File, Form, HTTPException, Path, Query, Request, Response, UploadFile

from gracekelly.api.error_codes import AUTH_SYNC_HTTP_CODE, AUTH_TASK_FAILURE_CODE
from gracekelly.api.routes._helpers import resolve_effective_dry_run
from gracekelly.app_state import get_app_state
from gracekelly.core.contracts import (
    ATTACHMENT_METADATA_KEY,
    IMAGE_CONTENT_TYPES,
    ExecutionMode,
    FailureCode,
    FileAttachment,
    TaskStatus,
    discard_registered_attachments,
    register_file_attachments,
)
from gracekelly.core.models import resolve_model
from gracekelly.core.orchestrator import OrchestratorService, StorageUnavailableError, SubmissionSnapshot
from gracekelly.logging_utils import log_message, trace_id_from_metadata
from gracekelly.schemas import ModelView, OrchestrateRequest, OrchestrateResponse, TaskListItem, TaskView
from gracekelly.storage.base import TaskEventRecord, TaskRecord, TaskStepRecord

router = APIRouter(prefix="/api/v1", tags=["orchestration"])
logger = logging.getLogger(__name__)

__all__ = ("OrchestrateResponse",)


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

_TEXT_EXTENSIONS = frozenset({
    ".csv",
    ".html",
    ".js",
    ".json",
    ".md",
    ".py",
    ".rst",
    ".toml",
    ".ts",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
})

_IMAGE_CONTENT_TYPES_BY_EXTENSION = {
    ".gif": "image/gif",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


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
    prompt_contains: str | None = None,
) -> list[TaskListItem]:
    tasks = service.list_recent_tasks(
        limit,
        status=status,
        execution_mode=execution_mode,
        dry_run=dry_run,
        failure_code=failure_code,
        before=before,
        prompt_contains=prompt_contains,
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


def _load_task_view(
    service: OrchestratorService,
    task_id: str,
    *,
    events_limit: int | None = None,
    events_offset: int = 0,
) -> TaskView:
    task = service.get_task(task_id)
    steps = service.list_task_steps(task_id)
    events, events_total = service.list_task_events_paginated(
        task_id, limit=events_limit, offset=events_offset
    )
    return TaskView.from_task(task, steps, events, events_total=events_total)


def _render_task_export(task: TaskRecord) -> str:
    lines = [
        "---",
        f"task_id: {task.task_id}",
        f"status: {task.status}",
        f"accepted_at: {task.accepted_at.isoformat()}",
        f"duration_ms: {task.duration_ms}",
        f"model_count: {task.model_count}",
        f"dry_run: {task.dry_run}",
        "---",
        "",
        "## Prompt",
        "",
        task.prompt,
        "",
        "## Output",
        "",
        task.output_text or "_No output returned._",
    ]
    return "\n".join(lines)


def _parse_models_form_value(models: str | None) -> list[str]:
    if models is None:
        return []
    try:
        parsed = json.loads(models)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="Field 'models' must be a JSON array of strings.") from exc
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise HTTPException(status_code=422, detail="Field 'models' must be a JSON array of strings.")
    return parsed


async def _extract_file_content(file: UploadFile) -> tuple[str | None, FileAttachment | None]:
    filename = file.filename or "unknown"
    content_type = file.content_type or ""
    extension = FilePath(filename).suffix.lower()
    data = await file.read()

    if content_type in IMAGE_CONTENT_TYPES or extension in _IMAGE_CONTENT_TYPES_BY_EXTENSION:
        return None, FileAttachment(
            name=filename,
            content_type=content_type or _IMAGE_CONTENT_TYPES_BY_EXTENSION.get(extension, "image/jpeg"),
            data=data,
        )

    if content_type == "application/pdf" or extension == ".pdf":
        try:
            import pypdf
        except ImportError as exc:
            raise HTTPException(
                status_code=422,
                detail="PDF support requires 'pypdf'. Install with: pip install 'gracekelly[pdf]'",
            ) from exc
        try:
            reader = pypdf.PdfReader(io.BytesIO(data))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Cannot extract text from PDF: {filename}") from exc
        return f"[File: {filename}]\n{text}", None

    if extension in _TEXT_EXTENSIONS or content_type.startswith("text/"):
        return f"[File: {filename}]\n{data.decode('utf-8', errors='replace')}", None

    raise HTTPException(
        status_code=422,
        detail=(
            f"Unsupported file type: {content_type or extension}. "
            "Supported: text, PDF, images (jpeg/png/gif/webp)"
        ),
    )


@router.post(
    "/orchestrate",
    response_model=OrchestrateResponse,
    status_code=200,
    summary="Submit a prompt for orchestrated execution",
    description=(
        "Submits a prompt to one or more models according to the specified execution plan. "
        "Supports dry-run, quorum, merge strategies, reasoning mode, and optional trace correlation. "
        "Executes synchronously and returns the final task snapshot for the completed request."
    ),
    response_description="Final task snapshot with execution plan, steps, and terminal status",
    responses={
        422: {"description": "Validation error (unsupported model, invalid merge strategy, quorum conflict)"},
        501: {"description": "Requested capability is not implemented"},
        503: {"description": "Storage temporarily unavailable"},
        504: {"description": "Orchestration timed out (GRACEKELLY_ORCHESTRATE_TIMEOUT_SECONDS exceeded)"},
    },
)
async def orchestrate(payload: OrchestrateRequest, request: Request, response: Response) -> OrchestrateResponse:
    state = get_app_state(request)
    service = state.orchestrator_service
    _timeout = state.settings.orchestrate_timeout_seconds
    effective_dry_run = resolve_effective_dry_run(state, payload.dry_run)
    payload_for_submission = payload.model_copy(update={"dry_run": effective_dry_run})
    trace_id = trace_id_from_metadata(payload.metadata)
    if trace_id:
        response.headers["x-trace-id"] = trace_id
    logger.info(
        log_message(
            "orchestrate.request",
            dry_run=effective_dry_run,
            reasoning=payload.reasoning,
            model_count=len(payload.requested_model_names()),
            quorum=payload.quorum,
            merge_strategy=payload.merge_strategy,
            adapter_hint=payload.adapter_hint,
            execution_mode="dry-run" if effective_dry_run else "live",
            prompt_length=len(payload.prompt),
            trace_id=trace_id,
        )
    )
    try:
        _executor = getattr(state, "browser_executor", None)
        _loop = asyncio.get_running_loop()
        _coro = cast(asyncio.Future[SubmissionSnapshot], _loop.run_in_executor(_executor, service.submit_snapshot, payload_for_submission))
        try:
            snapshot = await (asyncio.wait_for(_coro, timeout=_timeout) if _timeout else _coro)
        except TimeoutError as exc:
            _coro.cancel()

            def _consume_timed_out_submission(_future: asyncio.Future[SubmissionSnapshot]) -> None:
                try:
                    _future.exception()
                except BaseException:
                    return

            _coro.add_done_callback(_consume_timed_out_submission)
            logger.warning(
                log_message(
                    "orchestrate.timeout",
                    timeout_seconds=_timeout,
                    trace_id=trace_id,
                )
            )
            raise HTTPException(status_code=504, detail="Orchestration request timed out.") from exc
        if (
            snapshot.task.status == TaskStatus.FAILED
            and snapshot.task.failure_code is not None
            and snapshot.task.failure_code.value == AUTH_TASK_FAILURE_CODE
        ):
            trace_id = trace_id_from_metadata(snapshot.task.metadata) or trace_id or str(uuid4())
            raise HTTPException(
                status_code=503,
                detail={
                    "code": AUTH_SYNC_HTTP_CODE,
                    "message": snapshot.task.failure_message or "Browser session is not authenticated.",
                    "trace_id": trace_id,
                },
                headers={"x-trace-id": trace_id},
            )
        try:
            requested_models = _requested_models_from_request(payload)
        except ValueError:
            requested_models = [
                ModelView(id=step.model_id, display_name=step.model_display_name)
                for step in snapshot.steps
            ]
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
            requested_models_override=requested_models,
        )
    except StorageUnavailableError as exc:
        logger.warning(
            log_message(
                "orchestrate.storage_failed",
                operation=exc.operation,
                dry_run=effective_dry_run,
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
                dry_run=effective_dry_run,
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
                dry_run=effective_dry_run,
                message=str(exc),
                trace_id=trace_id,
            )
        )
        raise HTTPException(status_code=501, detail="Requested capability is not available.") from exc
    except HTTPException:
        raise
    except Exception as exc:
        trace_id = trace_id or str(uuid4())
        logger.exception(
            log_message(
                "orchestrate.failed",
                dry_run=effective_dry_run,
                model_count=len(payload.requested_model_names()),
                trace_id=trace_id,
            )
        )
        raise HTTPException(
            status_code=500,
            detail={
                "code": FailureCode.UNKNOWN_ERROR.value,
                "message": "Internal server error.",
                "trace_id": trace_id,
            },
            headers={"x-trace-id": trace_id},
        ) from exc


@router.post(
    "/orchestrate/upload",
    response_model=OrchestrateResponse,
    status_code=200,
    summary="Submit a prompt with file uploads for orchestrated execution",
)
async def orchestrate_with_files(
    request: Request,
    response: Response,
    prompt: str = Form(...),
    model: str | None = Form(default=None),
    models: str | None = Form(default=None),
    session_id: str | None = Form(default=None),
    dry_run: bool = Form(default=False),
    files: list[UploadFile] | None = File(default=None),
) -> OrchestrateResponse:
    state = get_app_state(request)
    service = state.orchestrator_service
    timeout_seconds = state.settings.orchestrate_timeout_seconds
    effective_dry_run = resolve_effective_dry_run(state, dry_run)
    text_parts = [prompt]
    attachments: list[FileAttachment] = []
    uploads = files or []

    for upload in uploads:
        text_content, attachment = await _extract_file_content(upload)
        if text_content is not None:
            text_parts.append(text_content)
        if attachment is not None:
            attachments.append(attachment)

    payload = OrchestrateRequest(
        prompt="\n\n".join(text_parts),
        model=model,
        models=_parse_models_form_value(models),
        session_id=session_id,
        dry_run=effective_dry_run,
    )
    trace_id = trace_id_from_metadata(payload.metadata)
    if trace_id:
        response.headers["x-trace-id"] = trace_id
    logger.info(
        log_message(
            "orchestrate.upload.request",
            dry_run=effective_dry_run,
            model_count=len(payload.requested_model_names()),
            attachment_count=len(attachments),
            prompt_length=len(payload.prompt),
        )
    )

    attachment_token = register_file_attachments(tuple(attachments))
    payload_for_submission = payload
    if attachment_token is not None:
        payload_for_submission = payload.model_copy(
            update={"metadata": {**payload.metadata, ATTACHMENT_METADATA_KEY: attachment_token}}
        )

    executor_future: asyncio.Future[SubmissionSnapshot] | None = None
    try:
        executor = getattr(state, "browser_executor", None)
        loop = asyncio.get_running_loop()
        executor_future = cast(
            asyncio.Future[SubmissionSnapshot],
            loop.run_in_executor(executor, service.submit_snapshot, payload_for_submission),
        )
        try:
            if timeout_seconds:
                snapshot = await asyncio.wait_for(executor_future, timeout=timeout_seconds)
            else:
                snapshot = await executor_future
        except TimeoutError as exc:
            executor_future.cancel()

            def _consume_timed_out_submission(
                _future: asyncio.Future[SubmissionSnapshot],
            ) -> None:
                try:
                    _future.exception()
                except BaseException:
                    return

            executor_future.add_done_callback(_consume_timed_out_submission)
            if attachment_token is not None:
                token = attachment_token

                def _discard_attachments_on_finish(
                    _future: asyncio.Future[SubmissionSnapshot],
                ) -> None:
                    discard_registered_attachments(token)

                executor_future.add_done_callback(_discard_attachments_on_finish)
                attachment_token = None
            logger.warning(
                log_message(
                    "orchestrate.upload.timeout",
                    timeout_seconds=timeout_seconds,
                )
            )
            raise HTTPException(status_code=504, detail="Orchestration request timed out.") from exc
        if (
            snapshot.task.status == TaskStatus.FAILED
            and snapshot.task.failure_code is not None
            and snapshot.task.failure_code.value == AUTH_TASK_FAILURE_CODE
        ):
            trace_id = trace_id_from_metadata(snapshot.task.metadata) or trace_id or str(uuid4())
            raise HTTPException(
                status_code=503,
                detail={
                    "code": AUTH_SYNC_HTTP_CODE,
                    "message": snapshot.task.failure_message or "Browser session is not authenticated.",
                    "trace_id": trace_id,
                },
                headers={"x-trace-id": trace_id},
            )
        try:
            requested_models = _requested_models_from_request(payload)
        except ValueError:
            requested_models = [
                ModelView(id=step.model_id, display_name=step.model_display_name)
                for step in snapshot.steps
            ]
        if payload_for_submission.metadata != payload.metadata:
            snapshot.task.metadata = dict(payload.metadata)
            events = await asyncio.to_thread(service.list_task_events, snapshot.task.task_id)
            await asyncio.to_thread(service._repository.replace_task_snapshot, snapshot.task, snapshot.steps, events)

        logger.info(
            log_message(
                "orchestrate.upload.accepted",
                task_id=snapshot.task.task_id,
                status=snapshot.task.status,
                execution_mode=snapshot.task.execution_mode,
                dry_run=snapshot.task.dry_run,
                model_count=snapshot.task.model_count,
                attachment_count=len(attachments),
            )
        )
        return OrchestrateResponse.from_task(
            snapshot.task,
            snapshot.steps,
            [],
            requested_models_override=requested_models,
        )
    except StorageUnavailableError as exc:
        logger.warning(
            log_message(
                "orchestrate.upload.storage_failed",
                operation=exc.operation,
                dry_run=effective_dry_run,
                model_count=len(payload.requested_model_names()),
                message=str(exc),
            )
        )
        raise HTTPException(status_code=503, detail=_storage_error_detail(exc)) from exc
    except ValueError as exc:
        logger.warning(
            log_message(
                "orchestrate.upload.rejected",
                code="validation_error",
                dry_run=effective_dry_run,
                message=str(exc),
            )
        )
        raise HTTPException(status_code=422, detail=_sanitize_validation_error(exc)) from exc
    except NotImplementedError as exc:
        logger.warning(
            log_message(
                "orchestrate.upload.rejected",
                code="not_implemented",
                dry_run=effective_dry_run,
                message=str(exc),
            )
        )
        raise HTTPException(status_code=501, detail="Requested capability is not available.") from exc
    except HTTPException:
        raise
    except Exception as exc:
        trace_id = trace_id or str(uuid4())
        logger.exception(
            log_message(
                "orchestrate.upload.failed",
                dry_run=effective_dry_run,
                model_count=len(payload.requested_model_names()),
                attachment_count=len(attachments),
                trace_id=trace_id,
            )
        )
        raise HTTPException(
            status_code=500,
            detail={
                "code": FailureCode.UNKNOWN_ERROR.value,
                "message": "Internal server error.",
                "trace_id": trace_id,
            },
            headers={"x-trace-id": trace_id},
        ) from exc
    finally:
        discard_registered_attachments(attachment_token)


@router.get(
    "/tasks",
    response_model=list[TaskListItem],
    summary="List recent tasks",
    description=(
        "Returns a paginated list of recent tasks with step and event summaries. "
        "Supports filtering by status, execution mode, dry_run flag, and failure code. "
        "Use the `before` cursor (ISO timestamp) for keyset pagination."
    ),
    response_description="List of task summaries ordered by accepted_at descending",
    responses={
        503: {"description": "Storage temporarily unavailable"},
    },
)
async def list_tasks(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    status: TaskStatus | None = Query(default=None),
    execution_mode: ExecutionMode | None = Query(default=None),
    dry_run: bool | None = Query(default=None),
    failure_code: FailureCode | None = Query(default=None),
    before: str | None = Query(default=None, description="Cursor: accepted_at ISO timestamp for pagination"),
    prompt_contains: str | None = Query(
        default=None,
        max_length=200,
        description="Filter by prompt substring (case-insensitive)",
    ),
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
            prompt_contains=prompt_contains,
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


@router.get(
    "/tasks/{task_id}",
    response_model=TaskView,
    summary="Get full task detail",
    description=(
        "Returns the complete execution context for a task: plan scalars, all steps, and events. "
        "Events are paginated via `events_limit` / `events_offset` query parameters."
    ),
    response_description="Full task view including steps and paginated events",
    responses={
        404: {"description": "Task not found"},
        503: {"description": "Storage temporarily unavailable"},
    },
)
async def get_task(
    request: Request,
    task_id: str = Path(pattern=_UUID_PATTERN),
    events_limit: int | None = Query(default=None, ge=1, le=1000),
    events_offset: int = Query(default=0, ge=0),
) -> TaskView:
    service = get_app_state(request).orchestrator_service
    try:
        view = await asyncio.to_thread(
            _load_task_view, service, task_id,
            events_limit=events_limit, events_offset=events_offset,
        )
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


@router.get(
    "/tasks/{task_id}/export",
    summary="Export task as Markdown",
    response_class=Response,
    responses={
        200: {"content": {"text/markdown": {}}, "description": "Task exported as Markdown"},
        404: {"description": "Task not found"},
        503: {"description": "Storage temporarily unavailable"},
    },
)
async def export_task(
    request: Request,
    task_id: str = Path(pattern=_UUID_PATTERN),
) -> Response:
    service = get_app_state(request).orchestrator_service
    try:
        task = await asyncio.to_thread(service.get_task, task_id)
    except StorageUnavailableError as exc:
        raise HTTPException(status_code=503, detail=_storage_error_detail(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc
    return Response(content=_render_task_export(task), media_type="text/markdown; charset=utf-8")


@router.post(
    "/tasks/{task_id}/retry",
    response_model=OrchestrateResponse,
    status_code=200,
    summary="Retry a failed or cancelled task",
    description=(
        "Synchronously creates and executes a new task that replays the original prompt and execution plan. "
        "Only tasks with status `failed` or `cancelled` can be retried. "
        "The new task carries a `retry_of_task_id` link back to the original."
    ),
    response_description="Final task snapshot for the retry linked back to the original task",
    responses={
        404: {"description": "Original task not found"},
        409: {"description": "Task status does not allow retry (not failed or cancelled)"},
        422: {"description": "Validation error reconstructing the retry request"},
        503: {"description": "Storage temporarily unavailable"},
    },
)
async def retry_task(
    request: Request,
    task_id: str = Path(pattern=_UUID_PATTERN),
) -> OrchestrateResponse:
    state = get_app_state(request)
    service = state.orchestrator_service
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
        _executor = getattr(state, "browser_executor", None)
        _loop = asyncio.get_running_loop()
        snapshot = await _loop.run_in_executor(
            _executor,
            functools.partial(service.submit_snapshot, retry_request, retry_of_task_id=task_id),
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
