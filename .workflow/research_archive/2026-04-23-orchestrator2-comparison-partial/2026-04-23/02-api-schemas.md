# API request/response schemas side-by-side
Date: 2026-04-23
Status: schema comparison complete
Source of endpoint list: intended source is `01-inventory.md` sections 1.x; that artefact is absent in the current checkout, so the pairings below were reconstructed directly from route declarations in both projects.

## Intro
This document compares HTTP request/response schemas for the union of GraceKelly and Perplexity_Orchestrator2 endpoints.
Each H2 covers either a conservative cross-project pairing or a singleton endpoint with no reliable counterpart.
`Orchestrator2` refers to `D:/Perplexity_Orchestrator2/`; `GraceKelly` refers to `D:/GraceKelly/`.
`Request schema` sections describe JSON/form/query/path inputs accepted by the handler in the current codebase.
`Response schema` sections describe the successful response body shape only; error envelopes and runtime behavior are out of scope for this batch.
Field diffs are top-level only and use `identical`, `type-changed`, `default-changed`, `added`, `removed`.
Classification legend: `identical`, `compatible`, `breaking`, `orchestrator2-only`, `gracekelly-only`.
If a section mentions a stream or text payload, that note is schema-only; behavioral differences move to `03-api-behaviour.md`.

## GET /health
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/health.py:11-39`
```python
— (no request body)
```

### GraceKelly request schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/health.py:317-371`
```python
— (no request body)
```

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| — | no request body | no request body | identical |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/health.py:28, D:/Perplexity_Orchestrator2/api/routes/health.py:34`
```python
{
            "status": status,
            "accounts_available": available,
            "accounts_total": total,
        }

{
            "status": "error",
            "error": str(e),
            "accounts_available": 0,
            "accounts_total": 0,
        }
```

### GraceKelly response schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/health.py:343, D:/GraceKelly/src/gracekelly/api/routes/health.py:364`
```python
{"status": payload["status"]}

{
        "status": payload["status"],
        "version": payload.get("version", "0.1.0"),
        "environment": payload.get("environment"),
        "storage_backend": payload.get("storage_backend"),
        "active_model_executions": payload.get("active_model_executions"),
        "saturated_models": payload.get("saturated_models"),
    }
```

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `status` | status | payload['status'] | type-changed |
| `accounts_available` | available | — | removed |
| `accounts_total` | total | — | removed |
| `error` | str(e) | — | removed |
| `version` | — | payload.get('version', '0.1.0') | added |
| `environment` | — | payload.get('environment') | added |
| `storage_backend` | — | payload.get('storage_backend') | added |
| `active_model_executions` | — | payload.get('active_model_executions') | added |
| `saturated_models` | — | payload.get('saturated_models') | added |

### Curl examples
```bash
# Orchestrator2
curl -X GET "http://127.0.0.1:8001/health"

# GraceKelly
curl -X GET "http://127.0.0.1:8011/health"
```

### Classification
compatible
Обе стороны не принимают body и отдают JSON со `status`, но envelope полей различается.

## GET /api/v1/analytics
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/analytics.py:30-103`
```python
— (no request body)
```

### GraceKelly request schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/analytics.py:45-109`
```python
— (no request body)
```

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| — | no request body | no request body | identical |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/analytics.py:87`
```python
{
            "timestamp": now.isoformat(),
            "summary": {
                "total_queries": total_queries,
                "queries_24h": queries_24h,
                "success_rate": round(success_rate, 1),
                "avg_duration_ms": round(avg_duration, 0)
            },
            "queries_by_pattern": queries_by_pattern,
            "queries_per_hour": queries_per_hour
        }
```

### GraceKelly response schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/analytics.py:24-28, D:/GraceKelly/src/gracekelly/api/routes/analytics.py:15-21`
```python
class AnalyticsResponse(BaseModel):
    total_models: int
    total_executions: int
    models: list[ModelStatsView]
    top_models: list[ModelStatsView]

class ModelStatsView(BaseModel):
    model_id: str
    total_executions: int
    successful: int
    failed: int
    success_rate: float
    avg_duration_ms: float
```

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `timestamp` | now.isoformat() | — | removed |
| `summary` | {'total_queries': total_queries, 'queries_24h': queries_24h, 'success_rate': round(success_rate, 1), 'avg_duration_ms': round(avg_duration, 0)} | — | removed |
| `queries_by_pattern` | queries_by_pattern | — | removed |
| `queries_per_hour` | queries_per_hour | — | removed |
| `total_models` | — | int | added |
| `total_executions` | — | int | added |
| `models` | — | list[ModelStatsView] | added |
| `top_models` | — | list[ModelStatsView] | added |

### Curl examples
```bash
# Orchestrator2
curl -X GET "http://127.0.0.1:8001/api/analytics/overview"

# GraceKelly
curl -X GET "http://127.0.0.1:8011/api/v1/analytics"
```

### Classification
breaking
GraceKelly возвращает model analytics, а Orchestrator2 — dashboard overview с другим набором top-level ключей.

## POST /api/v1/orchestrate
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/gk_models.py:33-41, D:/Perplexity_Orchestrator2/api/routes/gk_models.py:13-22, D:/Perplexity_Orchestrator2/api/routes/gk_models.py:25-30`
```python
class GKOrchestrationRequest(BaseModel):
    """Request for GraceKelly orchestration."""
    query: str = Field(..., description="The question/task to execute", min_length=1)
    pattern: GKPattern = Field(default=GKPattern.DUAL, description="Orchestration pattern")
    thread_id: Optional[str] = Field(default=None, description="Thread ID for context")
    model: Optional[str] = Field(default=None, description="Specific model for single pattern")
    model_pair: Optional[str] = Field(default=None, description="Model pair for dual pattern (e.g. claude+gpt)")
    reasoning: Optional[bool] = Field(default=True, description="Enable reasoning/thinking mode (disable for structured output)")
    files: Optional[List[FileAttachment]] = Field(default=None, description="Attached files (base64-encoded)")

class GKPattern(str, Enum):
    """Orchestration patterns for GraceKelly."""
    BEST = "best"
    SONAR = "sonar"
    SINGLE = "single"
    DUAL = "dual"
    CONSENSUS = "consensus"
    MAXIMUM = "maximum"
    FIVE_MODELS = "five_models"
    FIVE_MODELS_COMPARE = "five_models_compare"

class FileAttachment(BaseModel):
    """File attached to a query."""
    name: str
    type: str = ""
    size: int = 0
    data: str = ""
```

### GraceKelly request schema
Source: `D:/GraceKelly/src/gracekelly/schemas.py:14-46`
```python
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
    dry_run: bool = False
    decompose: bool = Field(
        default=True,
        description="Enable automatic decomposition for complex prompts",
    )
    session_id: str | None = Field(default=None, description="Session ID for conversation chaining")

    @model_validator(mode="after")
    def validate_model_selection(self) -> OrchestrateRequest:
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
```

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `query` | str / Field(..., description='The question/task to execute', min_length=1) | — | removed |
| `pattern` | GKPattern / Field(default=GKPattern.DUAL, description='Orchestration pattern') | — | removed |
| `thread_id` | Optional[str] / Field(default=None, description='Thread ID for context') | — | removed |
| `model` | Optional[str] / Field(default=None, description='Specific model for single pattern') | str \| None / Field(default=None, min_length=1, max_length=120) | type-changed |
| `model_pair` | Optional[str] / Field(default=None, description='Model pair for dual pattern (e.g. claude+gpt)') | — | removed |
| `reasoning` | Optional[bool] / Field(default=True, description='Enable reasoning/thinking mode (disable for structured output)') | bool / False | type-changed |
| `files` | Optional[List[FileAttachment]] / Field(default=None, description='Attached files (base64-encoded)') | — | removed |
| `prompt` | — | str / Field(min_length=1, max_length=40000) | added |
| `models` | — | list[str] / Field(default_factory=list, max_length=8) | added |
| `adapter_hint` | — | AdapterHint / AdapterHint.AUTO | added |
| `quorum` | — | int / Field(default=1, ge=1, le=8) | added |
| `merge_strategy` | — | MergeStrategy / MergeStrategy.FIRST_SUCCESS | added |
| `cancel_on_quorum` | — | bool / True | added |
| `metadata` | — | dict[str, Any] / Field(default_factory=dict) | added |
| `dry_run` | — | bool / False | added |
| `decompose` | — | bool / Field(default=True, description='Enable automatic decomposition for complex prompts') | added |
| `session_id` | — | str \| None / Field(default=None, description='Session ID for conversation chaining') | added |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/gk_models.py:62-69, D:/Perplexity_Orchestrator2/api/routes/gk_models.py:44-50, D:/Perplexity_Orchestrator2/api/routes/gk_models.py:53-59`
```python
class GKOrchestrationResponse(BaseModel):
    """Response from GraceKelly orchestration."""
    task_id: str
    status: str
    pattern: str
    model_responses: List[ModelResponse] = []
    consensus: Optional[ConsensusResult] = None
    duration_ms: int = 0

class ModelResponse(BaseModel):
    """Response from a single model."""
    model: str
    text: str
    duration_ms: int = 0
    success: bool = True
    error: Optional[str] = None

class ConsensusResult(BaseModel):
    """Consensus analysis result."""
    text: str
    agreement_rate: int = 0
    completeness: int = 99
    agreement_sections: Optional[List[str]] = None
    difference_sections: Optional[List[str]] = None
```

### GraceKelly response schema
Source: `D:/GraceKelly/src/gracekelly/schemas.py:133-174, D:/GraceKelly/src/gracekelly/schemas.py:49-51`
```python
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
    was_decomposed: bool = False
    subtask_count: int = 0

    @classmethod
    def from_task(
        cls,
        task: TaskRecord,
        steps: list[TaskStepRecord] | None = None,
        events: list[TaskEventRecord] | None = None,
        requested_models_override: list[ModelView] | None = None,
    ) -> OrchestrateResponse:
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
            was_decomposed=task.was_decomposed,
            subtask_count=task.subtask_count,
        )

class ModelView(BaseModel):
    id: str
    display_name: str
```

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `task_id` | str | str | identical |
| `status` | str | str | identical |
| `pattern` | str | — | removed |
| `model_responses` | List[ModelResponse] / [] | — | removed |
| `consensus` | Optional[ConsensusResult] / None | — | removed |
| `duration_ms` | int / 0 | int \| None / None | type-changed |
| `accepted_at` | — | datetime | added |
| `completed_at` | — | datetime \| None / None | added |
| `execution_mode` | — | str | added |
| `adapter_name` | — | str | added |
| `failure_code` | — | str \| None / None | added |
| `failure_message` | — | str \| None / None | added |
| `model` | — | ModelView \| None / None | added |
| `requested_models` | — | list[ModelView] | added |
| `output_text` | — | str \| None / None | added |
| `was_decomposed` | — | bool / False | added |
| `subtask_count` | — | int / 0 | added |

