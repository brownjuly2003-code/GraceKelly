# GraceKelly — Ответы на архитектурные вопросы (часть 3)

**Дата:** 16 марта 2026

---

## 1. Какие поля из execution plan вынести в колонки gk_tasks?

**Все пять. Они все участвуют в фильтрации или агрегации.**

```sql
ALTER TABLE gk_tasks ADD COLUMN quorum             INTEGER     NOT NULL DEFAULT 1;
ALTER TABLE gk_tasks ADD COLUMN merge_strategy      TEXT        NOT NULL DEFAULT 'first_success';
ALTER TABLE gk_tasks ADD COLUMN adapter_hint        TEXT        NOT NULL DEFAULT 'auto';
ALTER TABLE gk_tasks ADD COLUMN cancel_on_quorum    BOOLEAN     NOT NULL DEFAULT TRUE;
ALTER TABLE gk_tasks ADD COLUMN dry_run             BOOLEAN     NOT NULL DEFAULT TRUE;
ALTER TABLE gk_tasks ADD COLUMN completed_at        TIMESTAMPTZ NULL;
ALTER TABLE gk_tasks ADD COLUMN duration_ms         INTEGER     NULL;
```

**Обоснование по каждому:**

| Поле | Нужно в колонке? | Почему |
|------|-----------------|--------|
| dry_run | Да | `WHERE dry_run = false` — первый фильтр при анализе production runs. Без колонки — парсить JSONB каждый раз. |
| quorum | Да | "Покажи все задачи с quorum > 1" — реальный запрос для анализа multi-model usage. |
| merge_strategy | Да | Группировка по стратегии для сравнения результатов. Конечное множество значений — хороший кандидат для колонки. |
| adapter_hint | Да | "Сколько задач намеренно отправлено в browser vs api?" — операционная метрика. |
| cancel_on_quorum | Да | Нужно для аудита: "эта задача завершилась рано из-за cancel policy?" |

**Что НЕ выносить в колонки:**

- `execution_plan.steps[].provider_model_id` — живёт в gk_task_steps
- `execution_plan.steps[].priority` — живёт в gk_task_steps
- Любые вычисляемые поля (adapter_names list, result counts) — derivable из gk_task_steps

**Итоговая DDL для gk_tasks (полная):**

```sql
CREATE TABLE IF NOT EXISTS gk_tasks (
    task_id             TEXT        PRIMARY KEY,
    status              TEXT        NOT NULL,
    accepted_at         TIMESTAMPTZ NOT NULL,
    completed_at        TIMESTAMPTZ NULL,
    duration_ms         INTEGER     NULL,
    prompt              TEXT        NOT NULL,
    model_id            TEXT        NOT NULL,
    model_display_name  TEXT        NOT NULL,
    reasoning           BOOLEAN     NOT NULL,
    execution_mode      TEXT        NOT NULL,
    adapter_name        TEXT        NOT NULL,
    dry_run             BOOLEAN     NOT NULL DEFAULT TRUE,
    quorum              INTEGER     NOT NULL DEFAULT 1,
    merge_strategy      TEXT        NOT NULL DEFAULT 'first_success',
    adapter_hint        TEXT        NOT NULL DEFAULT 'auto',
    cancel_on_quorum    BOOLEAN     NOT NULL DEFAULT TRUE,
    failure_code        TEXT        NULL,
    failure_message     TEXT        NULL,
    output_text         TEXT        NULL,
    metadata            JSONB       NOT NULL DEFAULT '{}'::jsonb
);
```

7 новых колонок относительно текущей схемы. Все — NOT NULL с дефолтами, поэтому миграция обратно-совместима.

---

## 2. Минимальный набор статусов для gk_task_steps

**Четыре: `pending`, `completed`, `failed`, `cancelled`.**

Не три, не шесть. Вот почему:

### Зачем нужен `pending`

Сейчас execution синхронный, и шаг сразу получает финальный статус. Но при переходе на async/parallel execution появится момент, когда шаг создан, но ещё не запущен. Без `pending` невозможно отличить "шаг ещё не начался" от "шаг завершился без записи" (потеря данных).

Стоимость добавления `pending` сейчас — ноль. Стоимость добавления позже — миграция + рефакторинг всех `WHERE status =` запросов.

### Зачем нужен `cancelled`

Если cancel_on_quorum=true, оставшиеся шаги не выполняются. Им нужен статус. `failed` — неправильно (не было ошибки). Отсутствие записи — хуже (непонятно, сколько шагов было запланировано).

### Почему НЕ нужен `running`

`running` полезен только если шаги — долгоживущие процессы, за которыми нужно наблюдать в реальном времени. В текущей архитектуре шаг = один вызов adapter.execute(). Он либо pending, либо уже завершён. Отдельный `running` статус создаёт обязательство его обновлять (BEGIN → running, END → completed), что удваивает количество записей в БД без пользы.

Если в Phase 4+ browser execution станет 60+ секунд и появится потребность показывать "шаг сейчас выполняется", тогда добавить `running`. Но это одна миграция `UPDATE ... SET status = 'running'` — не architectural debt.

