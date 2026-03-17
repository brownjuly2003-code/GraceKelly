# GraceKelly — Ответы на архитектурные вопросы (часть 5)

**Дата:** 16 марта 2026

---

## 1. adapter_name в API: deprecated и убрать из v1, или computed compatibility field?

**Оставить как computed field в v1. Не deprecated.**

### Почему не убирать

adapter_name — полезная информация для потребителя API. "Кто дал результат?" — естественный вопрос. Убрать его — заставить клиента самостоятельно агрегировать steps, чтобы получить ответ на простой вопрос.

Deprecated означает "мы это уберём". Но нет причины убирать — есть причина перестать хранить. Это разные вещи.

### Как оформить

```python
class OrchestrateResponse(BaseModel):
    ...
    adapter_name: str  # computed, не хранится в gk_tasks

    @classmethod
    def from_task(cls, task: TaskRecord, steps: list[TaskStepRecord]) -> "OrchestrateResponse":
        adapter_name = cls._resolve_adapter_name(task, steps)
        return cls(..., adapter_name=adapter_name, ...)

    @staticmethod
    def _resolve_adapter_name(task: TaskRecord, steps: list[TaskStepRecord]) -> str:
        if task.dry_run:
            return "dry-run"
        successful = [s for s in steps if s.status == "completed"]
        if not successful:
            failed = [s for s in steps if s.status == "failed"]
            adapters = {f"{s.backend}.{s.provider}" for s in failed}
        else:
            adapters = {f"{s.backend}.{s.provider}" for s in successful}
        if len(adapters) == 1:
            return adapters.pop()
        return "multi"
```

Семантика стабильная:
- Single adapter → его имя
- Multiple adapters → `"multi"`
- Dry run → `"dry-run"`

Клиенту не нужно знать, что это computed. Поле ведёт себя точно как раньше, только source of truth — steps, а не колонка в gk_tasks.

### Что убрать

Колонку `adapter_name` из DDL gk_tasks. Не поле из API response.

**Вердикт:** computed field в API response. Не deprecated — полезен. Не хранится в БД — вычисляется из steps.

---

## 2. step_priority переименовать в step_order или step_index?

**Да. Переименовать в `step_index`. До freeze схемы.**

### Почему step_priority плохо

"Priority" в software engineering означает "важность, определяющую порядок обработки при конкуренции за ресурсы". Priority 1 обычно = самый важный. Это подразумевает, что шаг с priority=1 должен быть предпочтён шагу с priority=2 при нехватке ресурсов.

Но текущая семантика — просто порядковый номер: первый в списке = 1, второй = 2. Нет конкуренции за ресурсы, нет preemption. Это sequence position, а не priority.

### Почему step_index, а не step_order

| Название | Проблема |
|----------|----------|
| step_order | Неоднозначно: "order" = и "порядок", и "заказ". `ORDER BY step_order` читается как тавтология. |
| step_index | Однозначно: нулевой или единичный индекс позиции. Привычно для разработчиков. `ORDER BY step_index` — чисто. |
| step_number | Приемлемо, но длиннее и менее идиоматично для PK. |
| step_seq | Слишком коротко, путается с DB sequences. |

### 0-based или 1-based?

**1-based.** Причины:

- Текущий код уже генерирует `priority` начиная с 1: `enumerate(requested_models, start=1)`
- PostgreSQL ROW_NUMBER() — 1-based
- В API для оператора "шаг 1" понятнее, чем "шаг 0"

### Что менять

```sql
-- DDL
PRIMARY KEY (task_id, step_index)  -- было step_priority
```

```python
# planning.py
for step_index, model in enumerate(requested_models, start=1):
    steps.append(ExecutionStep(..., step_index=step_index))

# contracts.py
@dataclass(frozen=True, slots=True)
class ExecutionStep:
    ...
    step_index: int  # было priority
```

Rename в 4 файлах: contracts.py, planning.py, router.py, orchestrator.py. Все внутренние, API не затронут (step_index не экспонируется в текущем OrchestrateResponse). В будущем TaskStepView будет содержать `step_index`.