### Curl examples
```bash
# Orchestrator2
curl -X POST "http://127.0.0.1:8001/api/gk/orchestrate" -H "Content-Type: application/json" -d '{"query": "Example prompt"}'

# GraceKelly
curl -X POST "http://127.0.0.1:8011/api/v1/orchestrate" -H "Content-Type: application/json" -d '{"prompt": "Example prompt", "model": "claude-sonnet-4-6"}'
```

### Classification
breaking
Контракт оркестрации разный: `prompt`/`query`, поля маршрутизации и формат итогового response не совпадают.

## GET /api/v1/tasks
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/tasks.py:312-317`
```python
— (no request body)
```

### GraceKelly request schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/orchestrate.py:607-660`
```python
# no request body; path/query parameters
limit: int = Query(default=20, ge=1, le=100)  # query
status: TaskStatus | None = Query(default=None)  # query
execution_mode: ExecutionMode | None = Query(default=None)  # query
dry_run: bool | None = Query(default=None)  # query
failure_code: FailureCode | None = Query(default=None)  # query
before: str | None = Query(default=None, description='Cursor: accepted_at ISO timestamp for pagination')  # query
prompt_contains: str | None = Query(default=None, max_length=200, description='Filter by prompt substring (case-insensitive)')  # query
```

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `limit` | — | int / Query(default=20, ge=1, le=100) | added |
| `status` | — | TaskStatus \| None / Query(default=None) | added |
| `execution_mode` | — | ExecutionMode \| None / Query(default=None) | added |
| `dry_run` | — | bool \| None / Query(default=None) | added |
| `failure_code` | — | FailureCode \| None / Query(default=None) | added |
| `before` | — | str \| None / Query(default=None, description='Cursor: accepted_at ISO timestamp for pagination') | added |
| `prompt_contains` | — | str \| None / Query(default=None, max_length=200, description='Filter by prompt substring (case-insensitive)') | added |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/tasks.py:317`
```python
{"tasks": tasks, "count": len(tasks)}
```

### GraceKelly response schema
Source: `D:/GraceKelly/src/gracekelly/schemas.py:177-220, D:/GraceKelly/src/gracekelly/schemas.py:49-51`
```python
# wrapper: list[TaskListItem]

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
    ) -> TaskListItem:
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

class ModelView(BaseModel):
    id: str
    display_name: str
```

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `tasks` | tasks | — | removed |
| `count` | len(tasks) | — | removed |
| `task_id` | — | str | added |
| `status` | — | str | added |
| `accepted_at` | — | datetime | added |
| `completed_at` | — | datetime \| None / None | added |
| `duration_ms` | — | int \| None / None | added |
| `execution_mode` | — | str | added |
| `adapter_name` | — | str | added |
| `model` | — | ModelView \| None / None | added |
| `dry_run` | — | bool | added |
| `model_count` | — | int | added |
| `requested_models` | — | list[ModelView] | added |
| `cancelled_step_count` | — | int / 0 | added |
| `cancel_reason` | — | str \| None / None | added |
| `failure_code` | — | str \| None / None | added |
| `failure_message` | — | str \| None / None | added |

### Curl examples
```bash
# Orchestrator2
curl -X GET "http://127.0.0.1:8001/api/tasks/"

# GraceKelly
curl -X GET "http://127.0.0.1:8011/api/v1/tasks?limit=1&status=example&execution_mode=example&dry_run=False&failure_code=example&before=example&prompt_contains=example"
```

### Classification
breaking
GraceKelly поддерживает фильтрацию и rich task summaries, а Orchestrator2 отдаёт упрощённый `{count,tasks}` список.

## GET /api/v1/tasks/{task_id}
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/tasks.py:259-282`
```python
# no request body; path/query parameters
task_id: str  # path
```

### GraceKelly request schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/orchestrate.py:680-715`
```python
# no request body; path/query parameters
task_id: str = Path(pattern=_UUID_PATTERN)  # path
events_limit: int | None = Query(default=None, ge=1, le=1000)  # query
events_offset: int = Query(default=0, ge=0)  # query
```

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `task_id` | str | str / Path(pattern=_UUID_PATTERN) | default-changed |
| `events_limit` | — | int \| None / Query(default=None, ge=1, le=1000) | added |
| `events_offset` | — | int / Query(default=0, ge=0) | added |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/tasks.py:32-38`
```python
class TaskStatusResponse(BaseModel):
    """Response with task status."""
    task_id: str
    name: str
    status: str
    progress: dict
    subtasks: List[dict]
```

### GraceKelly response schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/orchestrate.py:680-715`
```python
TaskView
```

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `task_id` | str | — | removed |
| `name` | str | — | removed |
| `status` | str | — | removed |
| `progress` | dict | — | removed |
| `subtasks` | List[dict] | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X GET "http://127.0.0.1:8001/api/tasks/00000000-0000-0000-0000-000000000000?task_id=00000000-0000-0000-0000-000000000000"

# GraceKelly
curl -X GET "http://127.0.0.1:8011/api/v1/tasks/00000000-0000-0000-0000-000000000000?events_limit=1&events_offset=1"
```

### Classification
breaking
GraceKelly возвращает полный task snapshot со steps/events, Orchestrator2 — компактный status/progress model.

## POST /api/v1/batch
### Orchestrator2 request schema
— (not present in this project)

### GraceKelly request schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/batch.py:29-34`
```python
class BatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompts: list[_Prompt] = Field(min_length=1, max_length=20)
    model: str = Field(default="claude-sonnet-4-6", min_length=1, max_length=120)
    dry_run: bool = Field(default=False)
```

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `prompts` | — | list[_Prompt] / Field(min_length=1, max_length=20) | added |
| `model` | — | str / Field(default='claude-sonnet-4-6', min_length=1, max_length=120) | added |
| `dry_run` | — | bool / Field(default=False) | added |

### Orchestrator2 response schema
— (not present in this project)

### GraceKelly response schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/batch.py:43-47, D:/GraceKelly/src/gracekelly/api/routes/batch.py:37-40`
```python
class BatchResponse(BaseModel):
    results: list[BatchItemResponse]
    total: int
    succeeded: int
    failed: int

class BatchItemResponse(BaseModel):
    prompt: str
    answer: str
    status: str
```

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `results` | — | list[BatchItemResponse] | added |
| `total` | — | int | added |
| `succeeded` | — | int | added |
| `failed` | — | int | added |

### Curl examples
```bash
# Orchestrator2
— (not present in this project)

# GraceKelly
curl -X POST "http://127.0.0.1:8011/api/v1/batch" -H "Content-Type: application/json" -d '{"prompts": []}'
```

### Classification
gracekelly-only
В Orchestrator2 нет прямого HTTP counterpart с сопоставимым contract surface.

## POST /api/v1/compare
### Orchestrator2 request schema
— (not present in this project)

### GraceKelly request schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/compare.py:26-32`
```python
class CompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=40000)
    models: list[str] = Field(default_factory=lambda: ["claude-sonnet-4-6"], min_length=1, max_length=10)
    analyze: bool = Field(default=True)
    dry_run: bool = Field(default=False)
```

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `prompt` | — | str / Field(min_length=1, max_length=40000) | added |
| `models` | — | list[str] / Field(default_factory=lambda: ['claude-sonnet-4-6'], min_length=1, max_length=10) | added |
| `analyze` | — | bool / Field(default=True) | added |
| `dry_run` | — | bool / Field(default=False) | added |

### Orchestrator2 response schema
— (not present in this project)

### GraceKelly response schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/compare.py:41-46, D:/GraceKelly/src/gracekelly/api/routes/compare.py:35-38`
```python
class CompareResponse(BaseModel):
    answers: list[ModelAnswer]
    analysis: str | None
    total_models: int
    succeeded: int
    failed: int

class ModelAnswer(BaseModel):
    model_id: str
    answer: str
    status: str
```

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `answers` | — | list[ModelAnswer] | added |
| `analysis` | — | str \| None | added |
| `total_models` | — | int | added |
| `succeeded` | — | int | added |
| `failed` | — | int | added |

### Curl examples
```bash
# Orchestrator2
— (not present in this project)

# GraceKelly
curl -X POST "http://127.0.0.1:8011/api/v1/compare" -H "Content-Type: application/json" -d '{"prompt": "Example prompt"}'
```

### Classification
gracekelly-only
В Orchestrator2 нет прямого HTTP counterpart с сопоставимым contract surface.

## POST /api/v1/consensus
### Orchestrator2 request schema
— (not present in this project)

### GraceKelly request schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/consensus.py:27-37`
```python
class ConsensusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=40000)
    model: str = Field(default="claude-sonnet-4-6", min_length=1, max_length=120)
    similarity_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    consensus_target: float = Field(default=0.95, ge=0.0, le=1.0)
    max_rounds: int = Field(default=5, ge=1, le=20)
    variations_per_round: int = Field(default=3, ge=1, le=9)
    use_confidence_weighting: bool = True
    dry_run: bool = Field(default=False)
```

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `prompt` | — | str / Field(min_length=1, max_length=40000) | added |
| `model` | — | str / Field(default='claude-sonnet-4-6', min_length=1, max_length=120) | added |
| `similarity_threshold` | — | float / Field(default=0.85, ge=0.0, le=1.0) | added |
| `consensus_target` | — | float / Field(default=0.95, ge=0.0, le=1.0) | added |
| `max_rounds` | — | int / Field(default=5, ge=1, le=20) | added |
| `variations_per_round` | — | int / Field(default=3, ge=1, le=9) | added |
| `use_confidence_weighting` | — | bool / True | added |
| `dry_run` | — | bool / Field(default=False) | added |

### Orchestrator2 response schema
— (not present in this project)