### Почему НЕ нужен `timed_out`

Timeout — это причина failure, а не отдельный статус. Правильная модель:

```
status = "failed", failure_code = "timeout"
```

Это консистентно с текущим `FailureCode.TIMEOUT`. Отдельный статус `timed_out` дублирует информацию и усложняет запросы: `WHERE status IN ('failed', 'timed_out')` вместо `WHERE status = 'failed'`.

### Итого

```python
class StepStatus(StrEnum):
    PENDING   = "pending"     # создан, ожидает выполнения
    COMPLETED = "completed"   # успешно завершён
    FAILED    = "failed"      # ошибка (причина в failure_code)
    CANCELLED = "cancelled"   # отменён (cancel_on_quorum или manual)
```

Терминальные: `completed`, `failed`, `cancelled`. Нетерминальный: `pending`.

---

## 3. Возвращать ли output_text каждого шага в GET /tasks/{task_id}?

**По умолчанию — возвращать. Но с одной защитой.**

### Почему возвращать

В MVP количество шагов — 1-5. Output каждого — типично 500-5000 символов. Суммарный payload TaskView — 5-30 KB. Это нормально для JSON API.

Скрывать output_text по умолчанию создаёт friction для основного use case: "покажи мне что ответили модели". Оператор будет вынужден делать дополнительный запрос для каждого шага.

### Одна защита: max_output_length в конфиге

Не truncate, не hide, не separate fetch. Просто ограничение на уровне сериализации:

```python
class TaskStepView(BaseModel):
    ...
    output_text: str | None = None
    output_truncated: bool = False

    @classmethod
    def from_record(cls, record, *, max_output_length: int = 20_000) -> "TaskStepView":
        output = record.output_text
        truncated = False
        if output and len(output) > max_output_length:
            output = output[:max_output_length]
            truncated = True
        return cls(..., output_text=output, output_truncated=truncated)
```

20 000 символов — достаточно для 99% ответов LLM. Если output_truncated=true, оператор знает, что есть больше.

### Когда вводить separate fetch

Конкретный триггер: когда появятся задачи с output >100 KB per step (code generation, long documents). Тогда:

```
GET /api/v1/tasks/{task_id}                        — steps без output_text
GET /api/v1/tasks/{task_id}/steps/{priority}/output — полный output одного шага
```

Но это не Phase 1-3 задача.

**Вердикт:** возвращать по умолчанию, truncate на 20K символов с флагом `output_truncated`. Не усложнять API раньше времени.

---

## 4. Task + steps + events: одна транзакция или раздельно?

**Task + steps в одной транзакции. Events — отдельно, best-effort.**

Это продолжение уже принятого решения. Текущий `_append_event_safe` уже выражает эту философию:

```python
def _append_event_safe(self, event: TaskEventRecord) -> None:
    try:
        self._repository.append_event(event)
    except Exception:
        return
```

Events — observability. Потеря события — degradation, не corruption. Потеря task или step — потеря данных.

### Конкретная реализация

```python
def save_task_with_steps(self, task: TaskRecord, steps: list[TaskStepRecord]) -> None:
    """Атомарно: task + все steps."""
    with self._connect() as conn:
        with conn.cursor() as cursor:
            cursor.execute(UPSERT_TASK_SQL, self._task_params(task))
            for step in steps:
                cursor.execute(INSERT_STEP_SQL, self._step_params(step))
        conn.commit()

def append_event_safe(self, event: TaskEventRecord) -> None:
    """Best-effort: отдельная транзакция, тихий failure."""
    try:
        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.execute(INSERT_EVENT_SQL, self._event_params(event))
            conn.commit()
    except Exception:
        logging.warning("Failed to append event %s for task %s", event.event_id, event.task_id)
```

### Почему не всё в одной транзакции

Если event INSERT упадёт (constraint violation, timeout, disk full), он утянет за собой ROLLBACK task + steps. Потерять observability data — допустимо. Потерять execution results из-за ошибки в логировании — нет.

### Почему task + steps обязаны быть атомарными

Task без steps — corrupted data. Оператор видит "completed" task, но не видит, какая модель ответила. Steps без task — orphaned records (FK constraint не даст, но логически бессмысленно).

Одна транзакция гарантирует: либо полный task со всеми steps, либо ничего.

**Вердикт:** `save_task_with_steps()` — одна транзакция. Events — отдельные best-effort вызовы с logging.warning при failure.

---

## 5. Cancel on quorum: жёсткая отмена или мягкий cancel_requested?

**Мягкая модель. `cancel_requested` с cooperative cancellation.**

### Почему не жёсткий cancel

Жёсткая отмена (`Thread.interrupt()`, `Task.cancel()`) имеет три проблемы:

1. **Browser adapter не поддерживает instant cancel.** Playwright page.goto() или waitForSelector() — blocking операции. Прерывание посреди browser interaction может оставить сессию в broken state.

2. **API adapter может поддерживать, но HTTP request уже ушёл.** urllib/httpx не позволяют отменить in-flight HTTP request без закрытия сокета. Закрытие сокета — side effect, который может вызвать retry на стороне провайдера.

