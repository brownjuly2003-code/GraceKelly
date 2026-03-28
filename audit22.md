# Аудит проекта GraceKelly — 2026-03-28

## Executive Summary

**GraceKelly** — production-ready оркестратор для multi-model LLM execution с двумя бэкендами исполнения (browser через Perplexity и API через Mistral/OpenAI/Anthropic). Проект демонстрирует зрелую архитектуру с чистым разделением слоёв, строгой типизацией, исчерпывающими тестами и несколькими уровнями защиты.

**Статус проекта:** Early production (Phase 13 in progress)
**Последний коммит:** d1781e4 (2026-03-28) — "Add tests: metrics payload request_metrics branches"
**Тесты:** 2091 passed, 6 skipped (98.7% pass rate)
**Оценка:** 7.8/10

---

## 1. Структура проекта

```
/d/GraceKelly/
├── src/gracekelly/              # 12,030 LOC Python source
│   ├── main.py                  # FastAPI app factory & wiring
│   ├── config.py                # Settings management (70+ env vars)
│   ├── schemas.py               # Pydantic request/response models
│   ├── app_state.py             # Request-scoped state
│   ├── middleware.py            # Auth, rate limiting, metrics
│   ├── logging_utils.py         # Structured logging helpers
│   ├── api/routes/              # 12 route modules (orchestrate, consensus, debate, etc.)
│   ├── core/                    # 76 modules (contracts, router, consensus, clustering, etc.)
│   ├── adapters/                # Execution backends
│   │   ├── api/                 # Mistral, OpenAI-compatible, Anthropic adapters
│   │   └── browser/             # Perplexity browser automation (Playwright, scripted)
│   ├── storage/                 # Task persistence
│   │   ├── base.py              # Abstract TaskRepository
│   │   ├── memory.py            # In-memory implementation
│   │   ├── postgres.py          # PostgreSQL implementation
│   │   └── schema.py            # DDL, migrations, schema discovery
│   └── tools/                   # CLI utilities (profile creation, DB export/import)
├── tests/                       # 24,415 LOC across 121 test files
├── docs/                        # Architecture and runbook
│   ├── architecture.md
│   ├── phased-roadmap.md        # 13 delivery phases
│   ├── operator-runbook.md      # Operational procedures
│   └── perplexity-dom-recon.md  # Browser UI reconnaissance
├── pyproject.toml               # Project config + 7 CLI entry points
├── Dockerfile                   # Python 3.12-slim, health check
├── docker-compose.yml           # 2 service configs (memory + postgres)
├── .github/workflows/ci.yml     # GitHub Actions (Python 3.11/3.12, mypy --strict, ruff)
└── .gitignore
```

### Ключевые метрики
- **Python-модулей:** 98 (src/) + 121 тестовых файлов
- **LOC:** 12,030 (src) + 24,415 (tests) = 36,445 total
- **Ratio тестов к коду:** 2.03:1 (отлично)
- **API-эндпоинтов:** 15
- **Storage бэкендов:** 2 (memory + PostgreSQL)
- **Адаптеров:** 6 (dry-run, Mistral API, OpenAI-compatible, Anthropic API, Playwright browser, scripted browser)

---

## 2. Стек технологий

### Core Dependencies
| Компонент | Версия | Назначение |
|-----------|--------|------------|
| FastAPI | >=0.115,<1.0 | Web framework |
| Uvicorn | >=0.30,<1.0 | ASGI server |
| Pydantic | (via FastAPI) | Request validation |
| Python | 3.11–3.12 | Runtime |

### Optional Dependencies
| Компонент | Версия | Назначение |
|-----------|--------|------------|
| psycopg | >=3.2,<4.0 | PostgreSQL adapter |
| psycopg_pool | >=3.2,<4.0 | Connection pooling |
| Playwright | >=1.56,<2.0 | Browser automation |

