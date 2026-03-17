# GraceKelly — Всесторонний аудит проекта

**Дата:** 16 марта 2026
**Ревизор:** Claude Opus 4.6
**Статус проекта:** Phase 1 завершена, Phase 2+ не начаты
**Тесты:** 16/16 pass (Python 3.12)

---

## 1. Суть проекта и актуальность

### Что это
GraceKelly — оркестратор для выполнения LLM-запросов через два канала:
- **Browser adapters** — отправка промптов через UI провайдеров (Perplexity → Claude/GPT/Gemini/Kimi)
- **API adapters** — прямые API-вызовы (Mistral)

Ключевая идея: multi-model execution с кворумом, merge-стратегиями и единым каноническим реестром моделей.

### Актуальность (март 2026)

**Сильные стороны идеи:**
- Browser-routed LLM execution остаётся практически нишевой задачей. Большинство инструментов (LiteLLM, OpenRouter, RouteLLM) работают только через API. GraceKelly закрывает реальный gap для пользователей, которые хотят использовать модели, доступные через UI Perplexity, но не имеющие отдельного API (или имеющие его по завышенным ценам).
- Multi-model orchestration с кворумом — зрелая концепция. В марте 2026 существуют решения (MoA, RouteLLM), но они все API-only. Гибридный browser+API подход — уникальное позиционирование.

**Риски идеи:**
- **Юридический риск:** Browser automation для обхода UI провайдера может нарушать ToS Perplexity. Это главный экзистенциальный риск проекта. Если Perplexity изменит ToS или начнёт активно блокировать автоматизацию (CAPTCHA, fingerprinting), весь browser-канал может стать нежизнеспособным в одну ночь.
- **Хрупкость browser-канала:** UI Perplexity обновляется без предупреждения. Каждое обновление DOM-структуры потребует починки селекторов. Это не разовая инвестиция, а постоянная maintenance burden.
- **Конкурентная динамика:** К марту 2026 практически все top-tier модели имеют доступные API (Claude через Anthropic, GPT через OpenAI, Gemini через Google AI Studio). Единственный аргумент за browser routing — цена (free tier Perplexity) или доступ к моделям без отдельного API-ключа. Этот аргумент ослабевает с каждым месяцем.
- **Масштаб:** Проект предназначен для одного пользователя или малой команды. Это нормально, но стоит явно это зафиксировать, чтобы не over-engineer.

### Вердикт по актуальности
Проект имеет **нишевую, но реальную** ценность для personal/small-team use. Как личный инструмент — вполне обоснован. Как продукт для широкой аудитории — рискован из-за юридических и технических constraints browser-канала.

---

## 2. Архитектура

### Что сделано правильно

1. **Clean separation of concerns.** Код хорошо декомпозирован: core/, storage/, adapters/, api/routes/ — каждый модуль имеет одну ответственность. Нет God-объектов.

2. **Adapter pattern.** `ExecutionAdapter` ABC — правильный контракт. Dry-run, API и browser адаптеры взаимозаменяемы. Это позволяет тестировать оркестрацию без реальных провайдеров.

3. **Canonical model registry.** Нормализация имён моделей с алиасами — решает реальную проблему drift между "Kimi K2" и "Kimi K2.5". Хорошо, что это делается один раз на входе.

4. **Append-only events.** `_append_event_safe` в оркестраторе — правильное решение. Event logging не блокирует критический путь. Тихий catch — допустимый trade-off для Phase 0.

5. **Frozen dataclasses с slots.** Правильный выбор для value objects — immutable, memory-efficient, не спутаешь с mutable state.

6. **PostgreSQL-first.** Решение пропустить SQLite и сразу целиться на PostgreSQL — обоснованное. SQLite добавил бы ненужную промежуточную миграцию.

7. **Failure taxonomy.** `FailureCode` enum с 7 типами — достаточный минимум, покрывает реальные сценарии. Не over-designed.

### Проблемы архитектуры

#### 2.1 Синхронное выполнение на async сервере (КРИТИЧНО)

FastAPI-роуты объявлены как `async def`, но `OrchestratorService.submit()` — полностью синхронный. Вызов `self._execution_router.execute()` блокирует event loop.

Для dry-run это незаметно (мгновенно). Но при реальном API-вызове (Mistral adapter использует `urllib.request.urlopen` — blocking I/O) сервер будет заблокирован на время каждого запроса. При multi-model execution с 2+ шагами — блокировка удваивается.

