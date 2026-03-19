# GraceKelly — Ответы на архитектурные вопросы (часть 2)

**Дата:** 16 марта 2026

---

## 1. Минимальный состав полей для gk_task_steps в первой миграции

```sql
CREATE TABLE IF NOT EXISTS gk_task_steps (
    task_id         TEXT        NOT NULL REFERENCES gk_tasks(task_id) ON DELETE CASCADE,
    step_priority   INTEGER     NOT NULL,
    model_id        TEXT        NOT NULL,
    backend         TEXT        NOT NULL,   -- "browser" | "api"
    provider        TEXT        NOT NULL,   -- "perplexity" | "mistral"
    status          TEXT        NOT NULL,   -- "completed" | "failed" | "accepted"
    failure_code    TEXT        NULL,
    failure_message TEXT        NULL,
    output_text     TEXT        NULL,
    duration_ms     INTEGER     NULL,
    PRIMARY KEY (task_id, step_priority)
);

CREATE INDEX IF NOT EXISTS idx_gk_task_steps_model_id
ON gk_task_steps(model_id);

CREATE INDEX IF NOT EXISTS idx_gk_task_steps_status
ON gk_task_steps(status);
```

**10 полей. Обоснование каждого:**

| Поле | Зачем | Можно ли убрать |
|------|-------|-----------------|
| task_id | FK, обязателен | Нет |
| step_priority | Порядок в плане, часть PK | Нет |
| model_id | Запросы "покажи все runs по GPT-5.4" | Нет |
| backend | Запросы "сколько browser vs api failures" | Нет |
| provider | "Сколько ошибок на perplexity?" — без provider пришлось бы join с реестром моделей, которого нет в БД | Нет |
| status | Фильтрация, агрегация | Нет |
| failure_code | Диагностика | Нет — нужен для `WHERE failure_code = 'timeout'` |
| failure_message | Текст ошибки для оператора | Можно, но дёшево хранить, дорого воспроизводить |
| output_text | Результат модели | Нет — это core value |
| duration_ms | Производительность | Нет — без него нет observability |

**Что сознательно не включено:**

- **step_id (TEXT PK):** Не нужен. Composite PK `(task_id, step_priority)` — естественный и уникальный. Отдельный UUID добавляет join-ы без пользы.
- **started_at / completed_at:** Не нужны при наличии `duration_ms`. Абсолютное время начала шага можно восстановить из `gk_tasks.accepted_at` + порядка событий. Два лишних TIMESTAMPTZ на каждую строку — overhead без use case.
- **provider_model_id:** Redundant с model_id + provider. Нужен только для дебага провайдера, а для этого есть events.
- **adapter_name:** Derivable из backend + provider.
- **reasoning (BOOLEAN):** Одинаков для всех шагов одного task — лежит в gk_tasks.
- **metadata JSONB:** Если нужны произвольные данные per-step, добавить потом. В MVP — нет.

---

## 2. Убрать step-level results из metadata целиком?

**Да. Полностью.**

Два источника правды для одних и тех же данных — гарантированная рассинхронизация. Если step results живут в `gk_task_steps`, они не должны дублироваться в `gk_tasks.metadata`.

**Что оставить в metadata JSONB:**

```python
# Пользовательские / trace данные
metadata = {
    "trace_id": "abc-123",           # user-provided
    "source": "cli",                  # user-provided
    "tags": ["experiment-42"],        # user-provided
}
```

**Что убрать из metadata (переехало в нормализованные таблицы):**

```python
# ВСЁ это теперь в gk_task_steps и gk_tasks columns:
metadata["execution"]                 # → gk_task_steps
metadata["requested_models"]          # → JOIN gk_task_steps
metadata["requested_models_resolved"] # → JOIN gk_task_steps
metadata["execution_plan"]            # → gk_tasks columns + gk_task_steps
```

**Миграция в OrchestratorService.submit():**

