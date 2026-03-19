# GraceKelly — Ответы на архитектурные вопросы (часть 6)

**Дата:** 16 марта 2026

---

## 1. Нужны ли dry-run задачам записи в gk_task_steps?

**Нет. Dry-run → только gk_tasks + gk_task_events.**

### Почему нет

Dry-run шаг не выполняет реальную работу. Адаптер возвращает моментальный симулированный результат:

```python
# dry_run.py
def execute(self, request: ExecutionRequest) -> ExecutionResult:
    return ExecutionResult(
        ...
        execution_mode="dry-run",
        task_status="accepted",
        details={"simulated": True, ...},
    )
```

Записывать это в gk_task_steps — значит:
- Засорять таблицу строками с `output_text=NULL`, `duration_ms≈0`, `status="accepted"`
- Усложнять аналитические запросы: каждый `SELECT` по gk_task_steps потребует `JOIN gk_tasks WHERE dry_run = false`, иначе dry-run шаги исказят статистику (success rate, avg duration)
- Хранить данные без потребителя: никто не спросит "покажи step-level результаты dry-run задачи"

### Что достаточно для dry-run

**gk_tasks:**
- `dry_run = TRUE`
- `status = "accepted"`
- `metadata` с информацией о плане (какие модели были запрошены, какой quorum)

**gk_task_events:**
- `task.accepted` — одно событие, фиксирующее факт dry-run

Этого достаточно, чтобы ответить на все реальные вопросы:
- "Сколько dry-run задач было?" → `SELECT COUNT(*) FROM gk_tasks WHERE dry_run = true`
- "Какие модели тестировались в dry-run?" → metadata или event payload
- "Когда последний dry-run?" → `accepted_at`

### Реализация

В `OrchestratorService.submit()`:

```python
if not execution_plan.dry_run:
    for step_result in batch_result.results:
        self._repository.save_step(task_id, step_result)
# dry_run — без записи steps
```

В `TaskView.from_task()`:

```python
steps = repository.list_steps(task_id) if not task.dry_run else []
```

### Граничный случай: dry-run validation

Dry-run может обнаружить проблему до execution (неизвестная модель, conflicting adapter_hint). Эти ошибки ловятся на уровне planning (`build_execution_plan`), до создания task. Они возвращаются как HTTP 422, не как task record. Steps не задействованы.

**Вердикт:** dry-run → gk_tasks + events. gk_task_steps только для реального execution (`dry_run = false`).

---

## 2. Минимальный канонический набор event_type

**Шесть типов. Не семь.**

```python
class EventType(StrEnum):
    TASK_ACCEPTED       = "task.accepted"
    TASK_COMPLETED      = "task.completed"
    TASK_FAILED         = "task.failed"
    STEP_COMPLETED      = "step.completed"
    STEP_FAILED         = "step.failed"
    TASK_CANCELLED      = "task.cancelled"
```

### Обоснование каждого

| event_type | Когда | Payload | Зачем |
|-----------|-------|---------|-------|
| `task.accepted` | Task создан, execution начинается | `{quorum, merge_strategy, models: [...]}` | Точка входа. Единственный обязательный event для любого task. |
| `task.completed` | Quorum достигнут, output готов | `{winning_model_id, duration_ms}` | Финальный happy-path event. |
| `task.failed` | Quorum не достигнут, все шаги failed | `{failure_code, failure_message}` | Финальный sad-path event. |
| `step.completed` | Один шаг успешно завершён | `{step_index, model_id, duration_ms}` | Per-model observability. Без этого невозможно понять, какой шаг был быстрым/медленным. |
| `step.failed` | Один шаг завершился ошибкой | `{step_index, model_id, failure_code}` | Per-model error tracking. |
| `task.cancelled` | Task отменён (cancel_on_quorum или manual) | `{reason, cancelled_steps: [step_index, ...]}` | Аудит: почему и какие шаги не выполнились. |

### Что НЕ включать

**`task.cancel_requested` — не нужен как отдельный event.**