**Что делать:**
- Либо переводить адаптеры на async (httpx/aiohttp вместо urllib)
- Либо выносить синхронные вызовы в `asyncio.to_thread()`
- Либо запускать execution в background task (FastAPI BackgroundTasks / отдельная очередь)

Это **архитектурный долг**, который нужно закрыть до реального использования. Текущее 202 Accepted в orchestrate route создаёт ложное впечатление асинхронности, но на самом деле ответ возвращается только после полного завершения execution.

#### 2.2 Последовательное multi-model execution (ВАЖНО)

`ExecutionRouter.execute()` проходит `plan.steps` последовательно в цикле `for`. При multi-model запросе с 4 моделями — время ответа = сумма всех вызовов, а не максимум.

**Что делать:** Параллельное выполнение шагов (asyncio.gather / concurrent.futures). Это необходимо для реального multi-model кворума.

#### 2.3 Отсутствие фоновой обработки (ВАЖНО)

HTTP endpoint возвращает 202 Accepted, что по HTTP-семантике означает "запрос принят для обработки, но ещё не выполнен". Однако фактически к моменту ответа execution уже завершён. Это семантическое несоответствие.

**Два пути:**
- Честный 200 OK с результатом (если execution остаётся синхронным)
- Реальная очередь: 202 + background processing + polling через GET /tasks/{id}

#### 2.4 Нет connection pooling для PostgreSQL (СРЕДНЕ)

`PostgresTaskRepository._connect()` создаёт новое подключение на каждую операцию. При нагрузке это станет bottleneck.

**Что делать:** Connection pool (psycopg_pool или встроенный пул psycopg 3).

#### 2.5 Нет retry/circuit breaker (ожидаемо для Phase 1)

Отсутствует в roadmap Phase 4. Архитектурно место для этого есть — между router и adapter. Контракты позволяют добавить middleware-слой.

---

## 3. Качество кода

### Общая оценка: 7.5/10

**Плюсы:**
- Чистый, читаемый Python. Нет magic numbers, нет nested callbacks.
- Консистентное использование type hints (`from __future__ import annotations` везде).
- Dataclasses вместо raw dicts для domain objects.
- Нет лишних зависимостей — только FastAPI + uvicorn. Mistral adapter использует stdlib urllib.

**Минусы:**

#### 3.1 Тихое проглатывание ошибок

```python
# orchestrator.py:108-112
def _append_event_safe(self, event: TaskEventRecord) -> None:
    try:
        self._repository.append_event(event)
    except Exception:
        return
```

Bare `except Exception` без логирования. Для Phase 0 это допустимый компромисс, но в production потеря событий без следа — опасна. Нужен хотя бы `logging.warning`.

#### 3.2 Конфигурация через dataclass, а не Pydantic Settings

`Settings` — обычный dataclass с ручным парсингом `os.getenv`. В FastAPI-проектах стандарт — `pydantic-settings` (`BaseSettings`), который даёт:
- Автоматическую валидацию типов
- Поддержку .env файлов
- Документацию полей

Не критично, но при росте количества настроек станет unmanageable.

#### 3.3 Сериализация requested_models через metadata dict

`metadata["requested_models_resolved"]` — это list of dicts внутри metadata. Потом `OrchestrateResponse.from_task()` десериализует обратно. Это fragile — если формат dict изменится, сломается без compile-time safety.

Лучше: отдельное поле в `TaskRecord` или типизированный DTO для metadata.

#### 3.4 Module-level singleton

```python
# config.py:40
settings = Settings.from_env()
```

```python
# main.py:91
app = create_app()
```

Module-level side effects. `settings` создаётся при import-time, `app` — тоже. Это затрудняет тестирование и делает невозможным изменение конфигурации после импорта. В тестах это обходится через `create_app(Settings(...))`, что правильно, но production `app` на строке 91 — лишний.

#### 3.5 Нет __all__ в __init__.py

Все `__init__.py` файлы пусты. Для библиотечного кода стоит определить public API через `__all__`.

---

## 4. Тесты

### Общая оценка: 6.5/10

**16 тестов, все проходят.** Но покрытие неравномерное.

**Хорошо покрыто:**
- Model registry и alias resolution (3 теста)
- Execution planning (2 теста)
- Orchestrator service (2 теста)
- Execution router + API adapter (3 теста)
- Browser adapter (1 тест)
- HTTP API smoke (3 теста)
- Failure taxonomy (1 тест)
- Readiness (1 тест)