**Вердикт:** переименовать в `step_index`, 1-based. Сейчас — бесплатно. После freeze схемы — миграция + rename в коде + потенциальный breaking change в API.

---

## 3. Добавить nullable retry_of_task_id в gk_tasks сейчас?

**Нет. Не добавлять.**

### Почему нет — те же аргументы, что для attempt_no, но сильнее

retry_of_task_id предполагает конкретную модель retry: "новый task, ссылающийся на предыдущий". Но это одна из минимум трёх возможных стратегий:

| Стратегия | Как устроена | retry_of_task_id нужен? |
|-----------|-------------|------------------------|
| Retry as new task | Новый task_id, ссылка на старый | Да |
| Retry in place | Тот же task_id, новые steps с attempt_no | Нет |
| Retry with fallback | Новый task_id, другие модели | Может быть, но семантика другая — это fallback, не retry |

Добавить `retry_of_task_id` сейчас — зафиксировать стратегию "retry as new task" без анализа альтернатив. Это ровно то, от чего предостерегает YAGNI: решение, которое выглядит дешёвым (nullable колонка), но сужает design space.

### Дополнительный аргумент

Nullable колонка, которая NULL в 100% строк месяцами:
- Засоряет `SELECT *` и debug output
- Провоцирует вопросы "когда это заполняется?"
- Создаёт соблазн начать использовать не по назначению ("давайте retry_of_task_id для linked tasks тоже")

### Стоимость добавления позже

```sql
ALTER TABLE gk_tasks ADD COLUMN retry_of_task_id TEXT NULL REFERENCES gk_tasks(task_id);
CREATE INDEX IF NOT EXISTS idx_gk_tasks_retry_of ON gk_tasks(retry_of_task_id) WHERE retry_of_task_id IS NOT NULL;
```

Одна миграция, partial index, zero backfill (все существующие строки — NULL, что корректно). Стоимость добавления позже — идентична стоимости добавления сейчас.

**Вердикт:** не добавлять. Нулевая выгода сейчас, нулевая экономия на будущей миграции, ненулевой риск premature commitment к одной retry-стратегии.

---

## 4. UNIQUE constraint на (task_id, sequence_no) для gk_task_events?

**Да. UNIQUE, а не просто индекс.**

### Зачем

sequence_no — ordering key для событий одного task. Два события с одинаковым `(task_id, sequence_no)` = corrupted data. Это инвариант, и он должен быть enforced на уровне БД, а не только приложения.

Индекс без UNIQUE:
- Ускоряет `ORDER BY sequence_no` ✓
- Не защищает от дубликатов ✗

UNIQUE constraint:
- Ускоряет `ORDER BY sequence_no` ✓
- Защищает от дубликатов ✓
- PostgreSQL реализует UNIQUE через B-tree index — отдельный индекс не нужен

### Как оформить

PK таблицы — `event_id`. Это правильно: event_id — глобально уникальный идентификатор события. `(task_id, sequence_no)` — уникальный внутри scope одного task.

```sql
CREATE TABLE IF NOT EXISTS gk_task_events (
    event_id     TEXT        PRIMARY KEY,
    task_id      TEXT        NOT NULL REFERENCES gk_tasks(task_id) ON DELETE CASCADE,
    sequence_no  INTEGER     NOT NULL,
    event_type   TEXT        NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL,
    payload      JSONB       NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (task_id, sequence_no)
);
```

Отдельный `CREATE INDEX` на `(task_id, sequence_no)` — не нужен. UNIQUE constraint создаёт его автоматически.

### Поведение при нарушении

Если приложение случайно попытается записать два события с одинаковым sequence_no для одного task:

```
ERROR: duplicate key value violates unique constraint "gk_task_events_task_id_sequence_no_key"
```

Это **правильное** поведение. Лучше получить ошибку и обнаружить баг в счётчике, чем тихо записать дубликат и получить corrupted event history.

