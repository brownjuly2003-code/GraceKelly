# GraceKelly — Ответы на архитектурные вопросы (часть 4)

**Дата:** 16 марта 2026

---

## 1. Surrogate step_id или composite PK task_id + step_priority?

**Composite PK. Без surrogate key.**

### Почему composite достаточен

`(task_id, step_priority)` — естественный и уникальный идентификатор. Один task не может содержать два шага с одинаковым приоритетом — это инвариант execution plan. Composite PK выражает этот инвариант на уровне БД.

Surrogate step_id (UUID) добавляет:
- Ещё один UUID на каждую строку — 36 байт storage + index overhead
- Необходимость генерировать и передавать его через все слои
- Ещё один способ ссылаться на шаг (по id или по task+priority?) — ambiguity

При этом не даёт ничего, что composite PK не даёт. Нет внешних систем, ссылающихся на step_id. Нет API, принимающего step_id. Нет JOIN-ов по step_id.

### Единственный сценарий, где surrogate нужен

Если шаг может быть выполнен несколько раз (retry с attempt_no). Тогда `(task_id, step_priority)` перестаёт быть уникальным, и нужен либо `(task_id, step_priority, attempt_no)`, либо surrogate.

Но это вопрос 3, и ответ на него — не закладывать retry в схему сейчас (см. ниже).

### Конкретное решение

```sql
CREATE TABLE IF NOT EXISTS gk_task_steps (
    task_id         TEXT        NOT NULL REFERENCES gk_tasks(task_id) ON DELETE CASCADE,
    step_priority   INTEGER     NOT NULL,
    -- ... остальные поля ...
    PRIMARY KEY (task_id, step_priority)
);
```

Если позже потребуется surrogate — одна миграция:

```sql
ALTER TABLE gk_task_steps ADD COLUMN step_id TEXT;
UPDATE gk_task_steps SET step_id = gen_random_uuid()::text;
ALTER TABLE gk_task_steps ALTER COLUMN step_id SET NOT NULL;
CREATE UNIQUE INDEX idx_gk_task_steps_step_id ON gk_task_steps(step_id);
```

PK не меняется, surrogate добавляется как unique column. Обратно-совместимо.

**Вердикт:** composite PK `(task_id, step_priority)`. Surrogate добавить когда появится потребитель, ссылающийся на отдельный шаг.

---

## 2. Что означает gk_tasks.adapter_name в mixed-adapter task?

**Текущая семантика сломана. Поле нужно переосмыслить.**

### Проблема

Сейчас `adapter_name` на уровне task определяется так (router.py:100):

```python
adapter_name = adapter_names[0] if len(adapter_names) == 1 else "multi"
```

При single-adapter task — имя адаптера. При mixed — строка `"multi"`. Это:
- Не фильтруемо: `WHERE adapter_name = 'api.mistral'` не найдёт task, где Mistral участвовал наряду с browser
- Не информативно: `"multi"` не говорит, какие адаптеры участвовали
- Не консистентно: семантика зависит от количества адаптеров

### Два варианта решения

#### Вариант A: Убрать adapter_name из gk_tasks, оставить только в gk_task_steps

```sql
-- gk_tasks: убрать adapter_name
-- gk_task_steps: уже есть backend + provider
```

Запрос "какие адаптеры участвовали в задаче?" →

```sql
SELECT DISTINCT backend, provider FROM gk_task_steps WHERE task_id = ?
```

Это нормализованно и правильно. Но ломает текущий API-контракт (`OrchestrateResponse.adapter_name`).

#### Вариант B: Переосмыслить как "primary adapter" — адаптер, давший winning result

```python
# В router._aggregate():
if plan.merge_strategy == "first_success":
    adapter_name = first_successful_result.adapter_name
else:
    adapter_name = adapter_names[0] if len(adapter_names) == 1 else "multi"
```

Семантика: `adapter_name` = "кто дал финальный output_text". При first_success — адаптер первого успешного шага. При single model — единственный адаптер. При concat — "multi" (несколько адаптеров контрибьютили в output).

### Рекомендация

**Вариант A.** Убрать `adapter_name` из `gk_tasks`.

Причины:
- adapter_name на уровне task — производная от step results. Хранить производные данные в parent record — denormalization, которая усложняет update logic.
- С появлением `gk_task_steps` вся per-adapter информация живёт в правильном месте.
- API-контракт меняется минимально: `OrchestrateResponse.adapter_name` вычисляется из steps при сериализации, а не хранится.

```python
class OrchestrateResponse(BaseModel):
    ...
    # adapter_name убрано из хранения, вычисляется при ответе:
    @computed_field
    @property
    def adapter_name(self) -> str:
        adapters = {step.adapter_name for step in self.steps}
        if len(adapters) == 1:
            return adapters.pop()
        return "multi"
```

Если backward compatibility критична на Phase 1, можно оставить `adapter_name` в gk_tasks как computed при INSERT:

```python
task.adapter_name = winning_result.adapter_name  # "кто дал output"
```

Но пометить как deprecated и не использовать для фильтрации.

**Вердикт:** убрать из gk_tasks, вычислять из gk_task_steps. Денормализация в parent record — источник inconsistency при mixed-adapter tasks.

---

## 3. Закладывать ли retry с attempt_no в схему сейчас?

**Нет. Не закладывать.**

### Почему нет

1. **Retry policy не определена.** Нет ответа на базовые вопросы: кто инициирует retry (оркестратор? оператор? автоматически?), какие failure_code retriable, сколько попыток, какой backoff. Закладывать attempt_no без этих решений — проектировать схему под воображаемые требования.