### GraceKelly response schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/consensus.py:40-48`
```python
class ConsensusResponse(BaseModel):
    consensus_score: float
    num_clusters: int
    best_response: str
    weighted_score: float | None
    total_rounds: int
    total_llm_calls: int
    needs_debate: bool
    top_cluster_size: int
```

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `consensus_score` | — | float | added |
| `num_clusters` | — | int | added |
| `best_response` | — | str | added |
| `weighted_score` | — | float \| None | added |
| `total_rounds` | — | int | added |
| `total_llm_calls` | — | int | added |
| `needs_debate` | — | bool | added |
| `top_cluster_size` | — | int | added |

### Curl examples
```bash
# Orchestrator2
— (not present in this project)

# GraceKelly
curl -X POST "http://127.0.0.1:8011/api/v1/consensus" -H "Content-Type: application/json" -d '{"prompt": "Example prompt"}'
```

### Classification
gracekelly-only
В Orchestrator2 нет прямого HTTP counterpart с сопоставимым contract surface.

## POST /api/v1/debate
### Orchestrator2 request schema
— (not present in this project)

### GraceKelly request schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/debate.py:28-34`
```python
class DebateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1, max_length=40000)
    initial_position: str | None = Field(default=None, max_length=40000)
    model: str = Field(default="claude-sonnet-4-6", min_length=1, max_length=120)
    dry_run: bool = Field(default=False)
```

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `topic` | — | str / Field(min_length=1, max_length=40000) | added |
| `initial_position` | — | str \| None / Field(default=None, max_length=40000) | added |
| `model` | — | str / Field(default='claude-sonnet-4-6', min_length=1, max_length=120) | added |
| `dry_run` | — | bool / Field(default=False) | added |

### Orchestrator2 response schema
— (not present in this project)

### GraceKelly response schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/debate.py:37-43`
```python
class DebateResponse(BaseModel):
    initial_position: str
    challenge: str
    defense: str
    improved_response: str
    model_id: str
    total_llm_calls: int
```

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `initial_position` | — | str | added |
| `challenge` | — | str | added |
| `defense` | — | str | added |
| `improved_response` | — | str | added |
| `model_id` | — | str | added |
| `total_llm_calls` | — | int | added |

### Curl examples
```bash
# Orchestrator2
— (not present in this project)

# GraceKelly
curl -X POST "http://127.0.0.1:8011/api/v1/debate" -H "Content-Type: application/json" -d '{"topic": "Example prompt"}'
```

### Classification
gracekelly-only
В Orchestrator2 нет прямого HTTP counterpart с сопоставимым contract surface.

## GET /healthz/live
### Orchestrator2 request schema
— (not present in this project)

### GraceKelly request schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/health.py:375-376`
```python
— (no request body)
```

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| — | no request body | no request body | identical |

### Orchestrator2 response schema
— (not present in this project)

### GraceKelly response schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/health.py:376`
```python
{"status": "ok"}
```

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `status` | — | 'ok' | added |

### Curl examples
```bash
# Orchestrator2
— (not present in this project)

# GraceKelly
curl -X GET "http://127.0.0.1:8011/healthz/live"
```

### Classification
gracekelly-only
В Orchestrator2 нет прямого HTTP counterpart с сопоставимым contract surface.

## GET /healthz/ready
### Orchestrator2 request schema
— (not present in this project)

### GraceKelly request schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/health.py:380-389`
```python
— (no request body)
```

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| — | no request body | no request body | identical |

### Orchestrator2 response schema
— (not present in this project)

### GraceKelly response schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/health.py:389`
```python
{"status": "ok"}
```

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `status` | — | 'ok' | added |

### Curl examples
```bash
# Orchestrator2
— (not present in this project)

# GraceKelly
curl -X GET "http://127.0.0.1:8011/healthz/ready"
```

### Classification
gracekelly-only
В Orchestrator2 нет прямого HTTP counterpart с сопоставимым contract surface.

## GET /api/v1/readiness
### Orchestrator2 request schema
— (not present in this project)

### GraceKelly request schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/health.py:393-412`
```python
— (no request body)
```

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| — | no request body | no request body | identical |

### Orchestrator2 response schema
— (not present in this project)

### GraceKelly response schema
Source: `D:/GraceKelly/src/gracekelly/core/readiness.py:24-53`
```python
return {
    "status": overall_status,
    "environment": environment,
    "execution_profile": profile.name,
    "components": components,
}
```

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `status` | — | str | added |
| `environment` | — | str | added |
| `execution_profile` | — | str | added |
| `components` | — | list[dict[str, Any]] | added |

### Curl examples
```bash
# Orchestrator2
— (not present in this project)

# GraceKelly
curl -X GET "http://127.0.0.1:8011/api/v1/readiness"
```

### Classification
gracekelly-only
В Orchestrator2 нет прямого HTTP counterpart с сопоставимым contract surface.

## GET /metrics
### Orchestrator2 request schema
— (not present in this project)

### GraceKelly request schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/health.py:416-428`
```python
— (no request body)
```

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| — | no request body | no request body | identical |

### Orchestrator2 response schema
— (not present in this project)

### GraceKelly response schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/health.py:110-313`
```python
text/plain; version=0.0.4; charset=utf-8
# Prometheus exposition produced by _build_metrics_payload()
# Includes readiness, component, execution, storage, browser, and request metrics series.
```

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `body` | — | text/plain; version=0.0.4; charset=utf-8 | added |

### Curl examples
```bash
# Orchestrator2
— (not present in this project)

# GraceKelly
curl -X GET "http://127.0.0.1:8011/metrics"
```

### Classification
gracekelly-only
В Orchestrator2 нет прямого HTTP counterpart с сопоставимым contract surface.

## GET /api/v1/health/detailed
### Orchestrator2 request schema
— (not present in this project)

### GraceKelly request schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/health_detailed.py:43-71`
```python
— (no request body)
```

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| — | no request body | no request body | identical |

### Orchestrator2 response schema
— (not present in this project)

### GraceKelly response schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/health_detailed.py:24-29, D:/GraceKelly/src/gracekelly/api/routes/health_detailed.py:14-16, D:/GraceKelly/src/gracekelly/api/routes/health_detailed.py:19-21`
```python
class DetailedHealthResponse(BaseModel):
    status: str
    uptime_seconds: int
    adapters: list[AdapterStatus]
    embeddings: EmbeddingsStatus
    total_adapters: int

class AdapterStatus(BaseModel):
    name: str
    status: str

class EmbeddingsStatus(BaseModel):
    status: str
    cache_size: int
```

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `status` | — | str | added |
| `uptime_seconds` | — | int | added |
| `adapters` | — | list[AdapterStatus] | added |
| `embeddings` | — | EmbeddingsStatus | added |
| `total_adapters` | — | int | added |

### Curl examples
```bash
# Orchestrator2
— (not present in this project)

# GraceKelly
curl -X GET "http://127.0.0.1:8011/api/v1/health/detailed"
```

### Classification
gracekelly-only
В Orchestrator2 нет прямого HTTP counterpart с сопоставимым contract surface.

## GET /api/v1/models
### Orchestrator2 request schema
— (not present in this project)

### GraceKelly request schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/models.py:177-190`
```python
— (no request body)
```

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| — | no request body | no request body | identical |

### Orchestrator2 response schema
— (not present in this project)

### GraceKelly response schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/models.py:130-164, D:/GraceKelly/src/gracekelly/schemas.py:54-67`
```python
return {
    "last_checked": snapshot.checked_at,
    "source": snapshot.source,
    "models": [item.model_dump() for item in catalog],
}

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
```

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `last_checked` | — | datetime | added |
| `source` | — | str | added |
| `models` | — | list[ModelCatalogItem] | added |

### Curl examples
```bash
# Orchestrator2
— (not present in this project)

# GraceKelly
curl -X GET "http://127.0.0.1:8011/api/v1/models"
```

### Classification
gracekelly-only
В Orchestrator2 нет прямого HTTP counterpart с сопоставимым contract surface.

## POST /api/v1/models/refresh
### Orchestrator2 request schema
— (not present in this project)

### GraceKelly request schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/models.py:202-217`
```python
— (no request body)
```

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| — | no request body | no request body | identical |

### Orchestrator2 response schema
— (not present in this project)

### GraceKelly response schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/models.py:130-164, D:/GraceKelly/src/gracekelly/api/routes/models.py:202-217, D:/GraceKelly/src/gracekelly/schemas.py:54-67`
```python
payload = {
    "last_checked": snapshot.checked_at,
    "source": snapshot.source,
    "models": [item.model_dump() for item in catalog],
}
payload["refreshed_at"] = datetime.now(UTC).isoformat()
```

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `last_checked` | — | datetime | added |
| `source` | — | str | added |
| `models` | — | list[ModelCatalogItem] | added |
| `refreshed_at` | — | str | added |

### Curl examples
```bash
# Orchestrator2
— (not present in this project)

# GraceKelly
curl -X POST "http://127.0.0.1:8011/api/v1/models/refresh"
```

### Classification
gracekelly-only
В Orchestrator2 нет прямого HTTP counterpart с сопоставимым contract surface.

## POST /api/v1/orchestrate/upload
### Orchestrator2 request schema
— (not present in this project)

### GraceKelly request schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/orchestrate.py:399-590`
```python
# request fields from handler signature
prompt: str = Form(...)  # form
model: str | None = Form(default=None)  # form
models: str | None = Form(default=None)  # form
session_id: str | None = Form(default=None)  # form
dry_run: bool = Form(default=False)  # form
files: list[UploadFile] | None = File(default=None)  # file
```

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `prompt` | — | str / Form(...) | added |
| `model` | — | str \| None / Form(default=None) | added |
| `models` | — | str \| None / Form(default=None) | added |
| `session_id` | — | str \| None / Form(default=None) | added |
| `dry_run` | — | bool / Form(default=False) | added |
| `files` | — | list[UploadFile] \| None / File(default=None) | added |

### Orchestrator2 response schema
— (not present in this project)