3. **Семантика "отменено" неоднозначна.** Если adapter уже получил ответ, но ещё не вернул его — это cancelled или completed? Жёсткий cancel теряет готовый результат.

### Как устроен мягкий cancel

```python
@dataclass
class CancellationToken:
    _requested: bool = False

    def request_cancel(self) -> None:
        self._requested = True

    @property
    def is_cancelled(self) -> bool:
        return self._requested
```

```python
# В ExecutionRequest добавляется токен:
@dataclass(frozen=True, slots=True)
class ExecutionRequest:
    ...
    cancellation: CancellationToken | None = None
```

```python
# Router при достижении quorum:
for step in remaining_steps:
    request.cancellation.request_cancel()
# Уже запущенные шаги проверяют токен в safe points
```

```python
# Адаптер проверяет перед тяжёлыми операциями:
class MistralApiAdapter(ExecutionAdapter):
    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        if request.cancellation and request.cancellation.is_cancelled:
            return self._cancelled_result(request)

        # ... делает HTTP-вызов ...

        # Проверяет ещё раз после получения ответа
        if request.cancellation and request.cancellation.is_cancelled:
            # Результат уже есть — всё равно вернуть, не выбрасывать
            return result
```

### Контракт для адаптеров

- Адаптер **может** проверять `cancellation.is_cancelled` в safe points
- Адаптер **не обязан** это делать — если не проверяет, шаг просто завершится нормально
- Адаптер **не должен** прерывать себя посреди I/O операции

Это cooperative cancellation — как `CancellationToken` в C# или `context.Done()` в Go.

### Статусы при cancel

```
Шаг не начался + cancel_requested → status = "cancelled" (в gk_task_steps)
Шаг начался + cancel_requested    → шаг завершается нормально (completed/failed)
Шаг завершился до cancel          → completed/failed (не меняется)
```

**Вердикт:** мягкий cancel через CancellationToken. Cooperative, не принудительный. Адаптеры проверяют токен перед тяжёлыми операциями, но не обязаны прерываться.

---

## 6. Нужен ли domain object для ExecutionProfile вместо строки?

**Да. Прямо сейчас.**

Строка `execution_profile: str = "api-only"` в Settings — это неявный контракт. Что входит в "api-only"? Какие адаптеры required? Это знание размазано между Settings и readiness logic.

### Domain object

```python
@dataclass(frozen=True, slots=True)
class ExecutionProfile:
    name: str
    required_adapters: frozenset[str]
    optional_adapters: frozenset[str]
    storage_required: bool = True  # всегда True, но explicit

    def is_required(self, adapter_name: str) -> bool:
        return adapter_name in self.required_adapters

    def is_known(self, adapter_name: str) -> bool:
        return adapter_name in self.required_adapters or adapter_name in self.optional_adapters
```

### Предустановленные профили

```python
PROFILES: dict[str, ExecutionProfile] = {
    "dry-run": ExecutionProfile(
        name="dry-run",
        required_adapters=frozenset({"dry-run"}),
        optional_adapters=frozenset({"api.mistral", "browser.perplexity"}),
    ),
    "api-only": ExecutionProfile(
        name="api-only",
        required_adapters=frozenset({"dry-run", "api.mistral"}),
        optional_adapters=frozenset({"browser.perplexity"}),
    ),
    "hybrid": ExecutionProfile(
        name="hybrid",
        required_adapters=frozenset({"dry-run", "api.mistral", "browser.perplexity"}),
        optional_adapters=frozenset(),
    ),
}


def resolve_profile(name: str) -> ExecutionProfile:
    profile = PROFILES.get(name)
    if profile is None:
        raise ValueError(f"Unknown execution profile: {name}")
    return profile
```

### Использование

```python
# Settings хранит строку (для env var)
@dataclass(frozen=True, slots=True)
class Settings:
    ...
    execution_profile: str = "dry-run"

# main.py резолвит в domain object
profile = resolve_profile(active_settings.execution_profile)
app.state.execution_profile = profile

# readiness.py использует domain object
def build_readiness_report(
    *,
    profile: ExecutionProfile,
    repository: TaskRepository,
    adapters: dict[str, object],
) -> dict[str, Any]:
    for name, adapter in adapters.items():
        required = profile.is_required(name)
        ...
```

### Почему сейчас, а не позже

Три причины:

1. **Readiness logic уже нуждается в этом.** Вопрос 3 из answers.md показал, что readiness без required/optional — шум. ExecutionProfile — единственное место, где эта информация определяется.

2. **20 строк кода.** Dataclass + dict + функция. Не framework, не DI container. Добавляется за 5 минут, упрощает readiness, config validation и будущий wiring.

3. **Поздние добавления сложнее.** Если readiness, planning и router начнут читать execution_profile как строку и интерпретировать каждый по-своему, рефакторинг в domain object потребует изменений в 3+ модулях вместо одного.

**Вердикт:** да, domain object. Прямо сейчас. 20 строк, три use case, zero over-engineering.
