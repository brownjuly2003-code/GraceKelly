from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
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
from gracekelly.logging_utils import log_message, trace_id_from_metadata
from gracekelly.core.router import ExecutionRouter
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
    def __init__(self, repository: TaskRepository, execution_router: ExecutionRouter) -> None:
        self._repository = repository
        self._execution_router = execution_router

    def submit(self, request: OrchestrateRequest) -> TaskRecord:
        return self.submit_snapshot(request).task

    def submit_snapshot(self, request: OrchestrateRequest) -> SubmissionSnapshot:
        execution_plan = build_execution_plan(request)
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
        accepted_at = datetime.now(timezone.utc)
        batch_result = self._execution_router.execute(
            task_id=task_id,
            prompt=request.prompt,
            plan=execution_plan,
            reasoning=request.reasoning,
            metadata=dict(request.metadata),
        )
        completed_at = datetime.now(timezone.utc)
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
    ) -> list[TaskRecord]:
        try:
            return self._repository.list_recent(
                limit,
                status=status,
                execution_mode=execution_mode,
                dry_run=dry_run,
                failure_code=failure_code,
            )
        except Exception as exc:
            raise StorageUnavailableError("list_recent_tasks", str(exc)) from exc

    def list_task_events(self, task_id: str) -> list[TaskEventRecord]:
        try:
            return self._repository.list_events(task_id)
        except Exception as exc:
            raise StorageUnavailableError("list_task_events", str(exc)) from exc

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
        results = batch_result.results
        events: list[TaskEventRecord] = []
        sequence_no = 0

        def next_event(event_type: EventType, created_at: datetime, payload: dict[str, object]) -> TaskEventRecord:
            nonlocal sequence_no
            sequence_no += 1
            return TaskEventRecord(
                event_id=str(uuid4()),
                task_id=task.task_id,
                sequence_no=sequence_no,
                event_type=event_type,
                created_at=created_at,
                payload=payload,
            )

        events.append(
            next_event(
                EventType.TASK_ACCEPTED,
                task.accepted_at,
                {
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
                },
            )
        )

        if task.dry_run:
            return events

        completed_steps: list[dict[str, object]] = []
        failed_steps: list[dict[str, object]] = []
        cancelled_steps: list[int] = []

        for step, result in zip(plan.steps, results, strict=True):
            if result.status == StepStatus.COMPLETED:
                step_payload = {
                    "step_index": step.step_index,
                    "model_id": step.model.id,
                    "model_display_name": step.model.display_name,
                    "duration_ms": result.duration_ms,
                }
                step_payload.update(self._event_result_details(result))
                completed_steps.append(step_payload)
                events.append(
                    next_event(
                        EventType.STEP_COMPLETED,
                        task.completed_at or task.accepted_at,
                        step_payload,
                    )
                )
            elif result.status == StepStatus.FAILED:
                step_payload = {
                    "step_index": step.step_index,
                    "model_id": step.model.id,
                    "model_display_name": step.model.display_name,
                    "failure_code": result.failure_code.value if result.failure_code else None,
                    "failure_message": result.failure_message,
                }
                step_payload.update(self._event_result_details(result))
                failed_steps.append(step_payload)
                events.append(
                    next_event(
                        EventType.STEP_FAILED,
                        task.completed_at or task.accepted_at,
                        step_payload,
                    )
                )
            elif result.status == StepStatus.CANCELLED:
                cancelled_steps.append(step.step_index)

        if task.status == TaskStatus.COMPLETED:
            winning_step = None
            if task.merge_strategy == MergeStrategy.FIRST_SUCCESS or task.model_count == 1:
                winning_step = completed_steps[0] if completed_steps else None
            task_payload = {
                "winning_step_index": winning_step["step_index"] if winning_step else None,
                "winning_model_id": winning_step["model_id"] if winning_step else None,
                "duration_ms": task.duration_ms,
                "cancelled_steps": cancelled_steps,
                "cancel_reason": "quorum_reached" if cancelled_steps else None,
            }
            task_payload.update(self._event_batch_details(batch_result))
            events.append(
                next_event(
                    EventType.TASK_COMPLETED,
                    task.completed_at or task.accepted_at,
                    task_payload,
                )
            )
        elif task.status == TaskStatus.FAILED:
            task_payload = {
                "failure_code": task.failure_code.value if task.failure_code else None,
                "failure_message": task.failure_message,
                "failed_steps": failed_steps,
            }
            task_payload.update(self._event_batch_details(batch_result))
            events.append(
                next_event(
                    EventType.TASK_FAILED,
                    task.completed_at or task.accepted_at,
                    task_payload,
                )
            )
        elif task.status == TaskStatus.CANCELLED:
            task_payload = {
                "reason": "operator",
                "cancelled_steps": cancelled_steps,
            }
            task_payload.update(self._event_batch_details(batch_result))
            events.append(
                next_event(
                    EventType.TASK_CANCELLED,
                    task.completed_at or task.accepted_at,
                    task_payload,
                )
            )
        return events

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
