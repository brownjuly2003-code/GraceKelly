from __future__ import annotations

import json
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import uuid4

from gracekelly.core.contracts import (
    EventType,
    ExecutionBatchResult,
    ExecutionMode,
    ExecutionPlan,
    ExecutionResult,
    FailureCode,
    MergeStrategy,
    StepStatus,
    TaskStatus,
)
from gracekelly.core.planning import build_execution_plan
from gracekelly.core.router import ExecutionRouter
from gracekelly.logging_utils import log_message, trace_id_from_metadata
from gracekelly.schemas import OrchestrateRequest
from gracekelly.storage.base import TaskEventRecord, TaskRecord, TaskRepository, TaskStepRecord

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _StepSummary:
    completed: list[dict[str, object]] = field(default_factory=list)
    failed: list[dict[str, object]] = field(default_factory=list)
    cancelled_indexes: list[int] = field(default_factory=list)


class _EventSequence:
    def __init__(self, task_id: str) -> None:
        self._task_id = task_id
        self._sequence_no = 0
        self.events: list[TaskEventRecord] = []

    def append(self, event_type: EventType, created_at: datetime, payload: dict[str, object]) -> None:
        self._sequence_no += 1
        self.events.append(
            TaskEventRecord(
                event_id=str(uuid4()),
                task_id=self._task_id,
                sequence_no=self._sequence_no,
                event_type=event_type,
                created_at=created_at,
                payload=payload,
            )
        )


class StorageUnavailableError(RuntimeError):
    def __init__(self, operation: str, message: str) -> None:
        super().__init__(f"Storage operation '{operation}' failed: {message}")
        self.operation = operation


@dataclass(frozen=True, slots=True)
class SubmissionSnapshot:
    task: TaskRecord
    steps: list[TaskStepRecord]


