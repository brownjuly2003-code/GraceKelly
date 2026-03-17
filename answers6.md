# GraceKelly — Ответы на архитектурные вопросы (часть 7)

**Дата:** 16 марта 2026

---

## 1. Точный task.status для Phase 1, включая dry-run

**Четыре статуса. Dry-run завершается как `completed`. Без `running`.**

```python
class TaskStatus(StrEnum):
    ACCEPTED  = "accepted"    # task создан, execution ещё не начался
    COMPLETED = "completed"   # quorum достигнут (или dry-run план валиден)
    FAILED    = "failed"      # quorum не достигнут
    CANCELLED = "cancelled"   # отменён оператором до завершения
```

### Dry-run: completed, не accepted

Текущее поведение — dry-run возвращает `status = "accepted"`. Это неправильно.

`accepted` по семантике означает "запрос принят, работа ещё не завершена". Но dry-run task — завершён моментально. Нет pending work, нечего poll-ить. Клиент, получивший `accepted`, обязан проверить GET /tasks/{id} позже — но для dry-run проверять нечего.

Dry-run — это валидация execution plan: "можно ли построить план для этих моделей с этим quorum?" Если план построен — задача выполнена успешно. Результат — подтверждение валидности, а не pending execution.

```python
# В OrchestratorService.submit():
if execution_plan.dry_run:
    task_status = "completed"  # план валиден, задача завершена
else:
    task_status = batch_result.task_status  # completed | failed
```

### Почему не нужен running

`running` на уровне task нужен только при асинхронном execution:

```
POST /orchestrate → 202, status=accepted
(execution в background)
GET /tasks/{id}   → status=running    ← вот этот момент
GET /tasks/{id}   → status=completed
```

Но текущая архитектура — синхронная. К моменту HTTP-ответа execution завершён. task никогда не находится в состоянии `running` с точки зрения клиента.

Когда execution станет асинхронным (Phase 3+), добавить `running` — одна строка в enum. Не миграция: старые данные не содержат `running` (они все терминальные), новые данные начнут его использовать. Обратно-совместимо.

### Матрица task.status

| Сценарий | status |
|----------|--------|
| Dry-run, план валиден | completed |
| Dry-run, план невалиден (unknown model) | HTTP 422, task не создаётся |
| Single model, success | completed |
| Single model, failure | failed |
| Multi-model, quorum достигнут | completed |
| Multi-model, quorum не достигнут | failed |
| Отменён оператором | cancelled |

**Вердикт:** 4 статуса: accepted, completed, failed, cancelled. Dry-run → completed. Без running до async execution.

---

## 2. task.cancelled в event stream: семантика

**Переименовать в `steps.cancelled`. Или убрать и вложить в payload task.completed.**

### Проблема

В answers5.md пример event stream для multi-model cancel:

```
1. task.accepted
2. step.completed  (step_index=1)
3. task.cancelled   (cancelled_steps=[2, 3])
4. task.completed
```

Это противоречиво: task одновременно "cancelled" и "completed". `task.cancelled` подразумевает, что **task** отменён. Но task успешен — отменены только оставшиеся **шаги**.

### Решение: убрать task.cancelled, вложить в task.completed

```
1. task.accepted
2. step.completed  (step_index=1, model_id=..., duration_ms=...)
3. task.completed   (winning_step=1, cancelled_steps=[2, 3], reason="quorum_reached")
```

`task.completed` фиксирует всё: и успех, и какие шаги были отменены, и почему. Одно событие вместо двух. Нет семантического конфликта.

Для полной operator cancel (оператор отменил task до завершения):

```
1. task.accepted
2. task.failed     (failure_code="cancelled", cancelled_steps=[1, 2, 3])
```

Или, если считать cancel отдельным терминальным статусом:

```
1. task.accepted
2. task.cancelled  (reason="operator", cancelled_steps=[1, 2, 3])
```

Здесь `task.cancelled` корректен: **весь task** отменён, не только шаги.

### Пересмотренный набор event_type

```python
class EventType(StrEnum):
    TASK_ACCEPTED   = "task.accepted"
    TASK_COMPLETED  = "task.completed"    # payload включает cancelled_steps если есть
    TASK_FAILED     = "task.failed"
    TASK_CANCELLED  = "task.cancelled"    # только для отмены всего task
    STEP_COMPLETED  = "step.completed"
    STEP_FAILED     = "step.failed"
```

