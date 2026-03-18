# GraceKelly — полный аудит проекта

Дата: 2026-03-19

---

## 1. Код и архитектура

**Результат: 0 critical, 6 warnings, 25 info**

Архитектурные границы из `docs/architecture.md` соблюдаются строго: адаптеры за границами, HTTP-маршруты без доменной логики, persistence заменяема, модели канонизируются на входе.

### Warnings

| Файл | Описание | Рекомендация |
|------|----------|-------------|
| `adapters/api/mistral.py` vs `openai_compat.py` | 99% дублирование кода: execute(), _post_json(), _extract_output_text(), _failure() | Вынести общую логику в BaseApiAdapter |
| `config.py:41` | `int(os.getenv(...))` без обработки ValueError — упадёт с непарсируемой переменной | Обернуть в try/except или helper-функцию |
| `core/orchestrator.py:193` | `_build_events()` — 34+ строк с вложенной функцией и множественными условиями | Разбить на `_build_step_events()` и `_build_terminal_event()` |
| `api/routes/health.py:108` | `_build_metrics_payload()` — 60+ строк повторяющихся `_emit_one_hot()` / `_emit_gauge()` | Рассмотреть MetricsBuilder |
| `core/readiness.py:71` | Параметры `execution_router: object` и `adapter: object` вместо типизированного Protocol | Ввести `Protocol[SupportsHealthcheck]` |
| `core/orchestrator.py:354` | `json.dumps(result.details, default=str)` может скрывать проблемы с типами | Добавить явную валидацию сериализуемости details |

### Положительные находки

- Все функции и методы имеют полные type hints (modern Python 3.10+ syntax)
- Нет bare except, все исключения специфичны
- FailureCode enum полностью покрывает таксономию ошибок
- Потокобезопасность: Lock в ModelConcurrencyGate, RLock в InMemoryTaskRepository
- Dataclasses с `slots=True` для оптимизации
- `zip(..., strict=True)` для защиты от рассинхронизации длин
- Нет мёртвого кода, неиспользуемых импортов

---

## 2. Покрытие тестами

**Результат: 7.6/10 — 180 passed, 4 skipped**

### Хорошо покрыто

| Модуль | Оценка | Комментарий |
|--------|--------|-------------|
| `core/orchestrator.py` | good | Основной flow, ошибки, events, quorum short-circuit |
| `core/planning.py` | good | Build plan, edge cases, конфликты адаптеров |
| `core/router.py` | good | Routing, concurrency, cancel-on-quorum |
| `core/circuit_breaker.py` | excellent | Все переходы состояний, cooldown, half-open |
| `storage/memory.py` | excellent | Фильтрация, ordering, dedup, snapshot replacement |
| `adapters/browser/perplexity.py` | good | Auth failures, model mismatch, cancellation (14 тестов) |

### Критические пробелы

| Модуль | Проблема |
|--------|----------|
| `core/concurrency.py` | Нет тестов вообще — thread-safety ModelConcurrencyGate не проверена |
| `core/execution_profile.py` | Нет тестов — profile resolution не проверен |
| `schemas.py` | Pydantic-валидация (границы полей, невалидный metadata) не тестируется |
| `storage/postgres.py` | CRUD только в live-тестах, нет unit-тестов с моками |
| `api/routes/models.py` | Endpoint `/api/v1/models` не тестируется |
| `adapters/browser/policy.py` | PopupPolicy, AuthRecoveryPolicy, SubmitPolicy — ни одного теста |
| `adapters/browser/selectors.py` | Валидность селекторов не проверяется |
| `logging_utils.py` | Форматирование логов не тестируется |

### Отсутствующие edge cases

- Очень длинные промпты (near 40KB max)
- Unicode/emoji в промптах
- Concurrent writes в один task (race condition в storage)
- Network timeout в API-адаптерах (не симулируется)
- Malformed responses от API (пустое тело, не-JSON, missing fields)
- Browser crash recovery

---

## 3. Безопасность

**Результат: 1 critical, 1 high, 5 medium**

### CRITICAL

| Проблема | Где | Описание |
|----------|-----|----------|
| Нет аутентификации на API | `api/routes/*.py` | Все endpoints открыты: `/api/v1/orchestrate`, `/tasks`, `/models`, `/health`, `/metrics`. Кто угодно с сетевым доступом может слать промпты (расход API-квот), читать историю задач, запускать browser-автоматизацию |

**Рекомендация:** Bearer token middleware или API key в headers. Для dev — достаточно localhost-only binding (уже по умолчанию `127.0.0.1`).

### HIGH

| Проблема | Где | Описание |
|----------|-----|----------|
| Path traversal в profile_dir | `playwright_driver.py:82` | `profile_dir` из конфига передаётся в Playwright без валидации. `profile_dir="../../../../etc"` не отсекается |

**Рекомендация:** `Path(profile_dir).resolve()` + проверка `is_relative_to(allowed_parent)`.

### MEDIUM

| Проблема | Где | Описание |
|----------|-----|----------|
| Утечка деталей в ошибках | `orchestrate.py:107,118` | `str(exc)` возвращается клиенту — имена библиотек, структура моделей |
| Storage errors leak DB info | `orchestrate.py:21` | StorageUnavailableError может содержать DSN |
| Нет rate limiting | `api/routes/*.py` | Нет защиты от flood-запросов |
| Metrics без авторизации | `health.py:321` | `/metrics` отдаёт внутреннее состояние (лимиты, saturation) |
| Browser profile cookies | `perplexity-profile/` | Cookies хранятся незашифрованно на диске |

### Положительные находки

- SQL-инъекций нет — все запросы параметризованы (`%s` placeholders)
- Секреты не захардкожены — только через `os.getenv()`
- JavaScript в browser automation — только hardcoded строки, нет injection vectors
- HTTPS enforced для всех внешних API
- Нет опасных функций (`eval`, `exec`, `pickle`, unsafe `yaml`)
- Thread-safe locking в критических путях

---

## 4. Документация

**Результат: 9.9/10 — практически полное соответствие**

### Всё совпадает

- 7 API endpoints — все реализованы и работают как описано
- 6 console scripts — все существуют с правильными entry points
- Storage schema (TaskRecord, TaskStepRecord, TaskEventRecord) — все поля на месте
- Фазы roadmap — статусы корректны
- Конфигурация — все env vars и defaults совпадают
- Operator runbook — все recovery-команды и метрики актуальны

### Единственный gap

`implementation-plan.md` ссылается на `audit2.md`, `audit2-recommendations.md` и `gate4-audit-brief.md` — этих файлов нет в репозитории. Либо хранятся внешне, либо нужно уточнить.

---

## Приоритеты исправлений

### Высокий приоритет

1. Аутентификация на API endpoints (если планируется доступ не только с localhost)
2. Тесты для `concurrency.py` — thread-safety критична
3. Валидация `profile_dir` на path traversal
4. Санитизация ошибок в API-ответах (не возвращать `str(exc)`)

### Средний приоритет

5. Вынести общий код Mistral/OpenAI адаптеров в BaseApiAdapter
6. Тесты для `schemas.py` Pydantic-валидации
7. Тесты для `/api/v1/models` endpoint
8. Rate limiting middleware
9. Тесты для browser policies

### Низкий приоритет

10. Упростить `_build_events()` и `_build_metrics_payload()`
11. Protocol вместо `object` в readiness.py
12. Тесты для `logging_utils.py`
13. Документировать расположение audit-артефактов