### GraceKelly response schema
Source: `D:/GraceKelly/src/gracekelly/schemas.py:133-174, D:/GraceKelly/src/gracekelly/schemas.py:49-51`
```python
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
    was_decomposed: bool = False
    subtask_count: int = 0

    @classmethod
    def from_task(
        cls,
        task: TaskRecord,
        steps: list[TaskStepRecord] | None = None,
        events: list[TaskEventRecord] | None = None,
        requested_models_override: list[ModelView] | None = None,
    ) -> OrchestrateResponse:
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
            was_decomposed=task.was_decomposed,
            subtask_count=task.subtask_count,
        )

class ModelView(BaseModel):
    id: str
    display_name: str
```

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `task_id` | — | str | added |
| `status` | — | str | added |
| `accepted_at` | — | datetime | added |
| `completed_at` | — | datetime \| None / None | added |
| `duration_ms` | — | int \| None / None | added |
| `execution_mode` | — | str | added |
| `adapter_name` | — | str | added |
| `failure_code` | — | str \| None / None | added |
| `failure_message` | — | str \| None / None | added |
| `model` | — | ModelView \| None / None | added |
| `requested_models` | — | list[ModelView] | added |
| `output_text` | — | str \| None / None | added |
| `was_decomposed` | — | bool / False | added |
| `subtask_count` | — | int / 0 | added |

### Curl examples
```bash
# Orchestrator2
— (not present in this project)

# GraceKelly
curl -X POST "http://127.0.0.1:8011/api/v1/orchestrate/upload" \
  -F "prompt=Example prompt" \
  -F "model=claude-sonnet-4-6" \
  -F "files=@sample.txt;type=text/plain"
```

### Classification
gracekelly-only
В Orchestrator2 нет прямого HTTP counterpart с сопоставимым contract surface.

## GET /api/v1/tasks/{task_id}/export
### Orchestrator2 request schema
— (not present in this project)

### GraceKelly request schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/orchestrate.py:728-739`
```python
# no request body; path/query parameters
task_id: str = Path(pattern=_UUID_PATTERN)  # path
```

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `task_id` | — | str / Path(pattern=_UUID_PATTERN) | added |

### Orchestrator2 response schema
— (not present in this project)

### GraceKelly response schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/orchestrate.py:159-178, D:/GraceKelly/src/gracekelly/api/routes/orchestrate.py:728-739`
```python
text/markdown; charset=utf-8
---
task_id: <uuid>
status: <status>
accepted_at: <iso-datetime>
duration_ms: <int>
model_count: <int>
dry_run: <bool>
---

## Prompt
<original prompt>

## Output
<output_text | _No output returned._>
```

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `body` | — | text/markdown; charset=utf-8 | added |

### Curl examples
```bash
# Orchestrator2
— (not present in this project)

# GraceKelly
curl -X GET "http://127.0.0.1:8011/api/v1/tasks/00000000-0000-0000-0000-000000000000/export"
```

### Classification
gracekelly-only
В Orchestrator2 нет прямого HTTP counterpart с сопоставимым contract surface.

## POST /api/v1/tasks/{task_id}/retry
### Orchestrator2 request schema
— (not present in this project)

### GraceKelly request schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/orchestrate.py:760-813`
```python
# request fields from handler signature
task_id: str = Path(pattern=_UUID_PATTERN)  # path
```

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `task_id` | — | str / Path(pattern=_UUID_PATTERN) | added |

### Orchestrator2 response schema
— (not present in this project)

### GraceKelly response schema
Source: `D:/GraceKelly/src/gracekelly/schemas.py:133-174, D:/GraceKelly/src/gracekelly/schemas.py:49-51`
```python
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
    was_decomposed: bool = False
    subtask_count: int = 0

    @classmethod
    def from_task(
        cls,
        task: TaskRecord,
        steps: list[TaskStepRecord] | None = None,
        events: list[TaskEventRecord] | None = None,
        requested_models_override: list[ModelView] | None = None,
    ) -> OrchestrateResponse:
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
            was_decomposed=task.was_decomposed,
            subtask_count=task.subtask_count,
        )

class ModelView(BaseModel):
    id: str
    display_name: str
```

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `task_id` | — | str | added |
| `status` | — | str | added |
| `accepted_at` | — | datetime | added |
| `completed_at` | — | datetime \| None / None | added |
| `duration_ms` | — | int \| None / None | added |
| `execution_mode` | — | str | added |
| `adapter_name` | — | str | added |
| `failure_code` | — | str \| None / None | added |
| `failure_message` | — | str \| None / None | added |
| `model` | — | ModelView \| None / None | added |
| `requested_models` | — | list[ModelView] | added |
| `output_text` | — | str \| None / None | added |
| `was_decomposed` | — | bool / False | added |
| `subtask_count` | — | int / 0 | added |

### Curl examples
```bash
# Orchestrator2
— (not present in this project)

# GraceKelly
curl -X POST "http://127.0.0.1:8011/api/v1/tasks/00000000-0000-0000-0000-000000000000/retry?task_id=00000000-0000-0000-0000-000000000000"
```

### Classification
gracekelly-only
В Orchestrator2 нет прямого HTTP counterpart с сопоставимым contract surface.

## POST /api/v1/pipeline
### Orchestrator2 request schema
— (not present in this project)

### GraceKelly request schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/pipeline.py:32-39`
```python
class PipelineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=40000)
    model: str = Field(default="claude-sonnet-4-6", min_length=1, max_length=120)
    reliability_level: str | None = Field(default=None)
    multi_model: bool = Field(default=False)
    dry_run: bool = Field(default=False)
```

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `prompt` | — | str / Field(min_length=1, max_length=40000) | added |
| `model` | — | str / Field(default='claude-sonnet-4-6', min_length=1, max_length=120) | added |
| `reliability_level` | — | str \| None / Field(default=None) | added |
| `multi_model` | — | bool / Field(default=False) | added |
| `dry_run` | — | bool / Field(default=False) | added |

### Orchestrator2 response schema
— (not present in this project)

### GraceKelly response schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/pipeline.py:42-49`
```python
class PipelineResponse(BaseModel):
    answer: str
    task_type: str
    pattern_used: str
    reliability_level: str
    total_llm_calls: int
    model_id: str
    models_used: list[str] = Field(default_factory=list)
```

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `answer` | — | str | added |
| `task_type` | — | str | added |
| `pattern_used` | — | str | added |
| `reliability_level` | — | str | added |
| `total_llm_calls` | — | int | added |
| `model_id` | — | str | added |
| `models_used` | — | list[str] / Field(default_factory=list) | added |

### Curl examples
```bash
# Orchestrator2
— (not present in this project)

# GraceKelly
curl -X POST "http://127.0.0.1:8011/api/v1/pipeline" -H "Content-Type: application/json" -d '{"prompt": "Example prompt"}'
```

### Classification
gracekelly-only
В Orchestrator2 нет прямого HTTP counterpart с сопоставимым contract surface.

## POST /api/v1/smart
### Orchestrator2 request schema
— (not present in this project)

### GraceKelly request schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/smart.py:36-43`
```python
class SmartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=40000)
    model: str = Field(default="claude-sonnet-4-6", min_length=1, max_length=120)
    reliability_level: str | None = Field(default=None)
    pattern: str | None = Field(default=None)
    dry_run: bool = Field(default=False)
```

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `prompt` | — | str / Field(min_length=1, max_length=40000) | added |
| `model` | — | str / Field(default='claude-sonnet-4-6', min_length=1, max_length=120) | added |
| `reliability_level` | — | str \| None / Field(default=None) | added |
| `pattern` | — | str \| None / Field(default=None) | added |
| `dry_run` | — | bool / Field(default=False) | added |

### Orchestrator2 response schema
— (not present in this project)

### GraceKelly response schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/smart.py:46-56`
```python
class SmartResponse(BaseModel):
    answer: str
    task_type: str
    complexity_level: str
    pattern_used: str
    reliability_level: str
    was_decomposed: bool
    used_consensus: bool
    used_roles: bool
    total_llm_calls: int
    model_id: str
```

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `answer` | — | str | added |
| `task_type` | — | str | added |
| `complexity_level` | — | str | added |
| `pattern_used` | — | str | added |
| `reliability_level` | — | str | added |
| `was_decomposed` | — | bool | added |
| `used_consensus` | — | bool | added |
| `used_roles` | — | bool | added |
| `total_llm_calls` | — | int | added |
| `model_id` | — | str | added |

### Curl examples
```bash
# Orchestrator2
— (not present in this project)

# GraceKelly
curl -X POST "http://127.0.0.1:8011/api/v1/smart" -H "Content-Type: application/json" -d '{"prompt": "Example prompt"}'
```

### Classification
gracekelly-only
В Orchestrator2 нет прямого HTTP counterpart с сопоставимым contract surface.

## POST /api/v1/smart/v2
### Orchestrator2 request schema
— (not present in this project)

### GraceKelly request schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/smart_v2.py:36-43`
```python
class SmartV2Request(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1, max_length=40000)
    model: str = Field(default="claude-sonnet-4-6", min_length=1, max_length=120)
    reliability_level: str | None = Field(default=None)
    pattern: str | None = Field(default=None)
    dry_run: bool = Field(default=False)
```

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `prompt` | — | str / Field(min_length=1, max_length=40000) | added |
| `model` | — | str / Field(default='claude-sonnet-4-6', min_length=1, max_length=120) | added |
| `reliability_level` | — | str \| None / Field(default=None) | added |
| `pattern` | — | str \| None / Field(default=None) | added |
| `dry_run` | — | bool / Field(default=False) | added |

### Orchestrator2 response schema
— (not present in this project)

### GraceKelly response schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/smart_v2.py:51-65, D:/GraceKelly/src/gracekelly/api/routes/smart_v2.py:46-48`
```python
class SmartV2Response(BaseModel):
    answer: str
    task_type: str
    complexity_level: str
    pattern_used: str
    reliability_level: str
    was_decomposed: bool
    used_consensus: bool
    used_roles: bool
    total_llm_calls: int
    model_id: str
    consensus_status: str | None
    consensus_score: float | None
    cluster_confidence: float | None
    dissenting_views: list[DissentingViewResponse]

class DissentingViewResponse(BaseModel):
    perspective: str
    support_ratio: float
```

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `answer` | — | str | added |
| `task_type` | — | str | added |
| `complexity_level` | — | str | added |
| `pattern_used` | — | str | added |
| `reliability_level` | — | str | added |
| `was_decomposed` | — | bool | added |
| `used_consensus` | — | bool | added |
| `used_roles` | — | bool | added |
| `total_llm_calls` | — | int | added |
| `model_id` | — | str | added |
| `consensus_status` | — | str \| None | added |
| `consensus_score` | — | float \| None | added |
| `cluster_confidence` | — | float \| None | added |
| `dissenting_views` | — | list[DissentingViewResponse] | added |