Те же 6 типов, но семантика `task.cancelled` уточнена: **отмена всего task**, не отдельных шагов. Отмена шагов из-за quorum — информация в payload `task.completed`.

### Payload contracts

```python
# task.completed payload:
{
    "winning_step_index": 1,
    "winning_model_id": "mistral-small",
    "duration_ms": 2340,
    "cancelled_steps": [2, 3],           # пустой список если нет cancelled
    "cancel_reason": "quorum_reached",   # null если нет cancelled
}

# task.cancelled payload (operator cancel):
{
    "reason": "operator",
    "cancelled_steps": [1, 2, 3],
}

# task.failed payload:
{
    "failure_code": "timeout",
    "failure_message": "No model reached quorum within timeout",
}
```

**Вердикт:** cancelled_steps → payload task.completed. `task.cancelled` event — только для отмены всего task оператором. Нет двусмысленности.

---

## 3. gk_tasks.model_id и model_display_name в multi-model task

**Убрать оба. Вычислять из steps.**

### Проблема

Текущий код записывает primary step model:

```python
# orchestrator.py:59
task = TaskRecord(
    ...
    model_id=primary_step.model.id,
    model_display_name=primary_step.model.display_name,
)
```

`primary_step = execution_plan.steps[0]` — первая запрошенная модель. Но это:

- **Не winning model** — при first_success вторая модель может ответить первой
- **Не "главная" модель** — порядок в `models[]` произвольный
- **Бессмысленно при multi-model** — "model_id задачи, в которой 3 модели" — какой?

Любой вариант (first requested, winning, primary) — произвольное соглашение, которое кто-то интерпретирует неправильно.

### Решение

Убрать `model_id` и `model_display_name` из gk_tasks. Заменить на:

```sql
ALTER TABLE gk_tasks DROP COLUMN model_id;
ALTER TABLE gk_tasks DROP COLUMN model_display_name;
ALTER TABLE gk_tasks ADD COLUMN model_count INTEGER NOT NULL DEFAULT 1;
```

`model_count` — сколько моделей участвовало. Единственное aggregate-поле, которое корректно на уровне task.

### Где получить model info

**Для single-model task:**

```sql
SELECT s.model_id, s.model_display_name
FROM gk_task_steps s
WHERE s.task_id = ? AND s.step_index = 1;
```

**Для winning model (first_success):**

```sql
SELECT s.model_id, s.model_display_name
FROM gk_task_steps s
WHERE s.task_id = ? AND s.status = 'completed'
ORDER BY s.step_index ASC
LIMIT 1;
```

**Для API response (TaskView):**

```python
class OrchestrateResponse(BaseModel):
    ...
    model: ModelView | None = None         # winning model, null для failed/dry-run
    requested_models: list[ModelView]       # все запрошенные, из steps

    @classmethod
    def from_task(cls, task: TaskRecord, steps: list[TaskStepRecord]) -> "OrchestrateResponse":
        winning = next((s for s in steps if s.status == "completed"), None)
        model = ModelView(id=winning.model_id, display_name=winning.model_display_name) if winning else None
        requested = [ModelView(id=s.model_id, display_name=s.model_display_name) for s in steps]
        return cls(..., model=model, requested_models=requested)
```

### Для dry-run (нет steps)

Dry-run не создаёт gk_task_steps. Информация о запрошенных моделях — в event payload `task.accepted`:

```python
# task.accepted payload для dry-run:
{
    "dry_run": True,
    "requested_models": [
        {"model_id": "kimi-k2-5", "display_name": "Kimi K2.5"},
        {"model_id": "mistral-small", "display_name": "Mistral Small"},
    ],
    "quorum": 1,
}
```

API response для dry-run:

```python
model = None  # нет winning model
requested_models = [...]  # из event payload
```

### Обратная совместимость API

Текущий `OrchestrateResponse.model` — required field (`ModelView`, не Optional). Сделать nullable — breaking change для клиентов, ожидающих non-null.