### Dev/Test Dependencies
| Компонент | Версия | Назначение |
|-----------|--------|------------|
| pytest | >=8.0,<9.0 | Test runner |
| ruff | >=0.4 | Linting/formatting |
| mypy | >=1.10 | Static type checking (strict) |

### Особенности языка
- Python 3.11+: `from __future__ import annotations`, match statements
- Strict mypy: 0 ошибок на всех 98 модулях
- `@dataclass(frozen=True, slots=True)` для иммутабельных контрактов
- `StrEnum` для всех перечислений (type-safe + JSON-serializable)

---

## 3. Конфигурация (50+ env vars)

### Основные категории

**General:** `GRACEKELLY_ENV`, `_HOST`, `_PORT` (default 127.0.0.1:8011), `_LOG_LEVEL`

**Security:** `GRACEKELLY_API_KEY` (опциональный — без него API полностью открыт с WARNING), `_RATE_LIMIT_PER_MINUTE`

**Storage:** `_STORAGE_BACKEND` (memory | postgres), `_POSTGRES_DSN`, `_POSTGRES_POOL_*`

**API Adapters:** `_{PROVIDER}_API_KEY`, `_BASE_URL`, `_TIMEOUT_SECONDS`, `_MAX_RETRIES`, `_RETRY_BACKOFF_SECONDS` (для Mistral, OpenAI, Anthropic)

**Browser:** `_BROWSER_ENABLED`, `_BROWSER_AUTOMATION_BACKEND` (null | playwright | scripted), `_BROWSER_PROFILE_DIR`, `_BROWSER_CIRCUIT_BREAKER_*`

**Execution:** `_EXECUTION_PROFILE` (dry-run, default)

### Загрузка конфигурации
- `config.py:Settings.from_env()` — dataclass factory
- Кастомные хелперы `_env_int()`, `_env_float()` с fallback'ами
- Pydantic валидация + custom min_length/max_length bounds
- `.env.example` с полным набором параметров и дефолтов

---

## 4. Архитектура и дизайн

### Высокоуровневая схема

```
FastAPI App
    ↓
API Routes (15 endpoints)
    ↓
Middleware (auth, rate limit, metrics)
    ↓
OrchestratorService
    ├→ ExecutionRouter
    │   ├→ ExecutionPlan (from request + models registry)
    │   └→ ExecutionBatchResult (parallel/sequential execution)
    ├→ TaskRepository (memory | postgres)
    └→ Adapter Registry
        ├→ DryRunAdapter
        ├→ API Adapters (Mistral, OpenAI, Anthropic)
        └→ BrowserAdapter
            ├→ PerplexityBrowserAdapter
            └→ BrowserAutomationPort
                ├→ PlaywrightBrowserAutomation
                ├→ ScriptedBrowserAutomation
                └→ NullBrowserAutomation
```

### Ключевые принципы

1. **Clean Layering** — API routes (HTTP concerns), core (domain), adapters (backends), storage (persistence)
2. **Immutable Contracts** — `@dataclass(frozen=True, slots=True)` для `ExecutionPlan`, `ExecutionStep`, `ExecutionResult` и др.
3. **Pluggable Storage** — абстрактный `TaskRepository` с двумя реализациями
4. **Dependency Injection** — все компоненты связываются в `main.py:create_app()`
5. **Type-Safe Enums** — `StrEnum` для всех статусов/режимов/кодов
6. **Port & Adapter Pattern** — `BrowserAutomationPort` ABC с 3 реализациями + policy-объекты

### Поток выполнения

1. Request → `POST /api/v1/orchestrate`
2. Pydantic validation + custom model/quorum rules
3. `build_execution_plan()` → маппинг моделей на адаптеры + steps
4. `OrchestratorService.submit()` → persist task + events
5. `ExecutionRouter.execute()`:
   - Dry-run: sequential via `DryRunAdapter`
   - Live: parallel via `ThreadPoolExecutor` + quorum-based early termination