Вместо текущего:
```python
metadata["execution"] = batch_result.details
metadata["requested_models"] = request.requested_model_names()
metadata["requested_models_resolved"] = [...]
metadata["execution_plan"] = {... steps ...}
```

Станет:
```python
# metadata содержит только user-provided данные
metadata = dict(request.metadata)
# step results сохраняются отдельно
for step_result in batch_result.results:
    self._repository.save_step(task_id, step_result)
```

Execution plan details (`quorum`, `merge_strategy`, `dry_run`, `adapter_hint`) стоит вынести в колонки `gk_tasks`, а не хранить в metadata.

**Вердикт:** single source of truth. metadata = только user data. Всё остальное — в нормализованных таблицах.

---

## 3. Как оформить readiness contract: где хранить required/optional и обязателен ли storage?

**Storage — всегда required, без исключений.** Если нельзя записать результат task, система не функциональна. Даже in-memory backend — это "storage работает". Отсутствие storage = отсутствие сервиса.

**Где хранить required/optional adapters:**

В `Settings`, но не как список имён, а как один enum-подобный параметр — **execution profile:**

```python
@dataclass(frozen=True, slots=True)
class Settings:
    ...
    execution_profile: str = "api-only"
    # "api-only"      → required: [storage, api.mistral],     optional: [browser.*]
    # "browser-only"  → required: [storage, browser.perplexity], optional: [api.*]
    # "hybrid"        → required: [storage, api.mistral, browser.perplexity]
    # "dry-run"       → required: [storage, dry-run],          optional: [всё остальное]
```

**Почему profile, а не два списка:**

Два списка (`required_adapters`, `optional_adapters`) — гибко, но error-prone. Оператор может случайно поставить browser в required на сервере без Chrome. Или забыть api в required. Profile — именованная конфигурация, которую можно валидировать целиком.

**Как это влияет на readiness:**

```python
def build_readiness_report(
    *,
    environment: str,
    execution_profile: str,
    repository: TaskRepository,
    adapters: dict[str, object],
) -> dict[str, Any]:
    required, optional = resolve_requirements(execution_profile, adapters)

    # storage всегда required
    components = [storage_component_status(repository, required=True)]

    for name, adapter in adapters.items():
        is_required = name in required
        components.append(adapter_component_status(name, adapter, required=is_required))

    # overall status учитывает только required
    required_statuses = [c for c in components if c["required"]]
    ...
```

Каждый компонент в ответе получает поле `"required": true/false` — оператор видит, что browser degraded, но знает, что это optional.

**Вердикт:** storage = always required. Adapters — через execution profile в Settings. Profile проще валидировать, чем два произвольных списка.

---

## 4. Какие operational hints добавить в ModelSpec прямо сейчас?

**Три. Не больше.**

```python
@dataclass(frozen=True, slots=True)
class ModelSpec:
    id: str
    display_name: str
    aliases: tuple[str, ...]
    adapter_kind: str
    provider: str
    provider_model_id: str
    reasoning_capable: bool = False
    # --- operational hints ---
    timeout_seconds: float = 30.0
    expected_latency_class: str = "fast"   # "fast" | "slow"
    concurrency_limit: int = 10
```

**Обоснование каждого:**

### timeout_seconds — ДОБАВИТЬ

Необходим для первого production run. Без timeout вызов к недоступному провайдеру повиснет навсегда. У каждой модели должен быть свой timeout:

```python
ModelSpec(id="mistral-small", ..., timeout_seconds=30.0)     # API — быстрый
ModelSpec(id="claude-sonnet-4-6", ..., timeout_seconds=90.0)  # Browser — медленный
```

Прямо сейчас timeout живёт только в MistralApiAdapter. Это неправильное место — timeout должен определяться моделью, а не адаптером. Адаптер читает `request.step.model.timeout_seconds`.

### expected_latency_class — ДОБАВИТЬ

Нужен для planning layer. Когда quorum=1 + first_success + параллельное выполнение, planner должен знать, что api-модель ответит за 3 сек, а browser — за 40. Это влияет на cancel-on-quorum: если api уже ответил, browser можно отменить.