### Curl examples
```bash
# Orchestrator2
— (not present in this project)

# GraceKelly
curl -X POST "http://127.0.0.1:8011/api/v1/smart/v2" -H "Content-Type: application/json" -d '{"prompt": "Example prompt"}'
```

### Classification
gracekelly-only
В Orchestrator2 нет прямого HTTP counterpart с сопоставимым contract surface.

## POST /api/v1/orchestrate/stream
### Orchestrator2 request schema
— (not present in this project)

### GraceKelly request schema
Source: `D:/GraceKelly/src/gracekelly/schemas.py:14-46`
```python
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
    dry_run: bool = False
    decompose: bool = Field(
        default=True,
        description="Enable automatic decomposition for complex prompts",
    )
    session_id: str | None = Field(default=None, description="Session ID for conversation chaining")

    @model_validator(mode="after")
    def validate_model_selection(self) -> OrchestrateRequest:
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
```

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `prompt` | — | str / Field(min_length=1, max_length=40000) | added |
| `model` | — | str \| None / Field(default=None, min_length=1, max_length=120) | added |
| `models` | — | list[str] / Field(default_factory=list, max_length=8) | added |
| `adapter_hint` | — | AdapterHint / AdapterHint.AUTO | added |
| `quorum` | — | int / Field(default=1, ge=1, le=8) | added |
| `merge_strategy` | — | MergeStrategy / MergeStrategy.FIRST_SUCCESS | added |
| `cancel_on_quorum` | — | bool / True | added |
| `reasoning` | — | bool / False | added |
| `metadata` | — | dict[str, Any] / Field(default_factory=dict) | added |
| `dry_run` | — | bool / False | added |
| `decompose` | — | bool / Field(default=True, description='Enable automatic decomposition for complex prompts') | added |
| `session_id` | — | str \| None / Field(default=None, description='Session ID for conversation chaining') | added |

### Orchestrator2 response schema
— (not present in this project)

### GraceKelly response schema
Source: `D:/GraceKelly/src/gracekelly/api/routes/stream.py:34-284`
```python
text/event-stream
accepted: {"model_id": str, "task_id": str}
complete: {"text": str, "model_id": str, "duration_ms": int | None, "task_id": str, "input_tokens": int | None, "output_tokens": int | None}
error: {"text": str}
```

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `events[]` | — | accepted \| complete \| error (SSE) | added |

### Curl examples
```bash
# Orchestrator2
— (not present in this project)

# GraceKelly
curl -N -X POST "http://127.0.0.1:8011/api/v1/orchestrate/stream" -H "Content-Type: application/json" -d '{"prompt": "Example prompt", "model": "claude-sonnet-4-6"}'
```

### Classification
gracekelly-only
В Orchestrator2 нет прямого HTTP counterpart с сопоставимым contract surface.

## GET /accounts
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/accounts.py:41-68`
```python
— (no request body)
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| — | no request body | no request body | identical |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/accounts.py:32-37, D:/Perplexity_Orchestrator2/api/routes/accounts.py:23-29`
```python
class AccountsListResponse(BaseModel):
    """List of accounts response."""
    accounts: List[AccountResponse]
    total: int
    with_sessions: int
    needing_login: int

class AccountResponse(BaseModel):
    """Account response model."""
    id: str
    email: str
    status: str
    requests_count: int
    has_session: bool
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `accounts` | List[AccountResponse] | — | removed |
| `total` | int | — | removed |
| `with_sessions` | int | — | removed |
| `needing_login` | int | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X GET "http://127.0.0.1:8001/accounts"

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## GET /accounts/{account_id}
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/accounts.py:72-86`
```python
# no request body; path/query parameters
account_id: str  # path
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `account_id` | str | — | removed |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/accounts.py:78`
```python
{"error": f"Account {account_id} not found"}
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `error` | f'Account {account_id} not found' | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X GET "http://127.0.0.1:8001/accounts/acc-001?account_id=example"

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## GET /accounts/needing-login
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/accounts.py:90-101`
```python
— (no request body)
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| — | no request body | no request body | identical |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/accounts.py:95`
```python
{
        "count": len(needing),
        "accounts": [
            {"id": acc.id, "email": acc.email}
            for acc in needing
        ]
    }
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `count` | len(needing) | — | removed |
| `accounts` | [{'id': acc.id, 'email': acc.email} for acc in needing] | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X GET "http://127.0.0.1:8001/accounts/needing-login"

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## GET /api/analytics/models
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/analytics.py:107-150`
```python
— (no request body)
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| — | no request body | no request body | identical |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/analytics.py:141`
```python
{
            "timestamp": datetime.now().isoformat(),
            "models": models
        }
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `timestamp` | datetime.now().isoformat() | — | removed |
| `models` | models | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X GET "http://127.0.0.1:8001/api/analytics/models"

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## GET /api/analytics/accounts
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/analytics.py:154-204`
```python
— (no request body)
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| — | no request body | no request body | identical |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/analytics.py:190`
```python
{
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total": len(accounts),
                "active": active_count,
                "cooldown": len(accounts) - active_count
            },
            "accounts": accounts
        }
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `timestamp` | datetime.now().isoformat() | — | removed |
| `summary` | {'total': len(accounts), 'active': active_count, 'cooldown': len(accounts) - active_count} | — | removed |
| `accounts` | accounts | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X GET "http://127.0.0.1:8001/api/analytics/accounts"

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## GET /api/analytics/trends
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/analytics.py:208-246`
```python
# no request body; path/query parameters
days: int = 7  # body
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `days` | int / 7 | — | removed |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/analytics.py:236`
```python
{
            "timestamp": datetime.now().isoformat(),
            "period_days": days,
            "daily_data": daily_data
        }
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `timestamp` | datetime.now().isoformat() | — | removed |
| `period_days` | days | — | removed |
| `daily_data` | daily_data | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X GET "http://127.0.0.1:8001/api/analytics/trends"

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## POST /api/conversation/create
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/conversation.py:28-34`
```python
# request fields from handler signature
task: Optional[str] = None  # body
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `task` | Optional[str] / None | — | removed |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/conversation.py:21-24`
```python
class CreateConversationResponse(BaseModel):
    """Response with conversation ID."""
    conversation_id: str
    status: str = "created"
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `conversation_id` | str | — | removed |
| `status` | str / 'created' | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X POST "http://127.0.0.1:8001/api/conversation/create" -H "Content-Type: application/json" -d '{"task": "Example prompt"}'

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## GET /api/conversation/{conv_id}
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/conversation.py:38-52`
```python
# no request body; path/query parameters
conv_id: str  # path
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `conv_id` | str | — | removed |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/conversation.py:44`
```python
{
        "id": conv.id,
        "status": conv.status,
        "task": conv.task,
        "message_count": len(conv.messages),
        "created_at": conv.created_at.isoformat(),
        "has_pending_question": conv.pending_question is not None,
        "pending_question": conv.pending_question.to_dict() if conv.pending_question else None
    }
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `id` | conv.id | — | removed |
| `status` | conv.status | — | removed |
| `task` | conv.task | — | removed |
| `message_count` | len(conv.messages) | — | removed |
| `created_at` | conv.created_at.isoformat() | — | removed |
| `has_pending_question` | conv.pending_question is not None | — | removed |
| `pending_question` | conv.pending_question.to_dict() if conv.pending_question else None | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X GET "http://127.0.0.1:8001/api/conversation/00000000-0000-0000-0000-000000000000?conv_id=00000000-0000-0000-0000-000000000000"

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## GET /api/conversation/{conv_id}/messages
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/conversation.py:56-67`
```python
# no request body; path/query parameters
conv_id: str  # path
limit: int = 50  # body
offset: int = 0  # body
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `conv_id` | str | — | removed |
| `limit` | int / 50 | — | removed |
| `offset` | int / 0 | — | removed |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/conversation.py:63`
```python
{
        "conversation_id": conv_id,
        "messages": [m.to_dict() for m in messages],
        "total": len(conv.messages)
    }
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `conversation_id` | conv_id | — | removed |
| `messages` | [m.to_dict() for m in messages] | — | removed |
| `total` | len(conv.messages) | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X GET "http://127.0.0.1:8001/api/conversation/00000000-0000-0000-0000-000000000000/messages?conv_id=00000000-0000-0000-0000-000000000000"

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## POST /api/conversation/{conv_id}/answer
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/conversation.py:16-18`
```python
class AnswerRequest(BaseModel):
    """Request to submit an answer."""
    answer: str
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `answer` | str | — | removed |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/conversation.py:81`
```python
{"status": "ok", "answer": data.answer}
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `status` | 'ok' | — | removed |
| `answer` | data.answer | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X POST "http://127.0.0.1:8001/api/conversation/00000000-0000-0000-0000-000000000000/answer" -H "Content-Type: application/json" -d '{"answer": "Example answer"}'

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## GET /api/debate/latest
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/debate.py:19-50`
```python
— (no request body)
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| — | no request body | no request body | identical |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/juhub/frontend/debate_data.json:1, D:/Perplexity_Orchestrator2/api/routes/debate.py:18-39`
```python
{
  "date": "YYYY-MM-DD",
  "generated_at": "HH:MM",
  "questions": [
    {
      "id": str,
      "text": str,
      "votes": object,
      "arguments": object,
    }
  ]
}
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `date` | str | — | removed |
| `generated_at` | str | — | removed |
| `questions` | list[dict] | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X GET "http://127.0.0.1:8001/api/debate/latest"

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## GET /api/debate/health
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/debate.py:54-84`
```python
— (no request body)
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| — | no request body | no request body | identical |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/debate.py:62, D:/Perplexity_Orchestrator2/api/routes/debate.py:72, D:/Perplexity_Orchestrator2/api/routes/debate.py:80`
```python
{
            "status": "no_data",
            "message": "No debate data available. Run scheduler to generate.",
            "path": str(DEBATE_DATA_PATH)
        }

{
            "status": "ok",
            "date": data.get("date"),
            "generated_at": data.get("generated_at"),
            "questions_count": len(data.get("questions", [])),
            "path": str(DEBATE_DATA_PATH)
        }

