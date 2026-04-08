from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from gracekelly.app_state import get_app_state
from gracekelly.core.contracts import (
    AdapterHint,
    ExecutionBackend,
    ExecutionMode,
    ExecutionPlan,
    ExecutionRequest,
    ExecutionStep,
    MergeStrategy,
    StepStatus,
    StreamChunk,
    TaskStatus,
)
from gracekelly.core.models import resolve_model
from gracekelly.schemas import OrchestrateRequest
from gracekelly.storage.base import TaskRecord, TaskStepRecord

router = APIRouter(prefix="/api/v1", tags=["streaming"])


def _format_sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _persist_stream_result(
    state: Any,
    body: OrchestrateRequest,
    model: Any,
    output_text: str | None,
    duration_ms: int | None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    task_id: str | None = None,
) -> str:
    task_id = task_id or str(uuid4())
    now = datetime.now(UTC)
    repo = state.task_repository
    if repo is None:
        return task_id
    task = TaskRecord(
        task_id=task_id,
        status=TaskStatus.COMPLETED,
        accepted_at=now,
        completed_at=now,
        duration_ms=duration_ms,
        prompt=body.prompt,
        reasoning=body.reasoning,
        execution_mode=ExecutionMode.DRY_RUN if body.dry_run else ExecutionMode.API,
        dry_run=body.dry_run,
        model_count=1,
        quorum=1,
        merge_strategy=MergeStrategy.FIRST_SUCCESS,
        adapter_hint=AdapterHint.AUTO,
        cancel_on_quorum=False,
        output_text=output_text,
        metadata=body.metadata,
    )
    step = TaskStepRecord(
        task_id=task_id,
        step_index=0,
        model_id=model.id,
        model_display_name=model.display_name,
        backend="api",
        provider=model.provider,
        status=StepStatus.COMPLETED,
        output_text=output_text,
        duration_ms=duration_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    repo.save_task_with_steps(task, [step])
    return task_id


async def _stream_chunks(
    adapter: Any,
    exec_request: ExecutionRequest,
    final_state: dict[str, Any] | None = None,
) -> AsyncIterator[str]:
    queue: asyncio.Queue[StreamChunk | None] = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def _produce() -> None:
        try:
            for chunk in adapter.execute_stream(exec_request):
                loop.call_soon_threadsafe(queue.put_nowait, chunk)
        except Exception as exc:
            loop.call_soon_threadsafe(queue.put_nowait, StreamChunk(type="error", text=str(exc)))
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    _ = loop.run_in_executor(None, _produce)

    while True:
        chunk = await queue.get()
        if chunk is None:
            break
        if chunk.type == "complete" and final_state is not None:
            final_state["text"] = chunk.text
            final_state.update(chunk.details)
        yield _format_sse(
            chunk.type,
            {
                "text": chunk.text,
                "model_id": chunk.model_id,
                **chunk.details,
            },
        )


@router.post("/orchestrate/stream")
async def orchestrate_stream(request: Request, body: OrchestrateRequest) -> StreamingResponse:
    state = get_app_state(request)
    model_names = body.requested_model_names()
    if not model_names:
        return StreamingResponse(
            iter([_format_sse("error", {"text": "No model specified"})]),
            media_type="text/event-stream",
        )

    model_name = model_names[0]
    resolved = resolve_model(model_name)
    if resolved is None:
        return StreamingResponse(
            iter([_format_sse("error", {"text": f"Unknown model: {model_name}"})]),
            media_type="text/event-stream",
        )

    provider = resolved.provider
    adapter = state.dry_run_adapter if body.dry_run else state.api_adapters.get(provider)
    supports_streaming = adapter is not None and provider != "anthropic" and hasattr(adapter, "execute_stream")

    if not supports_streaming:
        task_id = str(uuid4())
        step = ExecutionStep(
            model=resolved,
            backend=ExecutionBackend.API,
            provider=provider,
            provider_model_id=resolved.provider_model_id,
            step_index=0,
        )
        plan = ExecutionPlan(
            steps=(step,),
            quorum=1,
            merge_strategy=MergeStrategy.FIRST_SUCCESS,
            dry_run=body.dry_run,
            adapter_hint=AdapterHint.AUTO,
            cancel_on_quorum=False,
        )
        exec_request = ExecutionRequest(
            task_id=task_id,
            prompt=body.prompt,
            plan=plan,
            step=step,
            reasoning=body.reasoning,
        )
        fallback = adapter or state.dry_run_adapter
        result = await asyncio.to_thread(fallback.execute, exec_request)
        await asyncio.to_thread(
            _persist_stream_result,
            state,
            body,
            resolved,
            result.output_text,
            result.duration_ms,
            result.input_tokens,
            result.output_tokens,
            exec_request.task_id,
        )

        async def _fallback_stream() -> AsyncIterator[str]:
            yield _format_sse(
                "complete",
                {
                    "text": result.output_text or "",
                    "model_id": result.model_id,
                    "duration_ms": result.duration_ms,
                },
            )

        return StreamingResponse(_fallback_stream(), media_type="text/event-stream")

    assert adapter is not None

    task_id = str(uuid4())
    step = ExecutionStep(
        model=resolved,
        backend=ExecutionBackend.API,
        provider=provider,
        provider_model_id=resolved.provider_model_id,
        step_index=0,
    )
    plan = ExecutionPlan(
        steps=(step,),
        quorum=1,
        merge_strategy=MergeStrategy.FIRST_SUCCESS,
        dry_run=body.dry_run,
        adapter_hint=AdapterHint.AUTO,
        cancel_on_quorum=False,
    )
    exec_request = ExecutionRequest(
        task_id=task_id,
        prompt=body.prompt,
        plan=plan,
        step=step,
        reasoning=body.reasoning,
    )
    final_state: dict[str, Any] = {}

    async def _event_stream() -> AsyncIterator[str]:
        yield _format_sse("accepted", {"model_id": resolved.id, "task_id": exec_request.task_id})
        async for sse_line in _stream_chunks(adapter, exec_request, final_state):
            yield sse_line
        if "text" not in final_state:
            return
        await asyncio.to_thread(
            _persist_stream_result,
            state,
            body,
            resolved,
            final_state.get("text"),
            final_state.get("duration_ms"),
            final_state.get("input_tokens"),
            final_state.get("output_tokens"),
            exec_request.task_id,
        )

    return StreamingResponse(_event_stream(), media_type="text/event-stream")
