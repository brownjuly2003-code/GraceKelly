from __future__ import annotations

import logging
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from time import perf_counter
from typing import Any, cast
from uuid import uuid4

from gracekelly.api.error_codes import AUTH_TASK_FAILURE_CODE
from gracekelly.config import Settings
from gracekelly.core.complexity import assess_complexity
from gracekelly.core.contracts import (
    CancellationToken,
    EventType,
    ExecutionBackend,
    ExecutionBatchResult,
    ExecutionMode,
    ExecutionPlan,
    ExecutionRequest,
    ExecutionResult,
    FailureCode,
    MergeStrategy,
    StepStatus,
    TaskStatus,
)
from gracekelly.core.decomposition import execute_decomposed
from gracekelly.core.event_builder import EventBuilder
from gracekelly.core.planning import build_execution_plan
from gracekelly.core.router import ExecutionRouter
from gracekelly.core.session_context import build_session_context
from gracekelly.logging_utils import log_message, trace_id_from_metadata
from gracekelly.schemas import OrchestrateRequest
from gracekelly.storage.base import TaskEventRecord, TaskRecord, TaskRepository, TaskStepRecord

logger = logging.getLogger(__name__)


class StorageUnavailableError(RuntimeError):
    def __init__(self, operation: str, message: str) -> None:
        super().__init__(f"Storage operation '{operation}' failed: {message}")
        self.operation = operation


@dataclass(frozen=True, slots=True)
class SubmissionSnapshot:
    task: TaskRecord
    steps: list[TaskStepRecord]