{
            "status": "error",
            "message": str(e),
            "path": str(DEBATE_DATA_PATH)
        }
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `status` | 'no_data' | — | removed |
| `message` | 'No debate data available. Run scheduler to generate.' | — | removed |
| `path` | str(DEBATE_DATA_PATH) | — | removed |
| `date` | data.get('date') | — | removed |
| `generated_at` | data.get('generated_at') | — | removed |
| `questions_count` | len(data.get('questions', [])) | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X GET "http://127.0.0.1:8001/api/debate/health"

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## POST /api/english/respond
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/english.py:26-29`
```python
class ConversationRequest(BaseModel):
    message: str
    topic: str = "casual"
    history: List[dict] = []
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `message` | str | — | removed |
| `topic` | str / 'casual' | — | removed |
| `history` | List[dict] / [] | — | removed |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/english.py:32-33`
```python
class ConversationResponse(BaseModel):
    response: str
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `response` | str | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X POST "http://127.0.0.1:8001/api/english/respond" -H "Content-Type: application/json" -d '{"message": "Example prompt"}'

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## POST /api/english/analyze
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/english.py:36-37`
```python
class AnalysisRequest(BaseModel):
    responses: List[str]
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `responses` | List[str] | — | removed |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/english.py:40-41`
```python
class AnalysisResponse(BaseModel):
    analysis: str
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `analysis` | str | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X POST "http://127.0.0.1:8001/api/english/analyze" -H "Content-Type: application/json" -d '{"responses": ["example"]}'

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## GET /api/gk/patterns
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/gk_orchestrate.py:239-252`
```python
— (no request body)
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| — | no request body | no request body | identical |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/gk_orchestrate.py:241`
```python
{
        "patterns": [
            {"id": "best", "label": "Best (Perplexity)", "description": "Perplexity's own orchestration"},
            {"id": "sonar", "label": "Sonar (fast search)", "description": "No reasoning, max speed"},
            {"id": "single", "label": "1 model", "description": "With reasoning"},
            {"id": "dual", "label": "2 models", "description": "Reasoning + comparison"},
            {"id": "consensus", "label": "Consensus", "description": "4 models x 3 prompts, clustering"},
            {"id": "maximum", "label": "Maximum", "description": "Consensus + iteration until 95%"},
            {"id": "five_models", "label": "5 models (raw)", "description": "All 5 responses directly"},
            {"id": "five_models_compare", "label": "5 models (compare)", "description": "Agreement & differences"},
        ]
    }
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `patterns` | [{'id': 'best', 'label': 'Best (Perplexity)', 'description': "Perplexity's own orchestration"}, {'id': 'sonar', 'label': 'Sonar (fast search)', 'description': 'No reasoning, max speed'}, {'id': 'single', 'label': '1 model', 'description': 'With reasoning'}, {'id': 'dual', 'label': '2 models', 'description': 'Reasoning + comparison'}, {'id': 'consensus', 'label': 'Consensus', 'description': '4 models x 3 prompts, clustering'}, {'id': 'maximum', 'label': 'Maximum', 'description': 'Consensus + iteration until 95%'}, {'id': 'five_models', 'label': '5 models (raw)', 'description': 'All 5 responses directly'}, {'id': 'five_models_compare', 'label': '5 models (compare)', 'description': 'Agreement & differences'}] | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X GET "http://127.0.0.1:8001/api/gk/patterns"

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## GET /health/db
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/health.py:43-58`
```python
— (no request body)
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| — | no request body | no request body | identical |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/monitoring/sqlite_monitor.py:316-335`
```python
return {
    "timestamp": health.timestamp.isoformat(),
    "status": health.status,
    "metrics": {
        "db_size_mb": round(health.db_size_mb, 2),
        "total_records": health.total_records,
        "writes_per_minute": health.writes_last_minute,
        "avg_write_latency_ms": round(health.avg_write_latency_ms, 2),
    },
    "thresholds": {
        "db_size_warning_mb": self.thresholds.db_size_warning_mb,
        "db_size_critical_mb": self.thresholds.db_size_critical_mb,
        "writes_per_min_critical": self.thresholds.writes_per_min_critical,
    },
    "issues": health.issues,
    "needs_migration": health.status == "critical",
}
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `timestamp` | str | — | removed |
| `status` | str | — | removed |
| `metrics` | dict | — | removed |
| `thresholds` | dict | — | removed |
| `issues` | list[str] | — | removed |
| `needs_migration` | bool | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X GET "http://127.0.0.1:8001/health/db"

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## GET /api/interview/levels
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/interview.py:133-134`
```python
— (no request body)
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| — | no request body | no request body | identical |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/interview.py:40-71`
```python
[
  {
    "id": str,
    "en": str,
    "desc_en": str,
  }
]
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `items[]` | dict{id,en,desc_en} | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X GET "http://127.0.0.1:8001/api/interview/levels"

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## POST /api/interview/start
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/interview.py:80-83`
```python
class StartRequest(BaseModel):
    topic: str
    level: str
    count: int = 10
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `topic` | str | — | removed |
| `level` | str | — | removed |
| `count` | int / 10 | — | removed |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/interview.py:143, D:/Perplexity_Orchestrator2/api/routes/interview.py:160`
```python
{"valid": False, "reason": "Topic is empty"}

{"session_id": session_id, "status": "validating"}
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `valid` | False | — | removed |
| `reason` | 'Topic is empty' | — | removed |
| `session_id` | session_id | — | removed |
| `status` | 'validating' | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X POST "http://127.0.0.1:8001/api/interview/start" -H "Content-Type: application/json" -d '{"topic": "Example prompt", "level": "junior"}'

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## GET /api/interview/status/{session_id}
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/interview.py:164-175`
```python
# no request body; path/query parameters
session_id: str  # path
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `session_id` | str | — | removed |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/interview.py:167, D:/Perplexity_Orchestrator2/api/routes/interview.py:168`
```python
{"error": "Session not found"}

{
        "status": s["status"],
        "topic": s.get("refined_topic", s["topic"]),
        "progress": s["progress"],
        "total": s["count"],
        "ready": len(s["questions"]),
        "error": s.get("error"),
    }
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `error` | 'Session not found' | — | removed |
| `status` | s['status'] | — | removed |
| `topic` | s.get('refined_topic', s['topic']) | — | removed |
| `progress` | s['progress'] | — | removed |
| `total` | s['count'] | — | removed |
| `ready` | len(s['questions']) | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X GET "http://127.0.0.1:8001/api/interview/status/00000000-0000-0000-0000-000000000000?session_id=00000000-0000-0000-0000-000000000000"

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## GET /api/interview/question/{session_id}/{index}
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/interview.py:179-192`
```python
# no request body; path/query parameters
session_id: str  # path
index: int  # path
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `session_id` | str | — | removed |
| `index` | int | — | removed |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/interview.py:182, D:/Perplexity_Orchestrator2/api/routes/interview.py:184, D:/Perplexity_Orchestrator2/api/routes/interview.py:186`
```python
{"error": "Session not found"}

{"error": "Question not found"}

{
        "index": index,
        "total": s["count"],
        "topic": s.get("refined_topic", s["topic"]),
        "level": s["level"],
        **q,
    }
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `error` | 'Session not found' | — | removed |
| `index` | index | — | removed |
| `total` | s['count'] | — | removed |
| `topic` | s.get('refined_topic', s['topic']) | — | removed |
| `level` | s['level'] | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X GET "http://127.0.0.1:8001/api/interview/question/00000000-0000-0000-0000-000000000000/0?session_id=00000000-0000-0000-0000-000000000000&index=1"

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## POST /api/interview/evaluate
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/interview.py:86-89`
```python
class EvaluateRequest(BaseModel):
    session_id: str
    question_index: int
    answer: str
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `session_id` | str | — | removed |
| `question_index` | int | — | removed |
| `answer` | str | — | removed |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/interview.py:414-473, D:/Perplexity_Orchestrator2/api/routes/interview.py:195-216`
```python
result = {
    "score": score,
    "max_score": 10,
    "verdict": parsed.get("verdict", "—"),
    "strengths": parsed.get("strengths", []),
    "gaps": parsed.get("gaps", []),
    "ideal_answer_summary": parsed.get("ideal_answer_summary", ""),
}
result["follow_up"] = q.get("follow_up", "")
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `score` | int | — | removed |
| `max_score` | int / 10 | — | removed |
| `verdict` | str | — | removed |
| `strengths` | list[str] / [] | — | removed |
| `gaps` | list[str] / [] | — | removed |
| `ideal_answer_summary` | str | — | removed |
| `follow_up` | str / "" | — | removed |
| `error` | str | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X POST "http://127.0.0.1:8001/api/interview/evaluate" -H "Content-Type: application/json" -d '{"session_id": "00000000-0000-0000-0000-000000000000", "question_index": 1, "answer": "Example answer"}'

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## GET /api/interview/summary/{session_id}
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/interview.py:220-244`
```python
# no request body; path/query parameters
session_id: str  # path
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `session_id` | str | — | removed |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/interview.py:223, D:/Perplexity_Orchestrator2/api/routes/interview.py:228`
```python
{"error": "Session not found"}

