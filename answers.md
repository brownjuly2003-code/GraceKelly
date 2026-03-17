# GraceKelly — Ответы на архитектурные вопросы

**Дата:** 16 марта 2026

---

## 1. Достаточно ли хороша текущая схема данных для PostgreSQL, или менять до начала миграций?

**Да, менять.** Текущая схема имеет конкретные проблемы, которые дешевле исправить сейчас, чем мигрировать потом.

**Что не так:**

Вся multi-model информация спрятана в `metadata JSONB`. В orchestrator.py:

```python
metadata["requested_models_resolved"] = [
    {"id": step.model.id, "display_name": step.model.display_name}
    for step in execution_plan.steps
]
```

Результат каждой модели — тоже в JSONB внутри `metadata["execution"]["results"]`. Это означает:
- Нельзя сделать `SELECT * FROM ... WHERE model_id = 'gpt-5-4'` по отдельным результатам
- Нельзя посчитать success rate по моделям без JSON-парсинга
- Нет индексов на per-step данные

**Что добавить:**

```
gk_tasks              — без изменений + completed_at, duration_ms
gk_task_steps (NEW)   — task_id, step_priority, model_id, backend,
                         status, output_text, failure_code, duration_ms
gk_task_events        — без изменений
```

`gk_task_steps` — нормализованное представление того, что сейчас лежит в JSONB. Одна строка = один результат одной модели в рамках одного task.

Также в `gk_tasks`:
- **`completed_at TIMESTAMPTZ NULL`** — сейчас нет момента завершения, только `accepted_at`
- **`duration_ms INTEGER NULL`** — без этого невозможно анализировать производительность

`metadata JSONB` оставить для действительно произвольных данных (trace_id, user tags), а не для структурированных execution results.

**Вердикт:** менять сейчас. Три поля + одна таблица. После первой миграции это будет стоить в 10 раз дороже.

---

## 2. Правильно ли browser и api равноправны под одним orchestration contract?

**На уровне контракта — да, абсолютно правильно.** `ExecutionAdapter` ABC — чистый и минимальный:

```python
class ExecutionAdapter(ABC):
    def execute(self, request: ExecutionRequest) -> ExecutionResult
    def healthcheck(self) -> dict[str, Any]
```

Оркестратору не нужно знать, как именно выполняется запрос. Это правильная граница.

**Но есть нюанс, который текущий контракт не выражает:** browser и API адаптеры имеют радикально разные операционные характеристики:

| Характеристика | API | Browser |
|---|---|---|
| Latency | 1-10 сек | 15-120 сек |
| Stateful | Нет | Да (сессия, cookies) |
| Concurrency | Высокая | Очень низкая (1-2 потока) |
| Reliability | 99%+ | 70-90% |
| Retry-безопасность | Да | Осторожно |

Сейчас `ExecutionPlan` и `ExecutionRouter` не учитывают эти различия. Router проходит шаги одинаково, без разницы browser это или api.

**Что нужно:** Не ломать контракт адаптера, но добавить operational hints на уровне `ExecutionStep` или `ModelSpec`:

```python
@dataclass(frozen=True, slots=True)
class ModelSpec:
    ...
    expected_latency_class: str = "fast"  # fast | slow
    concurrency_limit: int = 10           # 1-2 для browser
```

Тогда planning layer сможет принимать умные решения: browser-шаги ставить первыми (запускать раньше), а не ждать их в конце. Или наоборот — ставить api-шаги первыми, если quorum=1 и нужен быстрый first_success.

**Вердикт:** равноправность на уровне контракта — оставить. Но planning/routing должен знать о различиях через metadata, не через тип адаптера.

---

## 3. Нормально ли degraded readiness при выключенном browser, или разделить required/optional?

**Нет. Текущий подход создаёт шум и снижает ценность readiness endpoint.**

Система, намеренно запущенная в API-only режиме, не должна кричать "degraded". Иначе это alert fatigue — оператор привыкает к "degraded" и пропускает реальные проблемы.

**Решение — разделение на required и optional:**

В `Settings` добавить явное объявление ожидаемых компонентов:

```python
@dataclass
class Settings:
    ...
    required_adapters: tuple[str, ...] = ("dry-run",)
    optional_adapters: tuple[str, ...] = ("api.mistral", "browser.perplexity")
```

В `build_readiness_report`:

```
required component failed    → status = "failed"
required component degraded  → status = "degraded"
optional component failed    → status = "ok" (но компонент помечен в details)
optional component degraded  → status = "ok"
all required OK              → status = "ok"
```

Деталь каждого компонента всё равно видна в `components[]` — можно посмотреть, что browser выключен. Но **overall status отражает реальную готовность**, а не cosmetic completeness.