**Не покрыто:**
- PostgreSQL repository — ноль тестов. Даже unit-тесты с mock connection отсутствуют.
- InMemory repository — нет прямых тестов (тестируется косвенно через orchestrator).
- Schemas validation — нет тестов на Pydantic validation rules (min_length, max_length, model_validator).
- Edge cases в merge strategies — тестируется только "first_success" и "best_effort" implicit path.
- Config.from_env — нет тестов.
- Error paths в MistralApiAdapter — только missing key, нет HTTP errors, timeout, rate limit.

**Замечание по окружению:** Тесты не запускаются на Python 3.13 (ModuleNotFoundError) — пакет установлен в site-packages Python 3.12, но системный python — 3.13. В pyproject.toml нет pytest configuration для `pythonpath`. Нужно добавить:

```toml
[tool.pytest.ini_options]
pythonpath = ["src"]
```

Это позволит запускать тесты без `pip install -e .` в каждом окружении.

---

## 5. Оценка roadmap

### Phase 0-1: Clean foundation + Execution contract — ЗАВЕРШЕНЫ

Дорожная карта адекватна. Phase 0 и 1 выполнены корректно. Все ключевые deliverables на месте.

### Phase 2: Browser worker — ГЛАВНЫЙ RISK

Это самая сложная и самая хрупкая часть проекта. Нужно будет:
- Запускать headless/headed Chrome с Playwright или Selenium
- Управлять профилями браузера (cookies, sessions)
- Парсить динамический DOM Perplexity (React SPA)
- Обрабатывать popup-ы, auth flows, rate limits
- Верифицировать, что выбранная модель действительно активна

Скелет (session.py, policy.py, perplexity.py) подготовлен грамотно — правильные абстракции на месте. Но реализация будет на порядок сложнее скелета.

**Рекомендация:** Перед реализацией browser worker стоит:
1. Исследовать текущий DOM Perplexity и документировать ключевые селекторы
2. Определить fallback-стратегию при поломке селекторов
3. Решить headed vs headless (headless чаще блокируется)
4. Выбрать инструмент (Playwright > Selenium для 2026)
5. Оценить, не проще ли использовать MCP Playwright или browser-use

### Phase 3: Durable state — ГОТОВ К ВЫПОЛНЕНИЮ

PostgreSQL schema уже есть. Нужна:
- Живая валидация схемы
- Миграционная стратегия (Alembic или raw SQL с version tracking)
- Тесты с testcontainers-postgres

### Phase 4: Reliability controls — ПРАВИЛЬНЫЕ ПРИОРИТЕТЫ

Account pool, fallback, circuit breakers — это Phase 4, и это правильно. Не стоит делать раньше.

### Phase 5: Operations surface — OK

Метрики, inspection, runbook. Зависит от реальной эксплуатации.

### Parallel track: API adapters — НЕДООЦЕНЁН

В текущем roadmap API adapters — "parallel track". Но с учётом рисков browser канала, это может стать **основным каналом**. Стоит повысить приоритет:
- Добавить OpenAI-compatible adapter (покрывает OpenAI, Together, Groq, Fireworks и десятки других)
- Добавить Anthropic adapter (прямой API к Claude)
- Один generic OpenAI-compatible adapter закроет 80% потребностей

---

## 6. Конкретные замечания и рекомендации

### 6.1 Немедленно (блокеры качества)

| # | Проблема | Файл | Действие |
|---|----------|------|----------|
| 1 | pytest не находит пакет на Python 3.13 | pyproject.toml | Добавить `[tool.pytest.ini_options] pythonpath = ["src"]` |
| 2 | Тихий `except Exception` без логирования | orchestrator.py:108 | Добавить `logging.warning(...)` |
| 3 | `app = create_app()` на module level | main.py:91 | Убрать, использовать только `uvicorn gracekelly.main:create_app --factory` |
| 4 | Нет `.gitignore` для `__pycache__` в src/ | .gitignore | Добавить `__pycache__/` и `*.pyc` (возможно уже есть, проверить) |

### 6.2 Краткосрочно (до начала Phase 2)

| # | Рекомендация | Обоснование |
|---|-------------|-------------|
| 1 | Перевести execution на async (httpx) | Блокирующий urllib на async сервере — architectural debt |
| 2 | Параллельное execution для multi-model | Без этого multi-model бессмысленно по latency |
| 3 | Добавить тесты для Pydantic schemas | Валидация на входе — единственная линия защиты |
| 4 | Добавить тесты для PostgreSQL repository | Хотя бы unit с mock connection |
| 5 | Добавить OpenAI-compatible API adapter | Один адаптер покрывает десятки провайдеров |
| 6 | Определить стратегию миграций | Alembic или version-tracked raw SQL |