{
        "topic": s.get("refined_topic", s["topic"]),
        "level": s["level"],
        "total_questions": len(s["questions"]),
        "answered": len(answered),
        "average_score": round(sum(scores) / len(scores), 1) if scores else 0,
        "questions": [
            {
                "index": i,
                "question": s["questions"][i]["question"][:120] if i < len(s["questions"]) else "",
                "subtopic": s["questions"][i].get("subtopic", "") if i < len(s["questions"]) else "",
                "score": s["results"][i]["score"] if i < len(s["results"]) and s["results"][i] else None,
                "verdict": s["results"][i]["verdict"] if i < len(s["results"]) and s["results"][i] else None,
            }
            for i in range(len(s["questions"]))
        ],
    }
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `error` | 'Session not found' | — | removed |
| `topic` | s.get('refined_topic', s['topic']) | — | removed |
| `level` | s['level'] | — | removed |
| `total_questions` | len(s['questions']) | — | removed |
| `answered` | len(answered) | — | removed |
| `average_score` | round(sum(scores) / len(scores), 1) if scores else 0 | — | removed |
| `questions` | [{'index': i, 'question': s['questions'][i]['question'][:120] if i < len(s['questions']) else '', 'subtopic': s['questions'][i].get('subtopic', '') if i < len(s['questions']) else '', 'score': s['results'][i]['score'] if i < len(s['results']) and s['results'][i] else None, 'verdict': s['results'][i]['verdict'] if i < len(s['results']) and s['results'][i] else None} for i in range(len(s['questions']))] | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X GET "http://127.0.0.1:8001/api/interview/summary/00000000-0000-0000-0000-000000000000?session_id=00000000-0000-0000-0000-000000000000"

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## POST /orchestrate
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/orchestrate.py:49-63, D:/Perplexity_Orchestrator2/api/routes/orchestrate.py:39-46`
```python
class OrchestrationRequest(BaseModel):
    """Request body for orchestration."""
    task: str = Field(..., description="The task to execute", min_length=1)
    level: ReliabilityLevel = Field(
        default=ReliabilityLevel.STANDARD,
        description="Reliability level (QUICK, STANDARD, HIGH, MAXIMUM)"
    )
    model: Optional[str] = Field(
        default=None,
        description="Specific model to use (overrides level defaults). Options: 'sonar', 'gpt', 'claude', 'gemini', 'kimi'"
    )
    mirror_telegram: bool = Field(
        default=False,
        description="Mirror result to Telegram"
    )

class ReliabilityLevel(str, Enum):
    """Reliability level for orchestration."""
    QUICK = "QUICK"
    STANDARD = "STANDARD"
    HIGH = "HIGH"
    MAXIMUM = "MAXIMUM"
    FOUR_OPINIONS = "FOUR_OPINIONS"  # Raw responses from 4 models without processing
    INTERSECTIONS = "INTERSECTIONS"
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `task` | str / Field(..., description='The task to execute', min_length=1) | — | removed |
| `level` | ReliabilityLevel / Field(default=ReliabilityLevel.STANDARD, description='Reliability level (QUICK, STANDARD, HIGH, MAXIMUM)') | — | removed |
| `model` | Optional[str] / Field(default=None, description="Specific model to use (overrides level defaults). Options: 'sonar', 'gpt', 'claude', 'gemini', 'kimi'") | — | removed |
| `mirror_telegram` | bool / Field(default=False, description='Mirror result to Telegram') | — | removed |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/orchestrate.py:66-70`
```python
class OrchestrationResponse(BaseModel):
    """Response for orchestration request."""
    task_id: str
    status: str
    message: str
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `task_id` | str | — | removed |
| `status` | str | — | removed |
| `message` | str | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X POST "http://127.0.0.1:8001/orchestrate" -H "Content-Type: application/json" -d '{"task": "Example prompt"}'

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## GET /status/{task_id}
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/orchestrate.py:465-481`
```python
# no request body; path/query parameters
task_id: str  # path
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `task_id` | str | — | removed |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/orchestrate.py:73-83`
```python
class TaskStatus(BaseModel):
    """Task status response."""
    task_id: str
    status: str  # pending, running, completed, failed
    progress: int = 0
    total_steps: int = 0
    current_step: Optional[str] = None
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `task_id` | str | — | removed |
| `status` | str | — | removed |
| `progress` | int / 0 | — | removed |
| `total_steps` | int / 0 | — | removed |
| `current_step` | Optional[str] / None | — | removed |
| `result` | Optional[dict] / None | — | removed |
| `error` | Optional[str] / None | — | removed |
| `created_at` | str | — | removed |
| `updated_at` | str | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X GET "http://127.0.0.1:8001/status/00000000-0000-0000-0000-000000000000?task_id=00000000-0000-0000-0000-000000000000"

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## GET /tasks
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/orchestrate.py:485-493`
```python
— (no request body)
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| — | no request body | no request body | identical |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/orchestrate.py:487`
```python
{
        "count": len(tasks),
        "tasks": [
            {"task_id": t["task_id"], "status": t["status"], "created_at": t["created_at"]}
            for t in tasks.values()
        ]
    }
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `count` | len(tasks) | — | removed |
| `tasks` | [{'task_id': t['task_id'], 'status': t['status'], 'created_at': t['created_at']} for t in tasks.values()] | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X GET "http://127.0.0.1:8001/tasks"

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## GET /stats/models
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/stats.py:11-26`
```python
— (no request body)
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| — | no request body | no request body | identical |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/stats.py:26`
```python
{"stats": get_model_stats_list()}
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `stats` | get_model_stats_list() | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X GET "http://127.0.0.1:8001/stats/models"

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## GET /stats/requests
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/stats.py:30-40`
```python
# no request body; path/query parameters
limit: int = 50  # body
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `limit` | int / 50 | — | removed |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/stats.py:40`
```python
{"requests": get_recent_requests_list(limit)}
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `requests` | get_recent_requests_list(limit) | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X GET "http://127.0.0.1:8001/stats/requests"

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## GET /stats/summary
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/stats.py:44-55`
```python
— (no request body)
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| — | no request body | no request body | identical |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/stats.py:55`
```python
{"summary": db.get_stats_summary()}
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `summary` | db.get_stats_summary() | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X GET "http://127.0.0.1:8001/stats/summary"

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## POST /api/tasks/complex
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/tasks.py:18-21`
```python
class CreateTaskRequest(BaseModel):
    """Request to create a complex task."""
    description: str
    auto_execute: bool = False
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `description` | str | — | removed |
| `auto_execute` | bool / False | — | removed |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/tasks.py:24-29`
```python
class CreateTaskResponse(BaseModel):
    """Response with created task info."""
    task_id: str
    name: str
    subtask_count: int
    subtasks: List[dict]
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `task_id` | str | — | removed |
| `name` | str | — | removed |
| `subtask_count` | int | — | removed |
| `subtasks` | List[dict] | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X POST "http://127.0.0.1:8001/api/tasks/complex" -H "Content-Type: application/json" -d '{"description": "Example prompt"}'

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## POST /api/tasks/{task_id}/execute
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/tasks.py:192-222`
```python
# request fields from handler signature
task_id: str  # path
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `task_id` | str | — | removed |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/tasks.py:41-46`
```python
class ExecuteTaskResponse(BaseModel):
    """Response after task execution."""
    task_id: str
    status: str
    progress: dict
    message: str
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `task_id` | str | — | removed |
| `status` | str | — | removed |
| `progress` | dict | — | removed |
| `message` | str | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X POST "http://127.0.0.1:8001/api/tasks/00000000-0000-0000-0000-000000000000/execute?task_id=00000000-0000-0000-0000-000000000000"

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## POST /api/tasks/{task_id}/resume
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/tasks.py:226-255`
```python
# request fields from handler signature
task_id: str  # path
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `task_id` | str | — | removed |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/tasks.py:41-46`
```python
class ExecuteTaskResponse(BaseModel):
    """Response after task execution."""
    task_id: str
    status: str
    progress: dict
    message: str
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `task_id` | str | — | removed |
| `status` | str | — | removed |
| `progress` | dict | — | removed |
| `message` | str | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X POST "http://127.0.0.1:8001/api/tasks/00000000-0000-0000-0000-000000000000/resume?task_id=00000000-0000-0000-0000-000000000000"

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## GET /api/tasks/{task_id}/result
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/tasks.py:286-308`
```python
# no request body; path/query parameters
task_id: str  # path
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `task_id` | str | — | removed |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/tasks.py:294`
```python
{
        "task_id": task.id,
        "name": task.name,
        "status": task.status.value,
        "result": task.get_final_result(),
        "subtask_results": [
            {
                "name": s.name,
                "status": s.status.value,
                "result": s.result[:500] if s.result else None,
                "consensus_score": s.consensus_score
            }
            for s in task.subtasks.values()
        ]
    }
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `task_id` | task.id | — | removed |
| `name` | task.name | — | removed |
| `status` | task.status.value | — | removed |
| `result` | task.get_final_result() | — | removed |
| `subtask_results` | [{'name': s.name, 'status': s.status.value, 'result': s.result[:500] if s.result else None, 'consensus_score': s.consensus_score} for s in task.subtasks.values()] | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X GET "http://127.0.0.1:8001/api/tasks/00000000-0000-0000-0000-000000000000/result?task_id=00000000-0000-0000-0000-000000000000"

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## DELETE /api/tasks/{task_id}
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/tasks.py:321-335`
```python
# no request body; path/query parameters
task_id: str  # path
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `task_id` | str | — | removed |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/tasks.py:335`
```python
{"status": "deleted", "task_id": task_id}
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `status` | 'deleted' | — | removed |
| `task_id` | task_id | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X DELETE "http://127.0.0.1:8001/api/tasks/00000000-0000-0000-0000-000000000000?task_id=00000000-0000-0000-0000-000000000000"

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## GET /api/threads
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/threads.py:92-101`
```python
— (no request body)
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| — | no request body | no request body | identical |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/threads.py:34-41`
```python
# wrapper: List[ThreadResponse]

class ThreadResponse(BaseModel):
    """Thread response model."""
    id: str
    title: str
    is_active: bool = False
    query_count: int = 0
    created_at: str
    updated_at: str
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `id` | str | — | removed |
| `title` | str | — | removed |
| `is_active` | bool / False | — | removed |
| `query_count` | int / 0 | — | removed |
| `created_at` | str | — | removed |
| `updated_at` | str | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X GET "http://127.0.0.1:8001/api/threads"

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## POST /api/threads
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/threads.py:16-18`
```python
class ThreadCreate(BaseModel):
    """Request to create a thread."""
    title: str = Field(default="Новая ветка", min_length=1, max_length=200)
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `title` | str / Field(default='Новая ветка', min_length=1, max_length=200) | — | removed |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/threads.py:34-41`
```python
class ThreadResponse(BaseModel):
    """Thread response model."""
    id: str
    title: str
    is_active: bool = False
    query_count: int = 0
    created_at: str
    updated_at: str
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `id` | str | — | removed |
| `title` | str | — | removed |
| `is_active` | bool / False | — | removed |
| `query_count` | int / 0 | — | removed |
| `created_at` | str | — | removed |
| `updated_at` | str | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X POST "http://127.0.0.1:8001/api/threads"

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## GET /api/threads/{thread_id}
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/threads.py:131-151`
```python
# no request body; path/query parameters
thread_id: str  # path
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `thread_id` | str | — | removed |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/threads.py:55-63, D:/Perplexity_Orchestrator2/api/routes/threads.py:44-52`
```python
class ThreadWithQueries(BaseModel):
    """Thread with its queries."""
    id: str
    title: str
    is_active: bool = False
    query_count: int = 0
    created_at: str
    updated_at: str
    queries: List[QueryResponse] = []