Варианты:
1. **Сделать nullable сейчас** — проект на Phase 1, клиентов нет, breaking change бесплатен
2. **Оставить как computed** — для multi-model вернуть первую запрошенную, пометить в docs как "primary requested model, not necessarily the winning model"

Рекомендация: **вариант 1**. Чем раньше API-контракт станет корректным, тем меньше tech debt.

**Вердикт:** убрать model_id и model_display_name из gk_tasks. Добавить model_count. model и requested_models в API — вычислять из steps (и event payload для dry-run).

---

## 4. Где хранить execution plan snapshot для dry-run?

**В payload события task.accepted. Это единственное правильное место.**

### Почему не metadata

Мы решили (answers2.md, вопрос 2): metadata = только user-provided data. Execution plan — system data. Нарушение этого решения ради dry-run — slippery slope обратно к "metadata как помойка".

### Почему не отдельная таблица/колонка

Dry-run plan snapshot — read-only данные, нужные для одного use case: "посмотреть, какой план был бы построен". Отдельная таблица gk_execution_plans или JSONB-колонка в gk_tasks — overhead ради одного типа задач.

### Почему event payload — правильно

`task.accepted` — первое событие любого task. Для dry-run — единственное значимое. Его payload естественно содержит snapshot того, что произошло при создании task:

```python
# Для dry-run:
TaskEventRecord(
    event_type="task.accepted",
    payload={
        "dry_run": True,
        "execution_plan": {
            "quorum": 2,
            "merge_strategy": "first_success",
            "adapter_hint": "auto",
            "steps": [
                {
                    "step_index": 1,
                    "model_id": "kimi-k2-5",
                    "display_name": "Kimi K2.5",
                    "backend": "browser",
                    "provider": "perplexity",
                },
                {
                    "step_index": 2,
                    "model_id": "mistral-small",
                    "display_name": "Mistral Small",
                    "backend": "api",
                    "provider": "mistral",
                },
            ],
        },
    },
)
```

```python
# Для реального execution — тот же формат, но dry_run=false:
TaskEventRecord(
    event_type="task.accepted",
    payload={
        "dry_run": False,
        "execution_plan": { ... },
    },
)
```

### Единообразие

task.accepted **всегда** содержит execution_plan snapshot — и для dry-run, и для реального execution. Это единый контракт. Не нужно проверять `if dry_run: читай plan из event; else: читай из steps`.

Для реального execution steps содержат results (status, output, duration). Для dry-run steps не существуют, но план — в event.

### Как получить plan для dry-run в API

```python
class TaskView:
    @classmethod
    def from_task(cls, task, steps, events):
        if task.dry_run:
            accepted_event = next(e for e in events if e.event_type == "task.accepted")
            requested_models = [
                ModelView(id=s["model_id"], display_name=s["display_name"])
                for s in accepted_event.payload["execution_plan"]["steps"]
            ]
        else:
            requested_models = [
                ModelView(id=s.model_id, display_name=s.model_display_name)
                for s in steps
            ]
```

Лёгкая асимметрия в from_task, но data model чистый: events для observability, steps для results.

**Вердикт:** execution plan snapshot → payload task.accepted. Единый формат для dry-run и real execution. Не metadata, не отдельная таблица.

---

## 5. Контракт gk_tasks.output_text в multi-model режиме

**Фиксируем жёстко:**

> `gk_tasks.output_text` — финальный merged/winning output задачи. Никогда не содержит per-step outputs. NULL для dry-run и failed tasks.

### Полная спецификация

| Сценарий | merge_strategy | output_text |
|----------|---------------|-------------|
| Dry-run | любая | NULL |
| Single model, completed | first_success | output этой модели |
| Single model, failed | любая | NULL |
| Multi-model, quorum=1, first_success | first_success | output первой успешной модели |
| Multi-model, quorum=2, concat | concat | `step1_output + "\n\n" + step2_output` |
| Multi-model, quorum не достигнут | любая | NULL |
| Cancelled (operator) | любая | NULL |

### Инварианты

```python
# Всегда истинно:
assert (task.status == "completed") == (task.output_text is not None or task.dry_run)
assert (task.status == "failed") == (task.output_text is None and task.failure_code is not None)
assert (task.dry_run) == (task.output_text is None)  # dry-run никогда не имеет output
```

