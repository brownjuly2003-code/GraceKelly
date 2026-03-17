from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from gracekelly.core.models import ModelSpec


class FailureCode(StrEnum):
    AUTH_FAILED = "auth_failed"
    MODEL_MISMATCH = "model_mismatch"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    STORAGE_FAILED = "storage_failed"
    UNKNOWN_ERROR = "unknown_error"


class ExecutionBackend(StrEnum):
    BROWSER = "browser"
    API = "api"


class AdapterHint(StrEnum):
    AUTO = "auto"
    BROWSER = "browser"
    API = "api"


class TaskStatus(StrEnum):
    ACCEPTED = "accepted"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MergeStrategy(StrEnum):
    FIRST_SUCCESS = "first_success"
    CONCAT = "concat"


class EventType(StrEnum):
    TASK_ACCEPTED = "task.accepted"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"
    TASK_CANCELLED = "task.cancelled"
    STEP_COMPLETED = "step.completed"
    STEP_FAILED = "step.failed"


@dataclass(slots=True)
class CancellationToken:
    _requested: bool = False

    def request_cancel(self) -> None:
        self._requested = True

    @property
    def is_cancelled(self) -> bool:
        return self._requested


@dataclass(frozen=True, slots=True)
class ExecutionStep:
    model: ModelSpec
    backend: ExecutionBackend
    provider: str
    provider_model_id: str
    step_index: int


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    steps: tuple[ExecutionStep, ...]
    quorum: int
    merge_strategy: MergeStrategy
    dry_run: bool
    adapter_hint: AdapterHint
    cancel_on_quorum: bool


@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    task_id: str
    prompt: str
    plan: ExecutionPlan
    step: ExecutionStep
    reasoning: bool
    metadata: dict[str, Any] = field(default_factory=dict)
    cancellation: CancellationToken | None = None

    @property
    def models(self) -> tuple[ModelSpec, ...]:
        return tuple(item.model for item in self.plan.steps)


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    adapter_name: str
    model_id: str
    model_display_name: str
    execution_mode: str
    status: StepStatus
    output_text: str | None = None
    failure_code: FailureCode | None = None
    failure_message: str | None = None
    duration_ms: int | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def is_failure(self) -> bool:
        return self.failure_code is not None


@dataclass(frozen=True, slots=True)
class ExecutionBatchResult:
    execution_mode: str
    task_status: TaskStatus
    results: tuple[ExecutionResult, ...]
    output_text: str | None = None
    failure_code: FailureCode | None = None
    failure_message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class ExecutionAdapter(ABC):
    name = "unknown"

    @abstractmethod
    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        raise NotImplementedError

    def healthcheck(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "adapter_name": self.name,
        }