6. `_aggregate()` → `MergeStrategy` (FIRST_SUCCESS | CONCAT)
7. `TaskRepository.save_task_with_steps()` → persist
8. `OrchestrateResponse` → task ID + status

---

## 5. API-эндпоинты (15 маршрутов)

### Core
| # | Метод | Path | Назначение |
|---|-------|------|------------|
| 1 | GET | `/health` | Health check (без авторизации) |
| 2 | GET | `/api/v1/readiness` | Readiness с детализацией компонентов |
| 3 | GET | `/metrics` | Prometheus-compatible метрики |

### Orchestration
| # | Метод | Path | Назначение |
|---|-------|------|------------|
| 4 | POST | `/api/v1/orchestrate` | Multi-model execution |
| 5 | GET | `/api/v1/tasks` | Список задач с фильтрами |
| 6 | GET | `/api/v1/tasks/{task_id}` | Полный контекст задачи |
| 7 | GET | `/api/v1/models` | Каталог моделей |

### Multi-Model Patterns
| # | Метод | Path | Назначение |
|---|-------|------|------------|
| 8 | POST | `/api/v1/consensus` | Majority voting + confidence |
| 9 | POST | `/api/v1/smart` | Auto-profile resolution |
| 10 | POST | `/api/v1/smart/v2` | Consensus V2: HAC clustering, cross-pollination, peer review |
| 11 | POST | `/api/v1/batch` | Parallel multi-prompt |
| 12 | POST | `/api/v1/pipeline` | Sequential task graph |
| 13 | POST | `/api/v1/debate` | Devil's Advocate |
| 14 | POST | `/api/v1/compare` | Multi-model comparison с judge |
| 15 | GET | `/api/v1/health/detailed` | Component-level health |

### HTTP-коды
- 202 Accepted, 400 Bad Request, 401 Unauthorized, 404 Not Found
- 429 Too Many Requests, 501 Not Implemented, 503 Service Unavailable

---

## 6. Схема БД (PostgreSQL)

```sql
gk_tasks (task_id PK)
  ├ status, execution_mode, dry_run, failure_code
  ├ prompt, reasoning, output_text
  ├ model_count, quorum, merge_strategy, adapter_hint
  ├ accepted_at, completed_at, duration_ms
  ├ metadata (jsonb)
  └ retry_of_task_id (FK)

gk_task_steps (task_id FK, step_index PK)
  ├ model_id, model_display_name
  ├ backend, provider
  ├ status, failure_code, failure_message
  ├ output_text, duration_ms

gk_task_events (event_id PK, task_id FK)
  ├ sequence_no, event_type
  ├ created_at, payload (jsonb)

gk_schema_migrations (name PK)
  ├ applied_at, status
```

- Connection pooling через `psycopg_pool.ConnectionPool`
- Health check, schema discovery, export/import с gzip + SHA256
- Все запросы — parameterized (`%s` placeholders, без SQL injection)

---

## 7. Тестирование

### Покрытие
- **Тестов:** 2091 passed, 6 skipped
- **Файлов:** 121
- **Ratio:** 2.03:1 (отлично)
- **Паттерн:** Unit + integration + edge-case

### Организация
```
tests/
├── test_api_adapter_*.py         (адаптеры Mistral, OpenAI, Anthropic)
├── test_app_startup.py           (фабрика приложения, wiring)
├── test_browser_*.py             (browser adapter, policies, selectors)
├── test_circuit_breaker*.py      (circuit breaker state machine)
├── test_config*.py               (парсинг настроек, валидация)
├── test_consensus*.py            (majority voting, V2 consensus)
├── test_contracts*.py            (data models, enums)
├── test_*_route.py               (все 15 API routes)
├── test_middleware*.py           (auth, rate limiting, metrics)
├── test_postgres*.py             (storage layer, DB operations)
├── test_orchestrator*.py         (submission, execution)
├── test_*_tool.py                (CLI utilities)
└── test_playwright_live.py       (optional live smoke test)
```

