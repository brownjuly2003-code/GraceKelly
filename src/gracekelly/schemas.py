from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from pydantic import BaseModel, Field, model_validator

from gracekelly.core.contracts import AdapterHint, EventType, MergeStrategy, StepStatus, TaskStatus
from gracekelly.storage.base import TaskEventRecord, TaskRecord, TaskStepRecord


class OrchestrateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=40000)
    model: str | None = Field(default=None, min_length=1, max_length=120)
    models: list[str] = Field(default_factory=list, max_length=8)
    adapter_hint: AdapterHint = AdapterHint.AUTO
    quorum: int = Field(default=1, ge=1, le=8)
    merge_strategy: MergeStrategy = MergeStrategy.FIRST_SUCCESS
    cancel_on_quorum: bool = True
    reasoning: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    dry_run: bool = True

    @model_validator(mode="after")
    def validate_model_selection(self) -> "OrchestrateRequest":
        if self.model is None and not self.models:
            raise ValueError("Either 'model' or 'models' must be provided.")
        if self.model is not None and self.models:
            raise ValueError("Use either 'model' or 'models', not both.")
        try:
            json.dumps(self.metadata)
        except (TypeError, ValueError) as exc:
            raise ValueError("metadata must be JSON-serializable.") from exc
        return self

    def requested_model_names(self) -> list[str]:
        if self.model is not None:
            return [self.model]
        return list(self.models)


class ModelView(BaseModel):
    id: str
    display_name: str


class ModelCatalogItem(ModelView):
    aliases: list[str]
    adapter_kind: str
    provider: str
    reasoning_capable: bool
    timeout_seconds: int
    expected_latency_class: str
    concurrency_limit: int
    available: bool | None = None
    availability_status: str
    availability_checked_at: datetime | None = None
    availability_source: str | None = None
    last_verified_at: datetime | None = None


class TaskEventView(BaseModel):
    event_id: str
    sequence_no: int
    event_type: str
    created_at: datetime
    payload: dict[str, Any]

    @classmethod
    def from_record(cls, event: TaskEventRecord) -> "TaskEventView":
        return cls(
            event_id=event.event_id,
            sequence_no=event.sequence_no,
            event_type=event.event_type,
            created_at=event.created_at,
            payload=event.payload,
        )


class TaskStepView(BaseModel):
    step_index: int
    model_id: str
    model_display_name: str
    backend: str
    provider: str
    status: str
    failure_code: str | None = None
    failure_message: str | None = None
    output_text: str | None = None
    output_truncated: bool = False
    duration_ms: int | None = None

    @classmethod
    def from_record(
        cls,
        record: TaskStepRecord,
        *,
        max_output_length: int = 20_000,
    ) -> "TaskStepView":
        output = record.output_text
        truncated = False
        if output is not None and len(output) > max_output_length:
            output = output[:max_output_length]
            truncated = True
        return cls(
            step_index=record.step_index,
            model_id=record.model_id,
            model_display_name=record.model_display_name,
            backend=record.backend,
            provider=record.provider,
            status=record.status,
            failure_code=record.failure_code,
            failure_message=record.failure_message,
            output_text=output,
            output_truncated=truncated,
            duration_ms=record.duration_ms,
        )


class OrchestrateResponse(BaseModel):
    task_id: str
    status: str
    accepted_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = None
    execution_mode: str
    adapter_name: str
    failure_code: str | None = None
    failure_message: str | None = None
    model: ModelView | None = None
    requested_models: list[ModelView]
    output_text: str | None = None

    @classmethod
    def from_task(
        cls,
        task: TaskRecord,
        steps: list[TaskStepRecord] | None = None,
        events: list[TaskEventRecord] | None = None,
        requested_models_override: list[ModelView] | None = None,
    ) -> "OrchestrateResponse":
        step_records = list(steps or [])
        event_records = list(events or [])
        return cls(
            task_id=task.task_id,
            status=task.status,
            accepted_at=task.accepted_at,
            completed_at=task.completed_at,
            duration_ms=task.duration_ms,
            execution_mode=task.execution_mode,
            adapter_name=_resolve_adapter_name(task, step_records),
            failure_code=task.failure_code,
            failure_message=task.failure_message,
            model=_resolve_winning_model(task, step_records),
            requested_models=requested_models_override or _resolve_requested_models(step_records, event_records),
            output_text=task.output_text,
        )