class QueryResponse(BaseModel):
    """Query response model."""
    id: str
    thread_id: str
    text: str
    models_used: str = ""
    result: str = ""
    consensus_score: int = 0
    created_at: str
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `id` | str | — | removed |
| `title` | str | — | removed |
| `is_active` | bool / False | — | removed |
| `query_count` | int / 0 | — | removed |
| `created_at` | str | — | removed |
| `updated_at` | str | — | removed |
| `queries` | List[QueryResponse] / [] | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X GET "http://127.0.0.1:8001/api/threads/00000000-0000-0000-0000-000000000000?thread_id=00000000-0000-0000-0000-000000000000"

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## PATCH /api/threads/{thread_id}
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/threads.py:21-23`
```python
class ThreadUpdate(BaseModel):
    """Request to update a thread."""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `title` | Optional[str] / Field(None, min_length=1, max_length=200) | — | removed |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/threads.py:34-41`
```python
class ThreadResponse(BaseModel):
    """Thread response model."""
    id: str
    title: str
    is_active: bool = False
    query_count: int = 0
    created_at: str
    updated_at: str
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `id` | str | — | removed |
| `title` | str | — | removed |
| `is_active` | bool / False | — | removed |
| `query_count` | int / 0 | — | removed |
| `created_at` | str | — | removed |
| `updated_at` | str | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X PATCH "http://127.0.0.1:8001/api/threads/00000000-0000-0000-0000-000000000000" -H "Content-Type: application/json" -d '{"title": "example"}'

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## DELETE /api/threads/{thread_id}
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/threads.py:180-197`
```python
# no request body; path/query parameters
thread_id: str  # path
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `thread_id` | str | — | removed |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/threads.py:197`
```python
{"status": "deleted", "thread_id": thread_id}
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `status` | 'deleted' | — | removed |
| `thread_id` | thread_id | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X DELETE "http://127.0.0.1:8001/api/threads/00000000-0000-0000-0000-000000000000?thread_id=00000000-0000-0000-0000-000000000000"

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## POST /api/threads/{thread_id}/queries
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/threads.py:26-31`
```python
class QueryCreate(BaseModel):
    """Request to add a query to a thread."""
    text: str = Field(..., min_length=1)
    models_used: Optional[str] = None
    result: Optional[str] = None
    agreement_rate: int = 0
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `text` | str / Field(..., min_length=1) | — | removed |
| `models_used` | Optional[str] / None | — | removed |
| `result` | Optional[str] / None | — | removed |
| `agreement_rate` | int / 0 | — | removed |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/threads.py:44-52`
```python
class QueryResponse(BaseModel):
    """Query response model."""
    id: str
    thread_id: str
    text: str
    models_used: str = ""
    result: str = ""
    consensus_score: int = 0
    created_at: str
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `id` | str | — | removed |
| `thread_id` | str | — | removed |
| `text` | str | — | removed |
| `models_used` | str / '' | — | removed |
| `result` | str / '' | — | removed |
| `consensus_score` | int / 0 | — | removed |
| `created_at` | str | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X POST "http://127.0.0.1:8001/api/threads/00000000-0000-0000-0000-000000000000/queries" -H "Content-Type: application/json" -d '{"text": "example"}'

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## GET /api/webpage/presets
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/webpage.py:109-111`
```python
— (no request body)
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| — | no request body | no request body | identical |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/webpage_presets.py:530-542`
```python
return {
    "palettes": {...},
    "font_pairs": {...},
    "grid_types": {...},
    "page_types": {...},
    "chart_types": {...},
    "section_templates": {...},
    "typography": {...},
    "audiences": AUDIENCES,
    "action_goals": ACTION_GOALS,
}
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `palettes` | dict | — | removed |
| `font_pairs` | dict | — | removed |
| `grid_types` | dict | — | removed |
| `page_types` | dict | — | removed |
| `chart_types` | dict | — | removed |
| `section_templates` | dict | — | removed |
| `typography` | dict | — | removed |
| `audiences` | list | — | removed |
| `action_goals` | list | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X GET "http://127.0.0.1:8001/api/webpage/presets"

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## POST /api/webpage/generate
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/webpage.py:45-46`
```python
class GenerateRequest(BaseModel):
    config: dict
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `config` | dict | — | removed |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/webpage.py:131, D:/Perplexity_Orchestrator2/api/routes/webpage.py:140`
```python
{
            "success": True,
            "session_id": session_id,
            "preview_url": f"/api/webpage/preview/{session_id}",
            "download_url": f"/api/webpage/download/{session_id}",
            "size_bytes": len(html_content.encode("utf-8")),
        }

{"success": False, "error": str(e)}
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `success` | True | — | removed |
| `session_id` | session_id | — | removed |
| `preview_url` | f'/api/webpage/preview/{session_id}' | — | removed |
| `download_url` | f'/api/webpage/download/{session_id}' | — | removed |
| `size_bytes` | len(html_content.encode('utf-8')) | — | removed |
| `error` | str(e) | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X POST "http://127.0.0.1:8001/api/webpage/generate" -H "Content-Type: application/json" -d '{"config": {"title": "Example"}}'

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## GET /api/webpage/preview/{session_id}
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/webpage.py:144-150`
```python
# no request body; path/query parameters
session_id: str  # path
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `session_id` | str | — | removed |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/webpage.py:148, D:/Perplexity_Orchestrator2/api/routes/webpage.py:150`
```python
HTMLResponse("<h1>Page not found</h1>", status_code=404)

HTMLResponse(content)
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `body` | text/html | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X GET "http://127.0.0.1:8001/api/webpage/preview/00000000-0000-0000-0000-000000000000?session_id=00000000-0000-0000-0000-000000000000"

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## GET /api/webpage/download/{session_id}
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/webpage.py:154-163`
```python
# no request body; path/query parameters
session_id: str  # path
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `session_id` | str | — | removed |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/webpage.py:158, D:/Perplexity_Orchestrator2/api/routes/webpage.py:159`
```python
{"error": "File not found"}

FileResponse(
        str(filepath),
        media_type="text/html",
        filename=f"webpage_{session_id[:8]}.html",
    )
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `error` | 'File not found' | — | removed |
| `body` | file response | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X GET "http://127.0.0.1:8001/api/webpage/download/00000000-0000-0000-0000-000000000000?session_id=00000000-0000-0000-0000-000000000000"

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## POST /api/webpage/ai-suggest
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/webpage.py:49-54`
```python
class AiSuggestRequest(BaseModel):
    topic: str = ""
    audience: str = "analyst"
    page_type: str = "dashboard"
    action_goal: str = "learn"
    message: str = ""
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `topic` | str / '' | — | removed |
| `audience` | str / 'analyst' | — | removed |
| `page_type` | str / 'dashboard' | — | removed |
| `action_goal` | str / 'learn' | — | removed |
| `message` | str / '' | — | removed |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/webpage.py:196, D:/Perplexity_Orchestrator2/api/routes/webpage.py:197, D:/Perplexity_Orchestrator2/api/routes/webpage.py:201`
```python
{"success": True, "suggestion": parsed}

{"success": False, "error": "Could not parse AI response"}

{"success": False, "error": str(e)}
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `success` | True | — | removed |
| `suggestion` | parsed | — | removed |
| `error` | 'Could not parse AI response' | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X POST "http://127.0.0.1:8001/api/webpage/ai-suggest"

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## POST /api/webpage/ai-content
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/webpage.py:57-63`
```python
class AiContentRequest(BaseModel):
    field_type: str = "title"
    section_type: str = "hero"
    topic: str = ""
    audience: str = "analyst"
    language: str = "en"
    context: str = ""
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `field_type` | str / 'title' | — | removed |
| `section_type` | str / 'hero' | — | removed |
| `topic` | str / '' | — | removed |
| `audience` | str / 'analyst' | — | removed |
| `language` | str / 'en' | — | removed |
| `context` | str / '' | — | removed |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/webpage.py:232, D:/Perplexity_Orchestrator2/api/routes/webpage.py:233, D:/Perplexity_Orchestrator2/api/routes/webpage.py:237`
```python
{"success": True, "content": parsed["content"]}

{"success": False, "error": "Could not parse AI response"}

{"success": False, "error": str(e)}
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `success` | True | — | removed |
| `content` | parsed['content'] | — | removed |
| `error` | 'Could not parse AI response' | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X POST "http://127.0.0.1:8001/api/webpage/ai-content"

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.

## POST /api/webpage/ai-chart
### Orchestrator2 request schema
Source: `D:/Perplexity_Orchestrator2/api/routes/webpage.py:66-69`
```python
class AiChartRequest(BaseModel):
    csv_data: str
    topic: str = ""
    language: str = "en"
```

### GraceKelly request schema
— (not present in this project)

### Request field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `csv_data` | str | — | removed |
| `topic` | str / '' | — | removed |
| `language` | str / 'en' | — | removed |

### Orchestrator2 response schema
Source: `D:/Perplexity_Orchestrator2/api/routes/webpage.py:268, D:/Perplexity_Orchestrator2/api/routes/webpage.py:269, D:/Perplexity_Orchestrator2/api/routes/webpage.py:273`
```python
{"success": True, "suggestion": parsed}

{"success": False, "error": "Could not parse AI response"}

{"success": False, "error": str(e)}
```

### GraceKelly response schema
— (not present in this project)

### Response field diff
| Field | Orchestrator2 type / default | GraceKelly type / default | Status |
|---|---|---|---|
| `success` | True | — | removed |
| `suggestion` | parsed | — | removed |
| `error` | 'Could not parse AI response' | — | removed |

### Curl examples
```bash
# Orchestrator2
curl -X POST "http://127.0.0.1:8001/api/webpage/ai-chart" -H "Content-Type: application/json" -d '{"csv_data": "month,value\nJan,10\nFeb,12"}'

# GraceKelly
— (not present in this project)
```

### Classification
orchestrator2-only
В GraceKelly нет прямого HTTP counterpart с сопоставимым contract surface.