2. **Retry одного шага vs retry всего task — разные стратегии.** Если Mistral вернул timeout, стоит ли повторить тот же шаг (attempt_no=2) или переключиться на другую модель (fallback)? Или повторить весь task? Каждый вариант — разная schema impact.

3. **PK не заблокирует.** Если потребуется attempt_no, миграция тривиальна:

```sql
-- Шаг 1: добавить колонку с дефолтом
ALTER TABLE gk_task_steps ADD COLUMN attempt_no INTEGER NOT NULL DEFAULT 1;

-- Шаг 2: изменить PK (требует пересоздания constraint)
ALTER TABLE gk_task_steps DROP CONSTRAINT gk_task_steps_pkey;
ALTER TABLE gk_task_steps ADD PRIMARY KEY (task_id, step_priority, attempt_no);
```

Это одна миграция, выполняется за секунды на таблице с <100K строк (реалистичный объём для Phase 1-3). Не architectural debt, а запланированное расширение.

4. **Преждевременная абстракция хуже, чем миграция.** attempt_no=1 на каждой строке в течение месяцев — мёртвое поле, которое загромождает код, API responses и debugging output. Каждый разработчик будет спрашивать "а зачем attempt_no, retry же нет?"

### Когда добавлять

Конкретный триггер: **когда retry policy реализована и нужно хранить историю попыток**. Не раньше Phase 4 (Reliability controls).

Если retry появится как "пересоздать весь task" (новый task_id), то attempt_no на уровне steps вообще не нужен — каждый retry = новый task с ссылкой на original.

### Альтернатива: retry как новый task

```python
class TaskRecord:
    ...
    retry_of_task_id: str | None = None  # ссылка на предыдущую попытку
```

Это проще, не ломает PK, и позволяет ретраить task целиком (с другими моделями, другим quorum). Решение о retry_of_task_id vs attempt_no — принять в Phase 4, когда retry policy определена.

**Вердикт:** не закладывать. Composite PK `(task_id, step_priority)` достаточен. Миграция до `(task_id, step_priority, attempt_no)` тривиальна когда потребуется. YAGNI.

---

## 4. Нужен ли sequence_no у gk_task_events?

**Да. Добавить сейчас.**

### Проблема

Текущий порядок событий определяется `created_at`:

```sql
SELECT ... FROM gk_task_events WHERE task_id = %s ORDER BY created_at ASC
```

Два события, записанных в одну миллисекунду (реалистично при best-effort append двух событий подряд), получат одинаковый `created_at`. Порядок между ними — undefined. PostgreSQL не гарантирует стабильный порядок строк с одинаковым sort key.

Текущий код создаёт два события за один submit:

```python
# orchestrator.py:70-96
self._append_event_safe(TaskEventRecord(..., event_type="task.submitted", ...))
self._append_event_safe(TaskEventRecord(..., event_type="task.execution.completed", ...))
```

Оба вызова происходят в одном синхронном потоке. `datetime.now(timezone.utc)` может вернуть одинаковое значение для обоих (Windows timer resolution — 15.6ms, Python datetime — microsecond).

### Решение

```sql
ALTER TABLE gk_task_events ADD COLUMN sequence_no INTEGER NOT NULL DEFAULT 0;
```

```sql
-- Обновить index:
DROP INDEX IF EXISTS idx_gk_task_events_task_id_created_at;
CREATE INDEX IF NOT EXISTS idx_gk_task_events_task_id_seq
ON gk_task_events(task_id, sequence_no);
```

Порядок чтения:

```sql
SELECT ... FROM gk_task_events
WHERE task_id = %s
ORDER BY sequence_no ASC;
```

### Генерация sequence_no

Два варианта:

#### Вариант A: Счётчик на уровне приложения (рекомендую)

```python
class OrchestratorService:
    def _next_sequence(self, task_id: str) -> int:
        """Monotonically increasing per task."""
        self._sequence_counters.setdefault(task_id, 0)
        self._sequence_counters[task_id] += 1
        return self._sequence_counters[task_id]
```

Просто, детерминированно, не зависит от БД. При in-memory backend — работает идентично. При PostgreSQL — тоже, потому что events append-only и один task обрабатывается одним потоком.

#### Вариант B: DB sequence или subquery

```sql
INSERT INTO gk_task_events (event_id, task_id, sequence_no, ...)
VALUES (
    %(event_id)s,
    %(task_id)s,
    COALESCE((SELECT MAX(sequence_no) FROM gk_task_events WHERE task_id = %(task_id)s), 0) + 1,
    ...
);
```

Работает, но добавляет subquery на каждый INSERT. Overkill для append-only событий, где writer — единственный.

**Рекомендация: Вариант A.** Счётчик в памяти. Просто, быстро, достаточно.

### Почему сейчас, а не позже

- Добавить `sequence_no` после накопления данных = миграция с backfill (`UPDATE ... SET sequence_no = row_number() OVER (PARTITION BY task_id ORDER BY created_at)`)
- Добавить сейчас, до первых данных = одна строка в DDL, ноль миграции
- Стоимость: одно INTEGER поле на событие. Бесплатно.

**Вердикт:** добавить `sequence_no INTEGER NOT NULL`. Генерировать в приложении. Сортировать по `sequence_no`, а не по `created_at`. `created_at` остаётся как informational timestamp, но не как ordering key.