class TaskListItem(BaseModel):
    task_id: str
    status: str
    accepted_at: datetime
    completed_at: datetime | None = None
    duration_ms: int | None = None
    execution_mode: str
    adapter_name: str
    model: ModelView | None = None
    dry_run: bool
    model_count: int
    requested_models: list[ModelView]
    cancelled_step_count: int = 0
    cancel_reason: str | None = None
    failure_code: str | None = None
    failure_message: str | None = None

    @classmethod
    def from_task(
        cls,
        task: TaskRecord,
        steps: list[TaskStepRecord] | None = None,
        events: list[TaskEventRecord] | None = None,
    ) -> "TaskListItem":
        step_records = list(steps or [])
        event_records = list(events or [])
        cancelled_step_count, cancel_reason = _resolve_cancel_summary(task, step_records, event_records)
        return cls(
            task_id=task.task_id,
            status=task.status,
            accepted_at=task.accepted_at,
            completed_at=task.completed_at,
            duration_ms=task.duration_ms,
            execution_mode=task.execution_mode,
            adapter_name=_resolve_adapter_name(task, step_records),
            model=_resolve_winning_model(task, step_records),
            dry_run=task.dry_run,
            model_count=task.model_count,
            requested_models=_resolve_requested_models(step_records, event_records),
            cancelled_step_count=cancelled_step_count,
            cancel_reason=cancel_reason,
            failure_code=task.failure_code,
            failure_message=task.failure_message,
        )


class TaskView(OrchestrateResponse):
    prompt: str
    reasoning: bool
    metadata: dict[str, Any]
    quorum: int
    merge_strategy: str
    adapter_hint: str
    cancel_on_quorum: bool
    retry_of_task_id: str | None = None
    winning_step_index: int | None = None
    cancelled_steps: list[int] = Field(default_factory=list)
    cancel_reason: str | None = None
    execution_details: dict[str, Any] = Field(default_factory=dict)
    steps: list[TaskStepView] = Field(default_factory=list)
    events: list[TaskEventView] = Field(default_factory=list)

    @classmethod
    def from_task(
        cls,
        task: TaskRecord,
        steps: list[TaskStepRecord] | None = None,
        events: list[TaskEventRecord] | None = None,
    ) -> "TaskView":
        step_records = list(steps or [])
        event_records = list(events or [])
        terminal_summary = _resolve_terminal_summary(event_records)
        return cls(
            task_id=task.task_id,
            status=task.status,
            accepted_at=task.accepted_at,
            completed_at=task.completed_at,
            duration_ms=task.duration_ms,
            execution_mode=task.execution_mode,
            adapter_name=_resolve_adapter_name(task, step_records),
            failure_code=task.failure_code,
            failure_message=task.failure_message,
            model=_resolve_winning_model(task, step_records),
            requested_models=_resolve_requested_models(step_records, event_records),
            output_text=task.output_text,
            prompt=task.prompt,
            reasoning=task.reasoning,
            metadata=task.metadata,
            quorum=task.quorum,
            merge_strategy=task.merge_strategy,
            adapter_hint=task.adapter_hint,
            cancel_on_quorum=task.cancel_on_quorum,
            retry_of_task_id=task.retry_of_task_id,
            winning_step_index=terminal_summary["winning_step_index"],
            cancelled_steps=terminal_summary["cancelled_steps"],
            cancel_reason=terminal_summary["cancel_reason"],
            execution_details=terminal_summary["execution_details"],
            steps=[TaskStepView.from_record(item) for item in step_records],
            events=[TaskEventView.from_record(item) for item in event_records],
        )