Два значения достаточно: `"fast"` (API, <10s) и `"slow"` (browser, 10-120s). Не число в секундах — это ложная точность.

### concurrency_limit — ДОБАВИТЬ

Нужен при параллельном выполнении. API адаптер может обработать 10+ одновременных запросов. Browser — максимум 1-2 (физически один Chrome). Без этого параллельный execution сломает browser канал.

### Что НЕ добавлять:

| Hint | Почему нет |
|------|-----------|
| cost_class | Нет биллинга, нет use case для решений на основе стоимости |
| supports_streaming | Нет streaming в архитектуре. Добавить, когда появится |
| retry_safe | Все API retry-safe. Browser — зависит от реализации, рано определять |
| priority / weight | Over-engineering для Phase 1. Порядок в `models[]` запроса — достаточный priority |

**Вердикт:** `timeout_seconds`, `expected_latency_class`, `concurrency_limit`. Три поля, три реальных use case. Всё остальное — YAGNI.

---

## 5. Policy для первого production run: что поменять в defaults?

Предложенный набор: `quorum=1, first_success, timeout=30s, cancel_on_quorum=true`.

**Поменять одно: timeout должен быть per-model, а не глобальный.**

```
quorum=1                  — оставить ✓
first_success             — оставить ✓
cancel_on_quorum=true     — оставить ✓
timeout=30s (глобальный)  — заменить на per-model timeout ✗
```

**Почему per-model timeout:**

Глобальный timeout=30s сломает browser-канал (нормальный ответ через Perplexity = 30-90 сек). А timeout=90s — слишком долго для API-модели, которая обычно отвечает за 3-5 сек.

Правильный подход:

```python
# В ModelSpec:
ModelSpec(id="mistral-small", ..., timeout_seconds=30.0)
ModelSpec(id="claude-sonnet-4-6", ..., timeout_seconds=90.0)
ModelSpec(id="kimi-k2-5", ..., timeout_seconds=90.0)
```

```python
# В ExecutionRouter, per-step:
result = await asyncio.wait_for(
    adapter.execute(request),
    timeout=request.step.model.timeout_seconds,
)
```

**Итоговые defaults для OrchestrateRequest:**

```python
class OrchestrateRequest(BaseModel):
    ...
    quorum: int = 1
    merge_strategy: str = "first_success"   # изменить default с "best_effort"
    cancel_on_quorum: bool = True            # новое поле
    # timeout НЕ на уровне запроса — он в ModelSpec
```

Отдельно: стоит переименовать текущий default `merge_strategy="best_effort"` в `"first_success"`. "best_effort" — расплывчатое название, которое не описывает конкретное поведение. Текущая реализация `_merge_outputs` при best_effort делает `"\n\n".join(outputs)` — это concat, а не best_effort.

**Вердикт:** quorum=1, first_success, cancel_on_quorum=true, per-model timeout. Единственное реальное изменение — timeout granularity.

---

## 6. Нужен ли уже сейчас endpoint GET /tasks/{task_id}/steps?

**Нет. Пока достаточно расширить существующий GET /tasks/{task_id}.**

```python
class TaskView(OrchestrateResponse):
    prompt: str
    reasoning: bool
    metadata: dict[str, Any]
    events: list[TaskEventView] = Field(default_factory=list)
    steps: list[TaskStepView] = Field(default_factory=list)   # ← добавить
```

Один endpoint возвращает task + steps + events. Это покрывает 100% use cases на текущем этапе:
- Оператор смотрит результат задачи → видит все step results inline
- Дебаг failure → видит failure_code каждого шага
- Duration analysis → видит duration_ms каждого шага

**Когда отдельный endpoint станет нужен:**

- Когда steps содержат большие output_text (>100KB) и полный TaskView становится слишком тяжёлым
- Когда появится пагинация по шагам (>50 шагов в одном task) — маловероятно
- Когда появится use case "дай мне только шаг N" — специфический дебаг