Упрощённо:
- `output_text is not None` ⟺ `status == "completed" and not dry_run`
- `output_text is NULL` ⟺ `status in ("failed", "cancelled") or dry_run`

### Merge strategies и output_text

| merge_strategy | Как формируется output_text |
|---------------|----------------------------|
| first_success | `output_text = first_completed_step.output_text` |
| concat | `output_text = "\n\n".join(step.output_text for step in completed_steps)` |

Новые стратегии в будущем (`vote`, `best`) будут определять свою логику формирования output_text, но контракт тот же: одна строка, финальный результат.

### Per-step outputs

Per-step outputs живут только в gk_task_steps.output_text. Клиент, которому нужны ответы каждой модели отдельно, читает steps. Клиент, которому нужен финальный результат — читает task.output_text.

Не дублируются. Не агрегируются в другом месте.

**Вердикт:** output_text = final merged result. NULL для dry-run/failed/cancelled. Per-step outputs — только в gk_task_steps. Контракт зафиксирован.

---

## 6. gk_tasks.failure_code и failure_message: только aggregate task failure?

**Да. Строго только aggregate.**

### Правило

```
gk_tasks.failure_code IS NOT NULL  ⟺  task.status = "failed"
gk_tasks.failure_code IS NULL      ⟺  task.status IN ("completed", "cancelled", "accepted")
```

Task-level failure означает: **задача в целом не выполнена, quorum не достигнут.**

### Что НЕ является task failure

Один шаг из трёх failed, но quorum=1 достигнут через другой шаг → task completed, не failed. Ошибка шага — в gk_task_steps. Task-level failure_code = NULL.

```
Task: status=completed, failure_code=NULL
  Step 1: status=completed  (Mistral ответил)
  Step 2: status=failed, failure_code=timeout  (Perplexity тайм-аут)
  Step 3: status=cancelled  (cancel_on_quorum)
```

Оператор видит: задача успешна, один шаг тайм-аутнул, один отменён. Чисто.

### Как формируется task-level failure

Когда quorum не достигнут, task.failure_code — **агрегат** step failures:

```python
def _resolve_task_failure(self, failed_steps: list[TaskStepRecord]) -> tuple[str, str]:
    """Выбрать representative failure для task level."""
    if not failed_steps:
        return FailureCode.UNKNOWN_ERROR, "No steps completed, no failures recorded."

    # Приоритет: первый step (highest priority) определяет task failure
    primary = failed_steps[0]

    if len(failed_steps) == 1:
        return primary.failure_code, primary.failure_message

    # Multiple failures — summarize
    codes = {s.failure_code for s in failed_steps}
    if len(codes) == 1:
        # Все шаги failed с одинаковым кодом
        return primary.failure_code, f"All {len(failed_steps)} steps failed: {primary.failure_message}"

    # Разные failure codes
    return FailureCode.UNKNOWN_ERROR, (
        f"{len(failed_steps)} steps failed with different errors: "
        + ", ".join(f"{s.model_id}={s.failure_code}" for s in failed_steps)
    )
```

### Примеры

**Все шаги timeout:**
```
task.failure_code = "timeout"
task.failure_message = "All 3 steps failed: Mistral request timed out after 30s"
```

**Разные ошибки:**
```
task.failure_code = "unknown_error"
task.failure_message = "3 steps failed with different errors: mistral-small=timeout, claude-sonnet-4-6=provider_unavailable, kimi-k2-5=rate_limited"
```

**Один шаг, одна ошибка:**
```
task.failure_code = "provider_unavailable"
task.failure_message = "Mistral API key is not configured."
```

### Инвариант в коде

```python
# В OrchestratorService — после execution:
if task_status == "completed":
    assert failure_code is None
    assert failure_message is None
    assert output_text is not None or dry_run

if task_status == "failed":
    assert failure_code is not None
    assert failure_message is not None
    assert output_text is None
```

Эти assert-ы — не runtime checks, а documentation of invariants. В тестах — проверяются явно.

**Вердикт:** failure_code/failure_message на gk_tasks — строго aggregate. Заполняются только при `status = "failed"` (quorum не достигнут). Step-level ошибки — только в gk_task_steps и step.failed events. Чистое разделение уровней.