def _resolve_adapter_name(task: TaskRecord, steps: list[TaskStepRecord]) -> str:
    if task.dry_run:
        return "dry-run"
    if not steps:
        return "unknown"
    completed = [item for item in steps if item.status == StepStatus.COMPLETED]
    candidates = completed or [item for item in steps if item.status == StepStatus.FAILED] or steps
    adapter_names = {f"{item.backend}.{item.provider}" for item in candidates}
    if len(adapter_names) == 1:
        return adapter_names.pop()
    return "multi"


def _resolve_requested_models(
    steps: list[TaskStepRecord],
    events: list[TaskEventRecord],
) -> list[ModelView]:
    if steps:
        return [
            ModelView(id=item.model_id, display_name=item.model_display_name)
            for item in steps
        ]
    accepted_event = next((item for item in events if item.event_type == EventType.TASK_ACCEPTED), None)
    if accepted_event is None:
        return []
    plan = accepted_event.payload.get("execution_plan", {})
    items = plan.get("steps", [])
    if not isinstance(items, list):
        return []
    return [
        ModelView(id=item["model_id"], display_name=item["display_name"])
        for item in items
        if isinstance(item, dict) and "model_id" in item and "display_name" in item
    ]


def _resolve_winning_model(task: TaskRecord, steps: list[TaskStepRecord]) -> ModelView | None:
    if task.dry_run or task.status != TaskStatus.COMPLETED:
        return None
    if task.merge_strategy != MergeStrategy.FIRST_SUCCESS and task.model_count > 1:
        return None
    for item in steps:
        if item.status == StepStatus.COMPLETED:
            return ModelView(id=item.model_id, display_name=item.model_display_name)
    return None


def _resolve_cancel_summary(
    task: TaskRecord,
    steps: list[TaskStepRecord],
    events: list[TaskEventRecord],
) -> tuple[int, str | None]:
    if task.dry_run:
        return 0, None
    final_event_type = EventType.TASK_COMPLETED if task.status == TaskStatus.COMPLETED else EventType.TASK_CANCELLED
    final_event = next((item for item in reversed(events) if item.event_type == final_event_type), None)
    if final_event is not None:
        cancelled_steps = final_event.payload.get("cancelled_steps", [])
        cancel_reason = final_event.payload.get("cancel_reason")
        if isinstance(cancelled_steps, list):
            return len(cancelled_steps), cancel_reason if isinstance(cancel_reason, str) else None
    cancelled_count = sum(1 for item in steps if item.status == StepStatus.CANCELLED)
    cancel_reason = "quorum_reached" if cancelled_count and task.status == TaskStatus.COMPLETED else None
    return cancelled_count, cancel_reason


def _resolve_terminal_summary(events: list[TaskEventRecord]) -> dict[str, Any]:
    terminal_types = {
        EventType.TASK_COMPLETED,
        EventType.TASK_FAILED,
        EventType.TASK_CANCELLED,
    }
    terminal_event = next((item for item in reversed(events) if item.event_type in terminal_types), None)
    if terminal_event is None:
        return {
            "winning_step_index": None,
            "cancelled_steps": [],
            "cancel_reason": None,
            "execution_details": {},
        }

    payload = terminal_event.payload
    cancelled_steps = payload.get("cancelled_steps", [])
    details = payload.get("details", {})
    return {
        "winning_step_index": payload.get("winning_step_index"),
        "cancelled_steps": cancelled_steps if isinstance(cancelled_steps, list) else [],
        "cancel_reason": payload.get("cancel_reason") if isinstance(payload.get("cancel_reason"), str) else None,
        "execution_details": details if isinstance(details, dict) else {},
    }