Ни один из этих сценариев не реалистичен для Phase 1-3. Максимум 4-5 моделей в одном task.

**Вердикт:** не создавать. Добавить `steps: list[TaskStepView]` в существующий TaskView. Ревизировать когда task содержит >10 шагов или >100KB per step.

---

## 7. Оставить browser wiring в main.py или выносить в отдельный module?

**Оставить в main.py. Сейчас не время.**

`main.py` — 97 строк. Это composition root. Он делает ровно одну вещь: создаёт зависимости и связывает их. Вынос в отдельный `bootstrap.py` или `container.py` добавит:
- Один лишний файл
- Один лишний import
- Один лишний уровень indirection

Без пользы. `main.py` читается за 30 секунд.

**Когда выносить:**

Конкретный триггер — **третье семейство адаптеров** или **main.py > 150 строк**. Сейчас два семейства (api, browser) + dry-run. Если появится, например, `adapters/mcp/` для MCP-интеграции, тогда:

```python
# adapters/registry.py
def build_adapter_registry(settings: Settings) -> dict[str, ExecutionAdapter]:
    registry = {"dry-run": DryRunExecutionAdapter()}
    registry.update(build_api_adapters(settings))
    registry.update(build_browser_adapters(settings))
    return registry
```

Но не раньше.

Другой триггер — если wiring начнёт содержать **логику** (if/else на конфигурацию, retry, health pre-check). Пока wiring — это прямолинейное создание объектов, он принадлежит в main.py.

**Вердикт:** оставить. Рефакторить при третьем adapter family или >150 строк. Не раньше.

---

## 8. Когда выносить browser worker в отдельный процесс?

**После подтверждения полезности browser mode. Не раньше.**

Три стадии:

### Стадия 1: Monolith (сейчас → Phase 2-3)
Browser adapter живёт в том же процессе. Playwright запускается in-process. Это нормально для:
- Разработки и отладки
- Single-user режима
- Proof of concept browser канала

### Стадия 2: Подтверждение полезности (конец Phase 3)
Критерий: browser канал работает, используется минимум 2 недели, приносит реальную ценность. Если за 2 недели выяснится, что API adapters покрывают 95% потребностей — browser worker не нужно выносить. Его нужно депреоритизировать.

### Стадия 3: Выделение в отдельный процесс (Phase 4, если Stage 2 подтвердил ценность)
Конкретные причины для выделения:
- Chrome жрёт 500MB+ RAM и может упасть — не должен уносить orchestrator
- Browser execution = 30-90 сек, блокирует concurrency даже в async
- Нужно масштабировать browser workers отдельно (2-3 Chrome instance на разных машинах)

**Архитектурная подготовка, которую стоит сделать сейчас (Phase 1), без выноса:**

Единственное что нужно — **не создавать shared mutable state** между orchestrator и browser adapter. Текущий код уже соблюдает это: `BrowserSessionState` mutable, но принадлежит только `BrowserSessionManager`, который передаётся только в browser adapter.

Если завтра нужно вынести browser worker в отдельный процесс, рефакторинг будет:

```python
# Вместо:
browser_adapter = PerplexityBrowserAdapter(session_manager=...)
router = ExecutionRouter(browser_adapter=browser_adapter)

# Станет:
browser_adapter = RemoteBrowserAdapter(url="http://browser-worker:8012")
router = ExecutionRouter(browser_adapter=browser_adapter)
```

`RemoteBrowserAdapter` реализует тот же `ExecutionAdapter` ABC, но делает HTTP-вызов к отдельному процессу. Orchestrator core не изменяется ни на строку. Это возможно именно потому, что граница (вопрос 5 из предыдущего файла) проходит по `ExecutionAdapter.execute()`.

**Вердикт:** выносить после подтверждения полезности. Не до Playwright-интеграции (нечего выносить), не сразу после (рано оценивать). После 2+ недель реального использования. Архитектура уже готова к выносу — adapter interface это позволяет без изменений в core.