**Вердикт:** разделить. Текущее решение в issue log ("treat degraded as informative") — это workaround, а не архитектура.

---

## 4. Minimum viable quorum/merge policy для первого production multi-model execution

**MVP: `quorum=1` + `merge_strategy=first_success`.** Это значит:

- Отправить промпт N моделям (параллельно, когда async будет готов)
- Вернуть результат первой успешной
- Остальные — дождаться или отменить

Это покрывает два главных use case:
1. **Single model** (quorum=1, models=1): обычный запрос
2. **Redundant execution** (quorum=1, models=3): отправить трём, вернуть первый ответ. Защита от timeout/unavailable одного провайдера.

**Что НЕ нужно в MVP:**

- `quorum=N` (все должны ответить) — усложняет error handling и timeout policy
- `merge_strategy=concat` — конкатенация ответов нескольких моделей редко полезна без post-processing
- `merge_strategy=vote` / `merge_strategy=best` — требует оценки качества ответов, что само по себе LLM-задача

**Что стоит добавить сразу рядом с MVP:**

- **Timeout per step:** если модель не ответила за X секунд — failure, переход к следующей (при quorum=1 это даёт бесплатный fallback)
- **Cancel on quorum:** как только quorum набран — остальные шаги можно не ждать

Текущий `ExecutionRouter._aggregate()` уже реализует quorum-логику корректно:

```python
if len(successful) >= plan.quorum:
    task_status = "completed"
```

Не хватает только cancel-on-quorum и timeout. Это укладывается в текущую архитектуру без ломки контрактов.

**Вердикт:** `quorum=1, first_success, timeout=30s` — production-ready минимум.

---

## 5. Где провести жёсткую границу между orchestration core и browser worker?

**Граница проходит по `ExecutionAdapter.execute()`. Ничего browser-специфичного не должно быть видно выше этой линии.**

Текущий код **почти** соблюдает это, но есть нарушение в `main.py`:

```python
from gracekelly.adapters.browser.perplexity import PerplexityBrowserAdapter
from gracekelly.adapters.browser.policy import (
    AuthRecoveryPolicy, ModelVerificationPolicy, PopupPolicy, SubmitPolicy,
)
from gracekelly.adapters.browser.session import BrowserSessionConfig, BrowserSessionManager
```

`main.py` знает о popup policies, auth recovery, session management. Это wiring, и для monolith-а это допустимо, но это именно то место, где old repo расползся.

**Правило: orchestration core (core/, storage/, api/) не должен импортировать ничего из adapters/browser/.**

Конкретная граница:

```
╔══════════════════════════════════════════╗
║  ORCHESTRATION CORE                      ║
║  core/orchestrator.py                    ║
║  core/router.py                          ║
║  core/planning.py                        ║
║  core/contracts.py  ← граница            ║
║  core/models.py                          ║
║  storage/*                               ║
║  api/routes/*                            ║
╠══════════════════════════════════════════╣
║  ADAPTER REGISTRATION (main.py)          ║
║  Знает о конкретных адаптерах.           ║
║  Единственное место, где browser         ║
║  импортируется.                          ║
╠══════════════════════════════════════════╣
║  BROWSER WORKER (adapters/browser/*)     ║
║  Playwright, DOM selectors, session mgmt ║
║  Знает только о contracts.py             ║
╠══════════════════════════════════════════╣
║  API WORKERS (adapters/api/*)            ║
║  HTTP clients, auth tokens               ║
║  Знает только о contracts.py             ║
╚══════════════════════════════════════════╝
```

**Три правила, которые предотвращают расползание:**

1. **`core/` никогда не импортирует `adapters/`** — ни прямо, ни через re-export. Сейчас это соблюдается.

2. **`adapters/browser/` никогда не импортирует `storage/`** — browser worker не пишет в базу. Он возвращает `ExecutionResult`, а orchestrator сам решает, что с ним делать. Сейчас это тоже соблюдается.

3. **Browser worker — отдельный процесс в Phase 4+.** Пока monolith, но архитектура должна позволить вынести browser worker в отдельный процесс, который общается с orchestrator по HTTP или через очередь. Для этого: никакого shared mutable state между orchestrator и browser adapter кроме `execute(request) -> result`.

**Красный флаг, который нужно мониторить:** если в `core/orchestrator.py` появится `if step.backend == "browser": <special logic>` — это начало расползания. Вся browser-специфика должна быть инкапсулирована внутри адаптера.

**Вердикт:** граница сейчас правильная. Держать её — вопрос дисциплины. Правила выше — guard rails.