cancel_requested — это intermediate state, не событие. В cooperative cancellation модели (answers2.md, вопрос 5) cancel request — это установка флага в CancellationToken. Между `cancel_requested` и `task.cancelled` проходит миллисекунды (cooperative check в safe point). Два события для одного логического действия — noise.

Вся нужная информация записывается в `task.cancelled`:
- reason: "quorum_reached" или "manual"
- cancelled_steps: какие шаги были cancelled
- Timestamp: когда произошла отмена

Если позже появится long-lived cancel (оператор нажал cancel, browser worker завершает текущую страницу 30 секунд), тогда `task.cancel_requested` обретёт смысл — зафиксировать момент запроса отдельно от момента фактической отмены. Но это Phase 4+, и добавить один event_type — не миграция.

**`step.started` — не нужен.**

По тем же причинам, что `running` статус не нужен для steps (answers2.md, вопрос 2). Шаг начался и завершился в рамках одного adapter.execute(). `step.completed` с duration_ms содержит всю информацию.

**`step.cancelled` — не нужен.**

Отменённые шаги перечислены в payload `task.cancelled`. Отдельное событие на каждый cancelled step — избыточно. При cancel_on_quorum с 3 моделями: один event `task.cancelled` вместо трёх `step.cancelled`. Меньше записей, та же информация.

### Порядок событий в типичных сценариях

**Single model, success:**
```
1. task.accepted
2. step.completed  (step_index=1)
3. task.completed
```

**Multi-model, quorum=1, first_success, cancel:**
```
1. task.accepted
2. step.completed  (step_index=1, fast model)
3. task.cancelled   (cancelled_steps=[2, 3])
4. task.completed
```

**Multi-model, all failed:**
```
1. task.accepted
2. step.failed     (step_index=1)
3. step.failed     (step_index=2)
4. task.failed
```

**Dry-run:**
```
1. task.accepted
```

### StrEnum vs строки

Зафиксировать как `StrEnum` в коде, но в БД хранить как TEXT без CHECK constraint (см. вопрос 4). Enum в коде — compile-time safety. TEXT в БД — extensibility.

**Вердикт:** 6 типов: `task.accepted`, `task.completed`, `task.failed`, `step.completed`, `step.failed`, `task.cancelled`. Без `cancel_requested`, без `step.started`, без `step.cancelled`.

---

## 3. Что включать в TaskStepView v1?

**9 полей. backend и provider — включить.**

```python
class TaskStepView(BaseModel):
    step_index: int
    model_id: str
    model_display_name: str
    backend: str
    provider: str
    status: str
    failure_code: str | None = None
    output_text: str | None = None
    output_truncated: bool = False
    duration_ms: int | None = None
```

### Обоснование включения backend и provider

**backend нужен** — оператор должен видеть, был ли шаг выполнен через browser или api, без маппинга model_id → backend в голове. Это ключевая диагностическая информация при failure:

```json
{
  "step_index": 1,
  "model_id": "claude-sonnet-4-6",
  "backend": "browser",
  "provider": "perplexity",
  "status": "failed",
  "failure_code": "timeout"
}
```

Без backend и provider оператор видит "claude-sonnet-4-6 failed with timeout" и должен помнить, что Claude идёт через browser через perplexity. При 5 моделях с разными backend/provider — unreasonable cognitive load.

**provider нужен** — в будущем одна модель может быть доступна через разных провайдеров (Claude через Perplexity browser и через Anthropic API). provider отвечает на вопрос "через кого пошли".

### Обоснование включения model_display_name

Не было в исходном списке, но нужен. API response не должен заставлять клиента резолвить `model_id` → human-readable name. `"claude-sonnet-4-6"` vs `"Claude Sonnet 4.6"` — второе для UI и логов.

### Что НЕ включать