В контексте best-effort append: если INSERT упал из-за UNIQUE violation — `_append_event_safe` его поглотит (catch Exception). Событие потеряно, но данные не corrupted. Это лучше, чем два события с одинаковым порядком.

**Вердикт:** UNIQUE `(task_id, sequence_no)`. Не индекс — constraint. Защита данных важнее, чем extra event в best-effort сценарии.

---

## 5. Достаточно ли backend + provider, или нужен adapter_name в gk_task_steps?

**Достаточно backend + provider. Без adapter_name.**

### Текущая конвенция именования

```python
# Адаптеры именуются по схеме "{backend}.{provider}":
"api.mistral"          # backend=api, provider=mistral
"browser.perplexity"   # backend=browser, provider=perplexity
"dry-run"              # особый случай
```

`adapter_name` = `f"{backend}.{provider}"`. Это производное значение. Хранить его отдельно — денормализация, идентичная проблеме с adapter_name в gk_tasks (answers3.md, вопрос 2).

### Проверка: есть ли сценарий, где backend + provider недостаточно?

| Сценарий | backend + provider | adapter_name нужен? |
|----------|-------------------|---------------------|
| Два API-адаптера для одного провайдера (mistral-fast, mistral-slow) | api + mistral — коллизия | Да |
| Два browser-адаптера для одного провайдера (perplexity-v1, perplexity-v2) | browser + perplexity — коллизия | Да |
| Один адаптер на провайдера (текущая архитектура) | Достаточно | Нет |

Вопрос: реалистичны ли коллизии?

**Нет — для текущей и обозримой архитектуры.** Один провайдер = один адаптер. Mistral API — один адаптер. Perplexity browser — один адаптер. Нет причины иметь два адаптера к одному провайдеру с разным поведением — это конфигурация (timeout, profile), а не разные адаптеры.

Если появится second adapter к тому же провайдеру (теоретически: `perplexity-headless` vs `perplexity-headed`), решение — расширить `provider` (`perplexity-headless`, `perplexity-headed`), а не добавлять ещё одно поле.

### Dry-run: особый случай

`dry-run` не вписывается в `backend + provider`:
- backend = ??? (не browser и не api)
- provider = ??? (нет провайдера)

Но dry-run шаги не записываются в gk_task_steps с финальными результатами. Dry-run task имеет `gk_tasks.dry_run = TRUE`, и его steps — симуляции. Если всё-таки записывать dry-run steps:

```
backend = "dry-run", provider = "internal"
```

Или проще: dry-run tasks не создают записей в gk_task_steps. Они мгновенные, без реального execution. Events достаточно для observability.

### Итоговая схема gk_task_steps (без adapter_name)

```sql
CREATE TABLE IF NOT EXISTS gk_task_steps (
    task_id         TEXT        NOT NULL REFERENCES gk_tasks(task_id) ON DELETE CASCADE,
    step_index      INTEGER     NOT NULL,
    model_id        TEXT        NOT NULL,
    backend         TEXT        NOT NULL,
    provider        TEXT        NOT NULL,
    status          TEXT        NOT NULL,
    failure_code    TEXT        NULL,
    failure_message TEXT        NULL,
    output_text     TEXT        NULL,
    duration_ms     INTEGER     NULL,
    PRIMARY KEY (task_id, step_index)
);

CREATE INDEX IF NOT EXISTS idx_gk_task_steps_model_id ON gk_task_steps(model_id);
CREATE INDEX IF NOT EXISTS idx_gk_task_steps_status ON gk_task_steps(status);
CREATE INDEX IF NOT EXISTS idx_gk_task_steps_provider ON gk_task_steps(provider);
```

Если нужно имя адаптера для API response — вычислять:

```python
@property
def adapter_name(self) -> str:
    return f"{self.backend}.{self.provider}"
```

**Вердикт:** backend + provider достаточно. adapter_name — computed property, не колонка. Денормализация в gk_task_steps создаёт ту же проблему, которую мы решили для gk_tasks.