### 6.3 Среднесрочно (Phase 2-3)

| # | Рекомендация | Обоснование |
|---|-------------|-------------|
| 1 | Playwright для browser automation | Лучшая поддержка, async API, auto-wait |
| 2 | Background task queue | Отделить HTTP-ответ от execution lifecycle |
| 3 | Structured logging (structlog) | JSON-логи для оркестратора обязательны |
| 4 | Connection pooling для PostgreSQL | psycopg_pool для production |
| 5 | Health check с реальным DB ping | Текущий healthcheck для postgres — SELECT 1 (верно), но нет timeout |
| 6 | Rate limiting на API endpoints | Даже для personal use — защита от случайных петель |

---

## 7. Безопасность

| # | Находка | Серьёзность | Рекомендация |
|---|---------|-------------|-------------|
| 1 | API key в переменной окружения | OK | Стандартный подход. Не хранить в коде или git. .env.example корректен. |
| 2 | Нет валидации prompt content | Низкая | Для personal use приемлемо. Для multi-user — нужна sanitization. |
| 3 | CORS не настроен | Низкая | Если будет фронтенд — добавить CORSMiddleware с whitelist. |
| 4 | Нет auth на API endpoints | Средняя | Для localhost — OK. При любом сетевом доступе — нужен API key / JWT. |
| 5 | SELECT * в PostgreSQL GET | Низкая | Лучше явно перечислять columns, но для Phase 0 допустимо. |
| 6 | task_id = UUID4 | OK | Непредсказуемый, достаточный для task identification. |

---

## 8. Зависимости

| Пакет | Версия | Оценка |
|-------|--------|--------|
| FastAPI | >=0.115,<1.0 | Актуально. FastAPI 1.0 ещё не вышел. Upper bound правильный. |
| Uvicorn | >=0.30,<1.0 | OK. |
| psycopg | optional | Правильно как optional. В dependencies не указан — нужно добавить в optional-deps. |
| pytest | >=8.0,<9.0 | OK для dev. |

**Отсутствуют в зависимостях:**
- `psycopg` — используется в postgres.py, но не в `[project.optional-dependencies]`
- `httpx` — понадобится при переходе на async HTTP
- `playwright` — понадобится для Phase 2

**Рекомендация:** Добавить optional dependency group:

```toml
[project.optional-dependencies]
postgres = ["psycopg[binary]>=3.1,<4.0"]
browser = ["playwright>=1.40"]
dev = ["pytest>=8.0,<9.0", "httpx>=0.27"]
```

---

## 9. Общий вердикт

### Что хорошо
- Чистый старт без legacy-долга. Сознательное решение не тащить за собой broken SQLite и mixed concerns.
- Грамотная декомпозиция. Каждый модуль имеет одну задачу. Контракты explicit.
- Правильные architectural decisions задокументированы. Issue log в implementation-plan.md — отличная практика.
- Работающий end-to-end path. Dry-run и API path функциональны.
- Тесты есть и проходят. 16/16 — хороший baseline.

### Что требует внимания
- **Async/sync mismatch** — главный технический долг. Нужно закрыть до реального использования.
- **Browser канал** — главный бизнес-риск. Хрупкий и юридически сомнительный. Нужен Plan B (расширение API adapters).
- **Тестовое покрытие** — неравномерное. PostgreSQL и schema validation не покрыты.
- **Missing optional deps в pyproject.toml** — psycopg не объявлен.

### Итоговая оценка

| Аспект | Оценка | Комментарий |
|--------|--------|-------------|
| Архитектура | 8/10 | Чистая, расширяемая. Async debt портит. |
| Качество кода | 7.5/10 | Хороший Python, мелкие недочёты |
| Тесты | 6.5/10 | Есть, но gaps заметны |
| Документация | 8/10 | Architecture, plan, roadmap — всё на месте |
| Актуальность идеи | 7/10 | Нишевая ценность, risk browser канала |
| Roadmap | 7.5/10 | Правильные приоритеты, API track недооценён |
| Безопасность | 7/10 | Для personal use OK, для multi-user — нужна работа |
| **Общая** | **7.5/10** | Сильный foundation, нужно закрыть async debt и расширить API track |