### Качество
- Extensive mocking (`Mock`, `MagicMock`, `patch()`)
- Shared `app` fixture с in-memory storage
- Edge cases: timeout, network errors, invalid models, quorum violations
- `@pytest.mark.parametrize` для вариаций
- Все импорты — реальные модули (без `type: ignore` в тестах)

---

## 8. Анализ безопасности

### Сильные стороны

- **API Key Authentication:** `hmac.compare_digest()` для timing-safe сравнения, Bearer token + X-API-Key header
- **Rate Limiting:** Per-client-IP sliding window (60s), periodic `_purge_stale()` каждые 500 запросов
- **Input Validation:** Pydantic schemas с min/max_length, regex. Prompt max: 40,000 chars; Models max: 8; Quorum: 1–8
- **Path Traversal Protection:** Browser profile dir блокирует `..` и `~`
- **Error Sanitization:** API не раскрывает stack traces, whitelist для validation errors
- **SQL Injection Prevention:** Все SQL — parameterized (`%s`)
- **Secrets Management:** `.env` в `.gitignore`, credentials через env vars, нет hardcoded ключей
- **Type Safety:** mypy strict — 0 ошибок, все адаптеры реализуют ABC

### Слабости

| Severity | Проблема | Рекомендация |
|----------|----------|--------------|
| MEDIUM | **Fail-Open Auth:** без `GRACEKELLY_API_KEY` API полностью открыт | Для production — обязать наличие ключа |
| MEDIUM | **CORS не настроен:** нет `CORSMiddleware` | Документировать решение, добавить при необходимости |
| LOW | **Health Endpoint Info Leakage:** `/health` раскрывает version, saturation, model status | Ограничить детали до `/api/v1/readiness` |
| LOW | **No Request Signing:** bearer token без HMAC, уязвим к replay | Для чувствительных деплоев — HMAC-SHA256 |
| LOW | **No TLS Config:** HTTP only, TLS ожидается на load balancer | Документировать требование TLS |

---

## 9. Анализ производительности

### Сильные стороны
- In-memory storage (default) — быстро для dev/test
- Connection pooling для PostgreSQL
- Parallel execution через `ThreadPoolExecutor`
- Quorum-based early termination
- Circuit breaker для browser adapter

### Проблемы

| Severity | Проблема | Влияние | Рекомендация |
|----------|----------|---------|--------------|
| HIGH | **Sequential по умолчанию** (dry_run=true) | 3–10x latency для multi-model | Сделать parallel по умолчанию |
| HIGH | **Синхронные адаптеры** (urllib, sync psycopg, sync playwright) | Thread pool exhaustion | Миграция на async (httpx, async-playwright) |
| MEDIUM | **Thread Pool Exhaustion** | `/health` блокируется при нагрузке | Отдельный executor для health/metrics |
| MEDIUM | **N+1 queries** в `GET /api/v1/tasks?limit=100` | 200+ запросов для PostgreSQL | Оптимизировать через JOINs |
| LOW | **Нет пагинации events** | Большие ответы при 10K+ событиях | Добавить limit/offset |

---

## 10. Надёжность и устойчивость

### Сильные стороны
- **Circuit Breaker:** Opens после N consecutive failures, half-open recovery, configurable cooldown
- **Graceful Degradation:** Adapter unavailable → PROVIDER_UNAVAILABLE, storage offline → 503
- **Task Event Persistence:** Event sequence numbers, отказ записи не ломает execution
- **Retry Support:** `retry_of_task_id` linkage, `POST /api/v1/tasks/{id}/retry`
- **Quorum-Based Execution:** Настраиваемый quorum + merge strategy

### Проблемы

