from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

from gracekelly.core.contracts import (
    EventType,
    ExecutionBatchResult,
    ExecutionPlan,
    ExecutionResult,
    MergeStrategy,
    StepStatus,
    TaskStatus,
)
from gracekelly.storage.base import TaskEventRecord, TaskRecord, TaskStepRecord

__all__ = ["EventBuilder"]


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


class EventBuilder:
    def build_step_records(
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

    def build_events(
        self,
        task: TaskRecord,
        plan: ExecutionPlan,
        batch_result: ExecutionBatchResult,
        *,
        accepted_plan: ExecutionPlan | None = None,
    ) -> list[TaskEventRecord]:
        seq = _EventSequence(task.task_id)
        seq.append(EventType.TASK_ACCEPTED, task.accepted_at, self._accepted_payload(task, accepted_plan or plan))
        if task.dry_run:
            return seq.events
        step_summary = self._build_step_events(seq, task, plan, batch_result.results)
        self._build_terminal_event(seq, task, batch_result, step_summary)
        return seq.events

    def accepted_payload(self, task: TaskRecord, plan: ExecutionPlan) -> dict[str, object]:
        return self._accepted_payload(task, plan)

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

    @staticmethod
    def _event_result_details(result: ExecutionResult) -> dict[str, object]:
        if not result.details:
            return {}
        return {"details": json.loads(json.dumps(result.details, default=str))}

    @staticmethod
    def _event_batch_details(batch_result: ExecutionBatchResult) -> dict[str, object]:
        if not batch_result.details:
            return {}
        return {"details": json.loads(json.dumps(batch_result.details, default=str))}