class OrchestratorService:
    def __init__(self, repository: TaskRepository, execution_router: ExecutionRouter) -> None:
        self._repository = repository
        self._execution_router = execution_router
        self._event_buffer: deque[TaskEventRecord] = deque(maxlen=500)

    def submit(self, request: OrchestrateRequest) -> TaskRecord:
        return self.submit_snapshot(request).task

    def submit_snapshot(
        self,
        request: OrchestrateRequest,
        *,
        retry_of_task_id: str | None = None,
    ) -> SubmissionSnapshot:
        execution_plan = build_execution_plan(request)
        self._flush_buffer()
        task_id = str(uuid4())
        trace_id = trace_id_from_metadata(request.metadata)
        logger.info(
            log_message(
                "task.submit.started",
                task_id=task_id,
                trace_id=trace_id,
                dry_run=execution_plan.dry_run,
                model_count=len(execution_plan.steps),
                quorum=execution_plan.quorum,
                merge_strategy=execution_plan.merge_strategy,
            )
        )
        accepted_at = datetime.now(UTC)
        batch_result = self._execution_router.execute(
            task_id=task_id,
            prompt=request.prompt,
            plan=execution_plan,
            reasoning=request.reasoning,
            metadata=dict(request.metadata),
        )
        completed_at = datetime.now(UTC)
        duration_ms = max(0, int((completed_at - accepted_at).total_seconds() * 1000))

        task = TaskRecord(
            task_id=task_id,
            status=batch_result.task_status,
            accepted_at=accepted_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            prompt=request.prompt,
            reasoning=request.reasoning,
            execution_mode=batch_result.execution_mode,
            dry_run=execution_plan.dry_run,
            model_count=len(execution_plan.steps),
            quorum=execution_plan.quorum,
            merge_strategy=execution_plan.merge_strategy,
            adapter_hint=execution_plan.adapter_hint,
            cancel_on_quorum=execution_plan.cancel_on_quorum,
            failure_code=batch_result.failure_code,
            failure_message=batch_result.failure_message,
            output_text=batch_result.output_text,
            metadata=dict(request.metadata),
            retry_of_task_id=retry_of_task_id,
        )
        steps = self._build_step_records(task_id, execution_plan, batch_result.results)
        try:
            self._repository.save_task_with_steps(task, steps)
        except Exception as exc:
            logger.warning(
                log_message(
                    "task.submit.storage_failed",
                    task_id=task_id,
                    trace_id=trace_id,
                    operation="save_task_with_steps",
                    message=str(exc),
                )
            )
            raise StorageUnavailableError("save_task_with_steps", str(exc)) from exc

        for event in self._build_events(task, execution_plan, batch_result):
            self._append_event_safe(event, trace_id=trace_id)
        logger.info(
            log_message(
                "task.submit.completed",
                task_id=task_id,
                trace_id=trace_id,
                status=task.status,
                execution_mode=task.execution_mode,
                dry_run=task.dry_run,
                step_count=len(steps),
                event_count=1 if task.dry_run else len(batch_result.results) + 2,
            )
        )
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

    def list_recent_tasks(
        self,
        limit: int = 20,
        *,
        status: TaskStatus | None = None,
        execution_mode: ExecutionMode | None = None,
        dry_run: bool | None = None,
        failure_code: FailureCode | None = None,
        before: datetime | None = None,
    ) -> list[TaskRecord]:
        try:
            return self._repository.list_recent(
                limit,
                status=status,
                execution_mode=execution_mode,
                dry_run=dry_run,
                failure_code=failure_code,
                before=before,
            )
        except Exception as exc:
            raise StorageUnavailableError("list_recent_tasks", str(exc)) from exc

    def list_task_events(self, task_id: str) -> list[TaskEventRecord]:
        try:
            return self._repository.list_events(task_id)
        except Exception as exc:
            raise StorageUnavailableError("list_task_events", str(exc)) from exc

    def list_task_events_paginated(
        self,
        task_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> tuple[list[TaskEventRecord], int]:
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

    def _build_step_records(
        self,
        task_id: str,
        plan: ExecutionPlan,
        results: tuple[ExecutionResult, ...],
    ) -> list[TaskStepRecord]:
        if plan.dry_run:
            return []
        records = []
        for step, result in zip(plan.steps, results, strict=True):
            records.append(
                TaskStepRecord(
                    task_id=task_id,
                    step_index=step.step_index,
                    model_id=step.model.id,
                    model_display_name=step.model.display_name,
                    backend=step.backend.value,
                    provider=step.provider,
                    status=result.status,
                    failure_code=result.failure_code,
                    failure_message=result.failure_message,
                    output_text=result.output_text,
                    duration_ms=result.duration_ms,
                )
            )
        return records

    def _build_events(
        self,
        task: TaskRecord,
        plan: ExecutionPlan,
        batch_result: ExecutionBatchResult,
    ) -> list[TaskEventRecord]:
        seq = _EventSequence(task.task_id)
        seq.append(EventType.TASK_ACCEPTED, task.accepted_at, self._accepted_payload(task, plan))
        if task.dry_run:
            return seq.events

        step_summary = self._build_step_events(seq, task, plan, batch_result.results)
        self._build_terminal_event(seq, task, batch_result, step_summary)
        return seq.events

    def _accepted_payload(self, task: TaskRecord, plan: ExecutionPlan) -> dict[str, object]:
        return {
            "dry_run": task.dry_run,
            "execution_plan": {
                "quorum": plan.quorum,
                "merge_strategy": plan.merge_strategy,
                "adapter_hint": plan.adapter_hint,
                "cancel_on_quorum": plan.cancel_on_quorum,
                "steps": [
                    {
                        "step_index": step.step_index,
                        "model_id": step.model.id,
                        "display_name": step.model.display_name,
                        "backend": step.backend.value,
                        "provider": step.provider,
                    }
                    for step in plan.steps
                ],
            },
        }

    def _build_step_events(
        self,
        seq: _EventSequence,
        task: TaskRecord,
        plan: ExecutionPlan,
        results: tuple[ExecutionResult, ...],
    ) -> _StepSummary:
        summary = _StepSummary()
        event_time = task.completed_at or task.accepted_at
        for step, result in zip(plan.steps, results, strict=True):
            if result.status == StepStatus.COMPLETED:
                payload: dict[str, object] = {
                    "step_index": step.step_index,
                    "model_id": step.model.id,
                    "model_display_name": step.model.display_name,
                    "duration_ms": result.duration_ms,
                }
                payload.update(self._event_result_details(result))
                summary.completed.append(payload)
                seq.append(EventType.STEP_COMPLETED, event_time, payload)
            elif result.status == StepStatus.FAILED:
                payload = {
                    "step_index": step.step_index,
                    "model_id": step.model.id,
                    "model_display_name": step.model.display_name,
                    "failure_code": result.failure_code.value if result.failure_code else None,
                    "failure_message": result.failure_message,
                }
                payload.update(self._event_result_details(result))
                summary.failed.append(payload)
                seq.append(EventType.STEP_FAILED, event_time, payload)
            elif result.status == StepStatus.CANCELLED:
                summary.cancelled_indexes.append(step.step_index)
        return summary

    def _build_terminal_event(
        self,
        seq: _EventSequence,
        task: TaskRecord,
        batch_result: ExecutionBatchResult,
        step_summary: _StepSummary,
    ) -> None:
        event_time = task.completed_at or task.accepted_at
        batch_details = self._event_batch_details(batch_result)

        if task.status == TaskStatus.COMPLETED:
            winning_step = None
            if task.merge_strategy == MergeStrategy.FIRST_SUCCESS or task.model_count == 1:
                winning_step = step_summary.completed[0] if step_summary.completed else None
            payload: dict[str, object] = {
                "winning_step_index": winning_step["step_index"] if winning_step else None,
                "winning_model_id": winning_step["model_id"] if winning_step else None,
                "duration_ms": task.duration_ms,
                "cancelled_steps": step_summary.cancelled_indexes,
                "cancel_reason": "quorum_reached" if step_summary.cancelled_indexes else None,
            }
            payload.update(batch_details)
            seq.append(EventType.TASK_COMPLETED, event_time, payload)
        elif task.status == TaskStatus.FAILED:
            payload = {
                "failure_code": task.failure_code.value if task.failure_code else None,
                "failure_message": task.failure_message,
                "failed_steps": step_summary.failed,
            }
            payload.update(batch_details)
            seq.append(EventType.TASK_FAILED, event_time, payload)
        elif task.status == TaskStatus.CANCELLED:
            payload = {
                "reason": "operator",
                "cancelled_steps": step_summary.cancelled_indexes,
            }
            payload.update(batch_details)
            seq.append(EventType.TASK_CANCELLED, event_time, payload)

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
            logger.warning(
                log_message(
                    "task.event_persistence_failed",
                    task_id=event.task_id,
                    trace_id=trace_id,
                    event_type=event.event_type,
                    sequence_no=event.sequence_no,
                    message=str(exc),
                )
            )
            self._event_buffer.append(event)
            return

    def _event_result_details(self, result: ExecutionResult) -> dict[str, object]:
        if not result.details:
            return {}
        return {
            "details": json.loads(json.dumps(result.details, default=str)),
        }

    def _event_batch_details(self, batch_result: ExecutionBatchResult) -> dict[str, object]:
        if not batch_result.details:
            return {}
        return {
            "details": json.loads(json.dumps(batch_result.details, default=str)),
        }