| Severity | Проблема | Рекомендация |
|----------|----------|--------------|
| HIGH | **Нет graceful shutdown:** in-flight requests убиваются при deploy | Drain period 60s |
| MEDIUM | **Нет request timeout** на orchestrate endpoint | Добавить timeout, возвращать 504 |
| MEDIUM | **Потеря events** при сбое storage (логируется, не retry) | Буфер failed events в memory |
| LOW | **Нет deadletter queue** для failed tasks | Опциональный background retry job |

---

## 11. Observability

### Реализовано
- **Structured Logging:** `log_message()`, key=value формат, trace_id propagation
- **Metrics:** `GET /metrics` — Prometheus-compatible gauges (task counts, saturation, circuit breaker)
- **Readiness:** `GET /api/v1/readiness` + `GET /api/v1/health/detailed`
- **Task Inspection:** Полный контекст задачи со steps, events, execution context

### Пробелы

| Severity | Проблема | Рекомендация |
|----------|----------|--------------|
| MEDIUM | Нет histogram latency / counter по status codes | `prometheus_client` library |
| MEDIUM | Нет error aggregation (только логи) | Sentry или аналог |
| LOW | Нет distributed tracing | OpenTelemetry при расширении |

---

## 12. Качество кода

### Метрики
- **LOC (src):** 12,030
- **LOC (tests):** 24,415
- **Ratio:** 2.03:1
- **Cyclomatic complexity:** Низкая (1–10 branches)
- **Type coverage:** 100% (mypy strict, 0 errors)

### Стандарты
- Ruff: 120-char line, E/F/W/I/UP rules
- Consistent imports, без unused vars
- Descriptive naming: `_execute_sequential`, `_aggregate`, `_purge_stale`
- Private methods с `_`, UPPERCASE constants

### Замечания
| Severity | Проблема |
|----------|----------|
| MEDIUM | 8 `# type: ignore` комментариев (в основном Playwright stubs, `json.loads` → `Any`) |
| LOW | `getattr()` в middleware для optional state attrs — defensive programming |
| LOW | Длинные функции: `submit_snapshot()` ~80 LOC, `_execute_parallel()` ~50 LOC |

---

## 13. Зависимости

### Core (нет известных CVE)
| Пакет | Версия | Статус |
|-------|--------|--------|
| FastAPI | 0.115+ | Actively maintained |
| Uvicorn | 0.30+ | Actively maintained |
| Pydantic | (via FastAPI) | Actively maintained |

### Optional (нет известных CVE)
| Пакет | Версия | Статус |
|-------|--------|--------|
| psycopg | 3.2+ | Actively maintained |
| psycopg_pool | 3.2+ | Part of psycopg ecosystem |
| Playwright | 1.56+ | Actively maintained |

### Dev (не в production)
| Пакет | Версия | Назначение |
|-------|--------|------------|
| pytest | 8.0+ | Testing |
| ruff | 0.4+ | Linting |
| mypy | 1.10+ | Type checking |

**Итого:** Нет устаревших или уязвимых зависимостей.

---

## 14. Деплой и операции

### Docker
- **Dockerfile:** `python:3.12-slim`, HEALTHCHECK каждые 30s, `uvicorn --factory`
- **Docker Compose:** Два сервиса (memory + postgres), PostgreSQL 16, volume persistence
- **Пробел:** Нет resource limits, нет network policies

### CI/CD (GitHub Actions)
- Matrix: Python 3.11 + 3.12
- Services: PostgreSQL 16 для integration tests
- Steps: deps install → ruff → mypy strict → pytest → import check
- **Пробелы:** Нет SAST, нет dependency scanning, нет coverage reporting

### Operator Runbook
- `docs/operator-runbook.md` покрывает: health check, browser profiles, PostgreSQL troubleshooting, circuit breaker reset, task retry, log debugging

---

## 15. Критические находки (по приоритету)

### CRITICAL — нет

### HIGH (исправить до production)

1. **Sequential execution по умолчанию** (dry_run=true → блокирует parallel)
   - Impact: 3–10x latency
   - Fix: auto-select based on mode/quorum