| Поле | Почему нет |
|------|-----------|
| failure_message | Длинные строки, полезны только при дебаге конкретного шага. Доступны через events (`step.failed` payload). В MVP — лишний вес в типичном response. |
| provider_model_id | Internal detail. Оператору не нужно знать, что Mistral Small = `mistral-small-latest`. |
| adapter_name | Computed из backend + provider. Не хранится, не возвращается отдельно. |
| metadata | Per-step metadata не предусмотрена в gk_task_steps. |

### Пересмотр: добавить failure_message?

Аргумент за: при failure оператор хочет видеть причину сразу, без второго запроса к events. `failure_code = "timeout"` говорит что, но `failure_message = "Mistral request timed out after 30s"` говорит почему.

Компромисс: **включить.** 10 полей вместо 9. failure_message — короткая строка (<200 символов), не увеличивает payload значимо, но экономит round-trip при дебаге.

### Финальный TaskStepView v1

```python
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
```

**Вердикт:** 11 полей. backend и provider — да, обязательны для диагностики. model_display_name и failure_message — добавить сверх исходного списка.

---

## 4. CHECK constraints на step statuses и merge strategies в первой миграции?

**Нет. Оставить на уровне приложения.**

### Почему нет DB-level CHECK

**1. Enum расширяется без миграции.**

Добавление нового статуса (`suspended`, `retrying`) или новой merge strategy (`weighted_vote`) — частая операция в ранних фазах проекта. С CHECK constraint каждое добавление = миграция:

```sql
ALTER TABLE gk_task_steps DROP CONSTRAINT chk_step_status;
ALTER TABLE gk_task_steps ADD CONSTRAINT chk_step_status
    CHECK (status IN ('pending', 'completed', 'failed', 'cancelled', 'suspended'));
```

Без CHECK — добавить значение в StrEnum в коде, deploy. Готово.

**2. CHECK constraint на merge_strategy ещё более хрупок.**

Merge strategies — это policy, не data. Они могут появляться экспериментально (`weighted`, `llm_judge`, `consensus`). Фиксировать их в DDL — premature. В gk_tasks это TEXT-поле с валидацией на входе (Pydantic pattern/enum), не на выходе (DB constraint).

**3. Pydantic уже валидирует на входе.**

```python
class OrchestrateRequest(BaseModel):
    merge_strategy: str = Field(default="first_success", max_length=64)
```

Невалидный merge_strategy не пройдёт дальше HTTP-слоя. CHECK constraint в БД ловит баги в коде (OrchestratorService записал невалидный статус). Но для этого есть тесты — они дешевле и быстрее, чем миграции constraints.

**4. Стоимость невалидных данных — низкая.**

Если баг в коде запишет `status = "compelted"` (typo), это обнаружится:
- В тестах (assertEqual на статус)
- В UI (неизвестный статус не отрендерится)
- В мониторинге (метрика по статусам покажет anomaly)

DB CHECK поймал бы это на INSERT. Но цена починки одинакова — fix typo, redeploy. CHECK не предотвращает баг, он ловит его на одном шаге раньше.

### Что стоит добавить вместо CHECK

**NOT NULL constraints — да.** Это не про валидацию значений, а про structural integrity. Уже есть в текущей DDL. Оставить.

**Комментарии в DDL — да.** Документировать допустимые значения:

```sql
CREATE TABLE IF NOT EXISTS gk_task_steps (
    ...
    status TEXT NOT NULL,  -- pending | completed | failed | cancelled
    ...
);

CREATE TABLE IF NOT EXISTS gk_tasks (
    ...
    merge_strategy TEXT NOT NULL DEFAULT 'first_success',  -- first_success | concat
    ...
);
```

### Когда добавить CHECK

Конкретный триггер: **schema freeze для production release**. Когда набор статусов и стратегий стабилизирован (не менялся 2+ месяца) и проект перешёл в maintenance mode. Тогда CHECK — защита от regression, а не тормоз для development.

**Вердикт:** нет CHECK constraints в первой миграции. Валидация на входе через Pydantic + StrEnum в коде. NOT NULL — да. CHECK — после стабилизации схемы.