class OrchestratorService:
    def __init__(self, repository: TaskRepository, execution_router: ExecutionRouter, settings: Settings | None = None) -> None:
        self._repository = repository
        self._execution_router = execution_router
        self._settings = settings if settings is not None else Settings()
        self._event_buffer: deque[TaskEventRecord] = deque(maxlen=500)
        self._event_builder = EventBuilder()

    def submit(self, request: OrchestrateRequest) -> TaskRecord:
        return self.submit_snapshot(request).task

    def submit_snapshot(self, request: OrchestrateRequest, *, retry_of_task_id: str | None = None) -> SubmissionSnapshot:
        self._flush_buffer()
        task_id = str(uuid4())
        active_request = request if request.session_id is None else request.model_copy(update={"prompt": build_session_context(self._repository, request.session_id, request.prompt, self._settings)})
        execution_plan = build_execution_plan(active_request)
        trace_id = trace_id_from_metadata(request.metadata)
        logger.info(log_message("task.submit.started", task_id=task_id, trace_id=trace_id, dry_run=execution_plan.dry_run, model_count=len(execution_plan.steps), quorum=execution_plan.quorum, merge_strategy=execution_plan.merge_strategy))
        accepted_at = datetime.now(UTC)
        planned_backends = {step.backend.value for step in execution_plan.steps}
        accepted_execution_mode = ExecutionMode.DRY_RUN if execution_plan.dry_run else ExecutionMode(next(iter(planned_backends))) if len(planned_backends) == 1 else ExecutionMode.MIXED
        base_task: dict[str, Any] = {
            "task_id": task_id, "accepted_at": accepted_at, "prompt": request.prompt, "reasoning": request.reasoning,
            "dry_run": execution_plan.dry_run, "model_count": len(execution_plan.steps), "quorum": execution_plan.quorum,
            "merge_strategy": execution_plan.merge_strategy, "adapter_hint": execution_plan.adapter_hint,
            "cancel_on_quorum": execution_plan.cancel_on_quorum, "metadata": dict(request.metadata),
            "retry_of_task_id": retry_of_task_id, "session_id": request.session_id,
        }
        accepted_task = TaskRecord(status=TaskStatus.ACCEPTED, completed_at=None, duration_ms=None, execution_mode=accepted_execution_mode, **cast(Any, base_task))
        accepted_event = TaskEventRecord(event_id=str(uuid4()), task_id=task_id, sequence_no=1, event_type=EventType.TASK_ACCEPTED, created_at=accepted_at, payload=self._event_builder.accepted_payload(accepted_task, execution_plan))
        try:
            self._repository.save_task_with_steps(accepted_task, [])
        except Exception as exc:
            logger.warning(log_message("task.submit.storage_failed", task_id=task_id, trace_id=trace_id, operation="save_task_with_steps", message=str(exc)))
            raise StorageUnavailableError("save_task_with_steps", str(exc)) from exc
        try:
            self._repository.append_event(accepted_event)
        except Exception as exc:
            logger.warning(log_message("task.event_persistence_failed", task_id=task_id, trace_id=trace_id, event_type=accepted_event.event_type, sequence_no=accepted_event.sequence_no, message=str(exc)))
        result_plan = execution_plan
        was_decomposed = False
        subtask_count = 0
        if request.decompose and assess_complexity(active_request.prompt).should_decompose and not execution_plan.dry_run:
            decomp_result = execute_decomposed(active_request.prompt, self._make_execute_fn(task_id, execution_plan, request.reasoning, dict(request.metadata)))
            was_decomposed = decomp_result.was_decomposed
            subtask_count = len(decomp_result.subtasks) if was_decomposed else 0
            step = execution_plan.steps[0]
            decomposition_details = {"was_decomposed": was_decomposed, "subtask_count": subtask_count, "subtasks": [item.prompt for item in decomp_result.subtasks]}
            result_plan = ExecutionPlan(steps=(step,), quorum=1, merge_strategy=MergeStrategy.FIRST_SUCCESS, dry_run=False, adapter_hint=execution_plan.adapter_hint, cancel_on_quorum=False)
            synthetic_result = ExecutionResult(adapter_name=f"{step.backend.value}.{step.provider}", model_id=step.model.id, model_display_name=step.model.display_name, execution_mode=ExecutionMode(step.backend.value), status=StepStatus.COMPLETED, output_text=decomp_result.final_answer, details={"decomposition": decomposition_details})
            batch_result = ExecutionBatchResult(
                execution_mode=synthetic_result.execution_mode,
                task_status=TaskStatus.COMPLETED,
                results=(synthetic_result,),
                output_text=decomp_result.final_answer,
                details={
                    "quorum": 1, "merge_strategy": MergeStrategy.FIRST_SUCCESS, "adapter_names": [synthetic_result.adapter_name],
                    "completed_step_count": 1, "failed_step_count": 0, "cancelled_step_count": 0, "failure_codes": [],
                    "winning_step_index": step.step_index, "winning_model_id": step.model.id, "cancelled_steps": [], "cancel_reason": None,
                    "decomposition": decomposition_details,
                },
            )
        else:
            if not execution_plan.dry_run and execution_plan.steps and all(step.backend == ExecutionBackend.BROWSER for step in execution_plan.steps):
                batch_result = self._execute_browser_plan_inline(
                    task_id=task_id,
                    prompt=active_request.prompt,
                    plan=execution_plan,
                    reasoning=request.reasoning,
                    metadata=dict(request.metadata),
                )
            else:
                batch_result = self._execution_router.execute(task_id=task_id, prompt=active_request.prompt, plan=execution_plan, reasoning=request.reasoning, metadata=dict(request.metadata))
        if (
            batch_result.failure_code is not None
            and batch_result.failure_code.value == AUTH_TASK_FAILURE_CODE
            and trace_id is None
        ):
            trace_id = str(uuid4())
            base_task["metadata"] = {**dict(request.metadata), "trace_id": trace_id}
        completed_at = datetime.now(UTC)
        duration_ms = max(0, int((completed_at - accepted_at).total_seconds() * 1000))
        task = TaskRecord(status=batch_result.task_status, completed_at=completed_at, duration_ms=duration_ms, execution_mode=batch_result.execution_mode, failure_code=batch_result.failure_code, failure_message=batch_result.failure_message, output_text=batch_result.output_text, was_decomposed=was_decomposed, subtask_count=subtask_count, **cast(Any, base_task))
        steps = self._event_builder.build_step_records(task_id, result_plan, batch_result.results)
        events = self._event_builder.build_events(task, result_plan, batch_result, accepted_plan=execution_plan)
        try:
            self._repository.replace_task_snapshot(task, steps, events)
        except Exception as exc:
            logger.warning(log_message("task.submit.storage_failed", task_id=task_id, trace_id=trace_id, operation="replace_task_snapshot", message=str(exc)))
            raise StorageUnavailableError("replace_task_snapshot", str(exc)) from exc
        logger.info(log_message("task.submit.completed", task_id=task_id, trace_id=trace_id, status=task.status, execution_mode=task.execution_mode, dry_run=task.dry_run, step_count=len(steps), event_count=len(events)))
        return SubmissionSnapshot(task=task, steps=steps)

    def get_task(self, task_id: str) -> TaskRecord:
        try:
            task = self._repository.get(task_id)
        except Exception as exc:
            raise StorageUnavailableError("get_task", str(exc)) from exc
        if task is None:
            raise KeyError(task_id)
        return task

    def list_task_steps(self, task_id: str) -> list[TaskStepRecord]:
        try:
            return self._repository.list_steps(task_id)
        except Exception as exc:
            raise StorageUnavailableError("list_task_steps", str(exc)) from exc

    def list_recent_tasks(self, limit: int = 20, *, status: TaskStatus | None = None, execution_mode: ExecutionMode | None = None, dry_run: bool | None = None, failure_code: FailureCode | None = None, before: datetime | None = None, prompt_contains: str | None = None) -> list[TaskRecord]:
        try:
            return self._repository.list_recent(limit, status=status, execution_mode=execution_mode, dry_run=dry_run, failure_code=failure_code, before=before, prompt_contains=prompt_contains)
        except Exception as exc:
            raise StorageUnavailableError("list_recent_tasks", str(exc)) from exc

    def list_task_events(self, task_id: str) -> list[TaskEventRecord]:
        try:
            return self._repository.list_events(task_id)
        except Exception as exc:
            raise StorageUnavailableError("list_task_events", str(exc)) from exc

    def list_task_events_paginated(self, task_id: str, *, limit: int | None = None, offset: int = 0) -> tuple[list[TaskEventRecord], int]:
        try:
            return self._repository.list_events_paginated(task_id, limit=limit, offset=offset)
        except Exception as exc:
            raise StorageUnavailableError("list_task_events_paginated", str(exc)) from exc

    def list_steps_batch(self, task_ids: list[str]) -> dict[str, list[TaskStepRecord]]:
        try:
            return self._repository.list_steps_batch(task_ids)
        except Exception as exc:
            raise StorageUnavailableError("list_steps_batch", str(exc)) from exc

    def list_events_batch(self, task_ids: list[str]) -> dict[str, list[TaskEventRecord]]:
        try:
            return self._repository.list_events_batch(task_ids)
        except Exception as exc:
            raise StorageUnavailableError("list_events_batch", str(exc)) from exc

    def _make_execute_fn(self, task_id: str, plan: ExecutionPlan, reasoning: bool, metadata: dict[str, object]) -> Callable[[str], str]:
        step = plan.steps[0]

        def execute_fn(prompt: str) -> str:
            request = ExecutionRequest(task_id=task_id, prompt=prompt, plan=plan, step=step, reasoning=reasoning, metadata=dict(metadata), cancellation=CancellationToken())
            result = self._execution_router._dry_run_adapter.execute(request) if plan.dry_run else self._execution_router._dispatch_step(step, request)
            return result.output_text or ""

        return execute_fn

    def _execute_browser_plan_inline(
        self,
        *,
        task_id: str,
        prompt: str,
        plan: ExecutionPlan,
        reasoning: bool,
        metadata: dict[str, object],
    ) -> ExecutionBatchResult:
        cancellation = CancellationToken()
        results: list[ExecutionResult] = []
        for step in plan.steps:
            if cancellation.is_cancelled:
                results.append(self._execution_router._cancelled_result(step))
                continue
            request = ExecutionRequest(
                task_id=task_id,
                prompt=prompt,
                plan=plan,
                step=step,
                reasoning=reasoning,
                metadata=dict(metadata),
                cancellation=cancellation,
            )
            started = perf_counter()
            result = self._execution_router._dispatch_step(step, request)
            results.append(self._execution_router._stamp_duration(result, started))
            if plan.cancel_on_quorum and self._execution_router._successful_count(tuple(results)) >= plan.quorum:
                cancellation.request_cancel()
        return self._execution_router._aggregate(plan, tuple(results))

    def _flush_buffer(self) -> None:
        while self._event_buffer:
            event = self._event_buffer.popleft()
            try:
                self._repository.append_event(event)
            except Exception:
                self._event_buffer.appendleft(event)
                break

    def _append_event_safe(self, event: TaskEventRecord, *, trace_id: str | None = None) -> None:
        try:
            self._repository.append_event(event)
        except Exception as exc:
            logger.warning(log_message("task.event_persistence_failed", task_id=event.task_id, trace_id=trace_id, event_type=event.event_type, sequence_no=event.sequence_no, message=str(exc)))
            self._event_buffer.append(event)