2. **Синхронные адаптеры** (urllib → thread pool exhaustion)
   - Impact: блокировка под нагрузкой
   - Fix: миграция на httpx + async-playwright

3. **Нет graceful shutdown**
   - Impact: long-running requests убиваются при deploy
   - Fix: shutdown grace period + request draining

### MEDIUM (исправить скоро)

4. N+1 queries при листинге задач (PostgreSQL)
5. Fail-open auth/rate-limiting (нет enforcement в dev mode)
6. Нет request timeout на orchestrate endpoint
7. Нет пагинации для task events
8. Потеря task events при сбое storage

### LOW (улучшения)

9. Health endpoint раскрывает информацию
10. Нет CORS configuration
11. Нет distributed tracing
12. Нет error tracking integration

---

## 16. OWASP Top 10 (2021)

| # | Категория | Статус | Комментарий |
|---|-----------|--------|-------------|
| A01 | Broken Access Control | ✅ | API key + rate limiting |
| A02 | Cryptographic Failures | ✅ | Timing-safe comparison |
| A03 | Injection | ✅ | Parameterized SQL, no eval() |
| A04 | Insecure Design | ⚠️ | Circuit breaker есть, но нет mandatory hardening |
| A05 | Security Misconfiguration | ⚠️ | Fail-open auth в dev, нет SAST |
| A06 | Vulnerable Components | ✅ | Нет CVE, deps актуальны |
| A07 | Auth Failures | ⚠️ | Bearer only, нет HMAC signing |
| A08 | Data Integrity | ✅ | Immutable contracts, validation |
| A09 | Logging Gaps | ✅ | Structured logging, но нет aggregation |
| A10 | SSRF | ⚠️ | Browser adapter → Perplexity; мониторить redirects |

---

## 17. Рекомендации (roadmap)

### Phase 1: Production Readiness (Weeks 1–2)
1. Auto-detect parallel execution (не sequential по умолчанию)
2. Graceful shutdown: drain in-flight requests (60s)
3. Enforce API key + rate limiting в production mode
4. Request timeout на orchestrate endpoint (120s default)
5. Event buffering для storage failures

### Phase 2: Performance (Weeks 3–4)
1. Async adapters (httpx для API, async-playwright для browser)
2. Optimize task listing → JOINs вместо N+1
3. Pagination для events

### Phase 3: Observability (Weeks 5–6)
1. Prometheus request metrics (histogram, counter)
2. Error tracking (Sentry)
3. OpenTelemetry distributed tracing
4. Ограничить `/health` details

### Phase 4: Security Hardening (Week 7+)
1. SAST в CI (bandit, semgrep)
2. Dependency scanning (pip-audit, safety)
3. HMAC request signing (опционально)
4. PII data handling policy
5. CORS policy

---

## 18. Итоговая оценка

| Категория | Оценка |
|-----------|--------|
| Архитектура | 9/10 |
| Безопасность | 7.5/10 |
| Производительность | 6.5/10 |
| Надёжность | 7.5/10 |
| Тестирование | 9/10 |
| Документация | 8.5/10 |
| **Общая оценка** | **7.8/10** |

### Сильные стороны
1. Чистая архитектура — layering, нет circular dependencies
2. Immutable data models — целый класс багов предотвращён
3. Type safety — mypy strict, 0 ошибок
4. Test coverage — 2091 тестов, 2.03:1 ratio
5. Pluggable storage — легко менять бэкенды
6. Structured logging — trace propagation
7. Port & Adapter pattern — browser testable без browser
8. Documentation — runbook, architecture, roadmap

### Что улучшить
1. Производительность — синхронные адаптеры, sequential по умолчанию
2. Надёжность — нет graceful shutdown, нет event buffering
3. Безопасность — fail-open auth, нет request signing
4. Observability — ограниченные метрики, нет error aggregation
5. Тестирование — нет load/stress тестов
