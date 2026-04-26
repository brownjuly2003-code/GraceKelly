# Стратегический аудит GraceKelly

**Дата:** 2026-04-26
**Версия проекта:** v0.1.0, HEAD ceeb27d
**Контекст:** локально используемый персональный инструмент (single-user, localhost)
**Аудитор:** Claude Opus 4.7, BCG-style depth
**Базис:** 105 src файлов / 15.5k LOC, 159 test файлов / 36k LOC, 382 коммита, 11 endpoints

---

## TL;DR

Engineering quality — 9/10. Strategic fit для personal product — 5/10.

Проект построен с дисциплиной enterprise SDK (strict typing, adapter ABC, circuit breaker, Prometheus, PostgreSQL, 2.3× test ratio), но используется одним человеком на localhost. Это **over-engineering на ~40% поверхности** — не дефект кода, а дефект scope. Поверхность создаёт постоянную поддержку, которой никто не платит.

**Три критических вывода:**

1. **Single point of failure** — вся ценность висит на 1,122 строках Playwright-обёртки против Perplexity DOM. Любой UI редизайн или ужесточение Cloudflare = всё ломается. Альтернативный путь (API-only) формально есть, но Perplexity Pro ($20/мес unlimited) против OpenAI+Anthropic ($50–150/мес pay-per-use) — это не fallback, это другой продукт.

2. **Velocity ≠ ROI** — 138 коммитов за 7 дней (≈20/день). При 30-минутном среднем чанке это 70+ часов работы за неделю на инфраструктуру для одного пользователя. Opportunity cost vs JobPilot / Pages_new / RAG — не очевиден.

3. **Решение нужно сейчас, не через год** — поверхность растёт линейно, maintenance долг — экспоненциально. Каждый дополнительный orchestration pattern (smart v2, batch, pipeline) увеличивает площадь, не использование.

**Рекомендация:** Option B — Simplify (см. §7). Срез ~40% LOC, fokus на 3 happy-path endpoints, заморозить storage/observability на dev-варианте. Maintenance падает с ~10 hr/неделя до ~3 hr/неделя при сохранении 95% реального value.

---

## 1. Что это и зачем (продуктовый контекст)

GraceKelly — локальный multi-LLM оркестратор, маршрутизирующий запросы либо через Perplexity Pro (browser automation, основной путь), либо через прямые API (OpenAI/Anthropic, fallback). Поверх голого «выбери модель и спроси» добавлены паттерны structured disagreement: compare, debate, consensus, smart routing, batch.

**Реальная ценность для пользователя:**

| Что даёт | Что заменяет |
|---|---|
| Multi-model output без N подписок | OpenAI Plus + Claude Pro + Perplexity Pro по отдельности |
| Compare/debate/consensus поверх UI | Ручной copy-paste между чатами |
| Локальный аудит-trail запросов | Скриншоты + блокнот |
| Программный доступ из RAG/agent_toolkit/juhub | Прямые ходы в API из этих проектов |

**Чего НЕ даёт** (важно для калибровки over-engineering):
- не multi-tenant — нет нужды в RBAC, audit logs за пределами личных
- не SLA-критичный — downtime означает «открой браузер вручную»
- не cost-sensitive в узком смысле — основная стоимость это flat $20/мес Perplexity Pro
- не latency-критичный — 30–120 секунд per call воспринимается ОК

Архитектура построена под продукт **с другими constraints** (multi-tenant SaaS), но используется как личный proxy. Это и есть источник over-engineering.

---

## 2. Architecture snapshot

```
HTTP (FastAPI 0.115+)
  ↓
Routes (15 endpoints, /api/v1/*)
  ↓
Orchestrator → ExecutionRouter (concurrency gates, quorum, cancellation)
  ↓
Adapter ABC
  ├─ DryRunAdapter (тестовый профиль)
  ├─ BrowserPerplexity → PlaywrightDriver (1,122 LOC, single-thread executor)
  ├─ AnthropicAPI (httpx, Claude Sonnet 4.6)
  └─ OpenAICompatible (httpx, GPT-5.4)
  ↓
Storage ABC
  ├─ InMemory (dev)
  └─ PostgreSQL 16 (806 LOC, миграции, pool, валидатор)
```

**Cross-cutting:**
- Circuit breaker (3 fail → open 60s → half-open probe)
- Per-model concurrency semaphore
- Budget tracking (per-task / per-hour browser submits)
- Prometheus metrics на /metrics
- OpenTelemetry hooks (опционально)
- HMAC-safe auth, CSP/X-Frame, Redis rate limiter (опционально)
- Correlation IDs, structured logging

**Frontend:** vanilla JS SPA в static/, без фреймворков.

---

## 3. Engineering quality — где сильно

| Аспект | Оценка | Доказательство |
|---|---|---|
| Type safety | A+ | mypy --strict, 0 errors на 105 файлах |
| Architectural boundaries | A | Adapter ABC, контракты как frozen dataclass + slots, FailureCode enum |
| Test coverage | A+ | 159 файлов, 35.9k LOC, hypothesis property-based, ratio 2.32× |
| Tech debt hygiene | A+ | 0 TODO/FIXME/HACK комментариев в src/ (enforced) |
| Resilience patterns | A | Circuit breaker, gates, cancellation tokens, budgets — учебниковая реализация |
| Observability surface | A | Health (live/ready/detailed), Prometheus, structured logs, trace IDs |
| Security hygiene | A | hmac.compare_digest, CSP, без hardcoded creds, non-root Docker user |
| Documentation | A | opt.md (рыночный аудит), architecture.md, runbook, phased-roadmap, audits/ |
| Workflow discipline | A | CC/CX split, R1-R5 battery, batch-фазы, self-score ≥9 |

**Самые чистые модули** (стоят как референс):
- `core/circuit_breaker.py` — textbook state machine
- `core/contracts.py` — типизация и failure taxonomy
- `middleware.py` — security-aware HTTP layer
- `storage/postgres.py` — clean data layer (несмотря на размер)

Это код, который не стыдно показать на собеседовании на staff-engineer позицию.

---

## 4. Где over-engineering для personal use

Это центральная часть аудита. Каждый пункт — поверхность, которая стоит времени поддержки и не имеет потребителя.

### 4.1 Тестовая нагрузка несоразмерна

| Метрика | Значение | Оценка для single-user |
|---|---|---|
| Test files | 159 | Норма для SDK с публичным API |
| Test LOC | 35,972 | 2.32× продакшен-кода |
| Hypothesis property-based | присутствует | Justified только для критических контрактов |

**Стоимость:** каждое изменение в core/orchestrator.py или core/router.py требует трогать ~10–20 тестов. При 8 коммитах/день это 80–160 test-edits/день.

**Рекомендация:** оставить smoke + критический happy path (≈40 тестов). Удалить unit-тесты на обвязку (ratelimiter, корреляционные IDs, экспортёры). Снизить ratio до ~0.8–1.0×.

### 4.2 PostgreSQL backend для one-user

806 LOC `storage/postgres.py` + миграции + import/export tools + validate_postgres.py. Это полноценный data layer.

**Реальная нагрузка:** один пользователь, ~10–50 запросов/день, history readable за всю историю помещается в одиночный JSON.

**Memory backend достаточен.** PostgreSQL уместен, если планируется multi-user или восстановление history между перезапусками >100k задач. Ни то, ни другое не актуально.

**Стоимость удаления:** убрать ~1,500 LOC + миграционный фреймворк + dependency `psycopg`. Memory backend бесконечно проще.

**Если хочется persistence** — SQLite через `sqlite3` (stdlib), 50 LOC адаптер.

### 4.3 Prometheus + OpenTelemetry surface

`/metrics` endpoint в Prometheus формате, гистограммы латенси, OTLP exporter hook. На localhost. Без Prometheus сервера, без Grafana, без Alertmanager.

**Это написано «по best practice», но не имеет потребителя.** Метрики никто не агрегирует, графики никто не смотрит, алерты не настроены.

**Рекомендация:** оставить базовый /health (live/ready). Удалить /metrics, OpenTelemetry, request_metrics.py гистограммы. Структурированные логи в JSON-файл достаточны.

### 4.4 Circuit breaker на N=1 трафике

Circuit breaker имеет статистический смысл при множественных параллельных запросах: «3 из последних 10 упали → отрубаем». На N=1 пользователе с 1–3 одновременных задач это deterministic «упал → жди 60 секунд».

**Применение:** простой retry с exponential backoff даёт тот же эффект в 30 LOC вместо ~200 LOC + state machine.

### 4.5 Rate limiter (опциональный, Redis-backed)

Single user не нужно self-rate-limit. Полностью лишний layer. Удалить middleware-блок + dependency на redis.

### 4.6 Trace correlation, request IDs

Distributed tracing для localhost. Correlation ID имеет смысл, когда запрос проходит через 3+ сервиса. У нас FastAPI → adapter → external — два прыжка.

Можно оставить как отладочный nice-to-have, но HTTP middleware для корреляции — лишний.

### 4.7 Orchestration patterns: 11 endpoints, реально использует 2–3

Endpoint inventory:
| # | Route | Назначение | Likely usage |
|---|---|---|---|
| 1 | POST /orchestrate | основной (single/multi) | ВЫСОКО |
| 2 | POST /orchestrate/stream | SSE | НИЗКО |
| 3 | POST /consensus | majority vote | СРЕДНЕ |
| 4 | POST /compare | pairwise | СРЕДНЕ |
| 5 | POST /debate | devil's advocate | СРЕДНЕ |
| 6 | POST /smart | auto-routing v1 | НИЗКО |
| 7 | POST /smart/v2 | HAC clustering | НИЗКО |
| 8 | POST /batch | parallel multi-prompt | НИЗКО |
| 9 | POST /pipeline | task graph | НЕ ИМПЛЕМЕНТИРОВАНО ПОЛНОСТЬЮ |
| 10 | GET /tasks/* | history | СРЕДНЕ |
| 11 | GET /analytics | aggregate stats | НИЗКО |

**Smart v2 с hierarchical agglomerative clustering** для consensus — особый случай. Это машинерия из академических статей про NLI. На N=3–5 моделей min-Levenshtein или word-overlap дают ту же точность за 5% сложности.

**Mistral embeddings** оставлены **только** для clustering в smart v2. Если smart v2 удалить — можно убрать весь embeddings stack.

**Рекомендация:** удалить smart, smart/v2, batch, pipeline. Оставить orchestrate, consensus, compare, debate, tasks/, models/.

### 4.8 Большие модули, требующие декомпозиции

| Файл | LOC | Концерны (смешаны) | Рекомендация |
|---|---|---|---|
| `playwright_driver.py` | 1,122 | session, popups, model selection, cold-start nav, screenshots, profile lock | Разделить: thin Playwright bind (300 LOC) + Perplexity policy (500 LOC) + recon helpers (200 LOC) |
| `orchestrate.py` | 851 | request validation, planning, decomposition, execution, event building | Разделить: planner, executor coordinator, response builder |
| `postgres.py` | 806 | будет удалён по §4.2 | — |
| `router.py` | 541 | dispatch + concurrency + quorum + cancellation | Допустимо, но quorum/merge можно вынести |

### 4.9 Резюме over-engineering

Если применить §4.1–4.8 целиком:
- LOC src: 15,500 → ~9,000 (–42%)
- LOC tests: 36,000 → ~12,000 (–67%)
- Файлов: 105 → ~70
- Dependencies: убрать psycopg, redis, opentelemetry, prometheus_client, mistral SDK
- Endpoints: 11 → 6
- Maintenance: ~10 hr/неделя → ~3 hr/неделя

При сохранении ~95% реальных use cases (orchestrate, consensus, compare, debate, history).

---

## 5. Реальные риски

Ранжированы по вероятности × impact, без enterprise-флагов (multi-tenant, RBAC, SSO — не применимо).

### 5.1 HIGH: Perplexity ToS / Cloudflare bot detection

**Что:** Browser automation через Playwright технически квалифицируется как automated access. Perplexity ToS не запрещает явно, но и не разрешает. Cloudflare Turnstile + fingerprinting детектят headless и могут забанить аккаунт.

**Триггеры:** редизайн bot detection, рост automated traffic от других пользователей PerPlex/Cloudflare, обнаружение characteristic patterns (всегда одна и та же sequence DOM операций).

**Mitigation сейчас:** dedicated chrome profile, без headless флага.

**План B:** нет. API fallback — это другой бизнес-модель ($50–150/мес vs $20/мес flat).

**Действия:**
- Документировать ToS-проверку в README (юзер должен принять риск осознанно)
- Готовить экспортёр истории + быстрый план миграции на API-only
- Не продвигать GraceKelly публично — массовый автоматизм увеличивает риск ban

### 5.2 HIGH: Perplexity UI breaks

**Что:** 1,122 LOC Playwright-обёртки на CSS селекторы. Perplexity редизайнит UI ≈раз в 2–3 месяца.

**Симптомы:** model picker не открывается, popup не закрывается, response selector возвращает пусто.

**Mitigation:** capture_perplexity_recon.py + ручной апдейт selectors.

**Time-to-recovery:** прошлые случаи (по `git log --grep selector`) — ~2–6 часов на инцидент.

**Действия:**
- Weekly cron `recon → diff → notification` чтобы ловить изменения до того как они ломают использование
- Snapshot предыдущей версии селекторов для быстрого rollback
- Замаркировать тесты, которые проверяют конкретные селекторы — разделить от логических

### 5.3 MEDIUM: Profile lock collision

**Что:** chrome profile занят, если пользователь открыл Perplexity вручную. _profile_is_locked detection присутствует, но это не предотвращение.

**Frequency:** ежедневно у любого пользователя, кто заходит в Perplexity вручную.

**Действия:**
- Документировать в README жирным
- В UI показывать предупреждение «закройте Perplexity в браузере»
- Использовать **отдельный профиль** Chrome специально для GraceKelly (уже сделано — chrome-profile/)

### 5.4 MEDIUM: Model catalog staleness

**Что:** новые модели в Perplexity появляются только при перезапуске приложения. Endpoint POST /api/v1/models/refresh существует, но его надо нажимать вручную.

**Действия:** на startup + каждые 6 часов автоматический refresh. 20 LOC.

### 5.5 MEDIUM: Cold-start latency

**Что:** первый запрос после простоя — 30 сек на Playwright нав + auth check.

**Mitigation:** thinking memoize + session persistence в latest коммитах (2026-04-26 stability run).

**Действия:** оставить как есть, фиксировать только если станет ежедневным фрикшеном.

### 5.6 HIGH: Opportunity cost

**Не технический, но критический.**

138 commits за 7 дней. При среднем коммите 30 минут (read-edit-test-commit cycle) = ~70 часов работы за неделю. Это full-time job на personal infrastructure.

**Активные параллельные проекты пользователя:** PageCraft, JobPilot, GraceKelly, RAG_Support_Assistant, Pages_new, AB_TEST, DE_project. Семь.

**Вопрос:** GraceKelly даёт пропорционально 1/7 ценности? Или пожирает 4/7 времени?

**Действия:**
- Записать **реальное использование** GraceKelly за 30 дней: какие endpoints вызывались, какие models, в контексте каких задач, какой output реально потреблён vs выброшен
- Если usage data покажет, что 80% запросов идут через 2 endpoint и 3 модели — все остальное удалять
- Если usage покажет <50 реальных продуктивных запросов в месяц — пересмотреть весь подход (см. §7 опции C/D)

### 5.7 LOW: Maintenance debt forever

Selectors, dependencies, Python versions, Chrome versions — постоянная поддержка. Ни один personal project не существует «в стабильном состоянии» бесконечно. Решение должно учитывать готовность платить maintenance tax 2–4 hr/месяц **forever**.

---

## 6. Где НЕ over-engineering (защищать)

Чтобы аудит был сбалансирован — что точно стоит сохранить:

1. **mypy --strict** — нулевая стоимость поддержки, бесконечный value при коллаборации с Codex CX
2. **Adapter ABC + FailureCode enum** — единственный способ удержать множественные провайдеры читаемыми
3. **Dry-run профиль** — инструмент для интеграторов, реальная польза
4. **Health endpoints (live/ready)** — нужны для Windows autostart restart logic
5. **Audit-trail history** — даже single-user хочет видеть «что я спрашивал на той неделе»
6. **CC/CX workflow + R1-R5 battery + batch фазы** — это рабочий процесс, не продукт. Менять не нужно.
7. **opt.md, architecture.md, audits/** — документация-как-asset. Стоит больше, чем код.

---

## 7. Стратегические опции

Четыре пути. BCG-style: trade-offs explicit, no false neutrality.

### Option A: Continue as-is

**Что:** поддерживать текущую архитектуру, добавлять fixes по мере поломок.

**Стоимость:** ~10 hr/неделя (selectors recon, mypy fixes по cascade, тесты на новые endpoints, Codex CX задачи).

**Riek:** maintenance долг растёт линейно, opportunity cost остаётся высоким.

**Когда выбрать:** если GraceKelly — это **тренировочный полигон** для engineering practice (CX/CC workflow, mypy strict, Playwright skills). Тогда over-engineering — feature, а не bug.

**Score:** 6/10 если личный полигон. 3/10 если рабочий инструмент.

### Option B: Simplify (рекомендуется)

**Что:** Срез по §4. Cохранить core (orchestrate, consensus, compare, debate, history). Удалить PostgreSQL, Prometheus, OpenTelemetry, smart v2, batch, pipeline, Mistral embeddings. Декомпозировать playwright_driver.

**Стоимость трансформации:** 1–2 недели concentrated work. Можно через CX в batch-режиме.

**Maintenance после:** ~3 hr/неделя.

**Сохраняет:** ~95% реального value, всю engineering-дисциплину (mypy strict, adapter ABC, тесты), Perplexity-as-primary execution.

**Score:** 9/10 как баланс engineering excellence vs personal scope.

### Option C: Pivot to API-first

**Что:** переписать как тонкий proxy перед OpenRouter / LiteLLM. Browser automation становится «experimental backend», не primary.

**Преимущества:**
- Никакого ToS-риска
- Стабильность (нет UI breaks)
- Cloud deployable, если потребуется
- API доступ к моделям, которых нет в Perplexity

**Недостатки:**
- $50–150/мес pay-per-use vs $20/мес Perplexity Pro flat
- Теряется уникальный value-prop (browser-first)
- 6+ недель работы на pivot

**Когда выбрать:** если usage показывает >200 запросов/день и Perplexity-зависимость становится узким местом.

**Score:** 7/10 long-term, 4/10 short-term для personal use.

### Option D: Retire

**Что:** убить GraceKelly, заменить existing tools.

| Use case | Замена |
|---|---|
| Multi-model orchestration | OpenRouter ($) или LiteLLM (self-host) |
| Perplexity Pro доступ | браузер вручную, Continue.dev для IDE |
| Compare/debate/consensus | 500 LOC standalone scripts (Python + httpx) |
| RAG/agent_toolkit/juhub integrations | прямые вызовы OpenRouter из этих проектов |

**Стоимость:** 1 неделя на переключение integrations + скрипт debate/consensus.

**Возврат:** ~70 hr/неделя свободного времени, $30–80/мес дополнительно на API.

**Когда выбрать:** если honest usage audit (см. 5.6) покажет <30 productive запросов/неделя через GraceKelly.

**Score:** 8/10 если usage низкий. 5/10 если usage реально активный.

### Сравнительная таблица

| Опция | LOC change | Maintenance/нед | Лучший case | Худший case |
|---|---|---|---|---|
| A: Continue | 0% | ~10 hr | engineering полигон | thrash |
| B: Simplify | –42% src | ~3 hr | personal tool с дисциплиной | теряем тестовую культуру |
| C: API-pivot | переписать 60% | ~5 hr | стабильность, scaling | теряем Perplexity flat-rate |
| D: Retire | –100% | 0 hr | свободное время | теряем 382 коммита value |

---

## 8. Recommendations (приоритезированы по effort/value)

### Now (неделя 1)

**R1. Honest usage telemetry.**
Включить логирование: endpoint, models, prompt-hash, response-bytes, success/fail, ms-latency. На 30 дней. Без аналитики, просто JSONL append.
**Effort:** 2 часа. **Decision input:** какой § 7 опции выбрать.

**R2. Zaморозить v0.1.0 как tagged release.**
Текущее состояние — самое стабильное (по git log стабилизационные коммиты 2026-04-25/26). Зафиксировать тег `v0.1.0-pre-simplify`. Это safety net перед любым refactor.
**Effort:** 30 минут.

**R3. README про ToS risk.**
Добавить блок: «GraceKelly использует browser automation против Perplexity. ToS не запрещает явно, но Cloudflare может детектить. Используйте на свой риск.» Не для кого-то — для себя через год.
**Effort:** 15 минут.

### Soon (недели 2–4)

**R4. Selectors weekly recon cron.**
Windows Task Scheduler: пятница 03:00, прогон capture_perplexity_recon.py, diff с предыдущим snapshot, notification если diff. Уменьшит time-to-detect Perplexity UI changes с «когда сломается на демо» до 1 недели.
**Effort:** 4 часа.

**R5. Принять решение по §7.**
После 2 недель usage telemetry — посмотреть данные, выбрать A/B/C/D. Не откладывать. Решение откладывать стоит ~10 hr/неделя.

### After decision (недели 5–8)

**Если B (Simplify):**
- R6.1 Удалить PostgreSQL backend. Сохранить SQLite-вариант или JSON snapshots.
- R6.2 Удалить Prometheus, OpenTelemetry, request_metrics.
- R6.3 Удалить smart, smart/v2, batch, pipeline endpoints.
- R6.4 Декомпозировать playwright_driver на 3 файла.
- R6.5 Урезать тесты до critical happy path.

**Если C (Pivot):**
- R7.1 Spike OpenRouter integration (1 неделя).
- R7.2 Если работает — перенести RAG/agent_toolkit/juhub на новый backend.
- R7.3 Browser adapter переводится в `experimental/`.

**Если D (Retire):**
- R8.1 Экспорт всей history в markdown для архива.
- R8.2 500 LOC standalone debate.py + consensus.py.
- R8.3 Migrate 3 integrators на OpenRouter напрямую.
- R8.4 Archive репозиторий.

---

## 9. Чего НЕ делать

Anti-patterns, которые соблазнительно сделать, но не стоит:

- **Не добавлять новые orchestration patterns** пока не используешь существующие 11. Each new pattern = +200 LOC + tests + docs = +2 hr/неделя forever.
- **Не строить cloud-deployment story.** Нет use case. Если появится — будет другой проект.
- **Не делать UI редизайн.** Secure mode broken — фиксить только когда реально мешает (если используешь без auth, не мешает).
- **Не воспринимать «8 коммитов/день» как velocity.** Часто это thrash: серия мелких fixes на cascade-проблемах. Real velocity = «одна batch-фаза с измеримой ценностью».
- **Не делать рыночный pivot (B2B, мульти-tenant).** opt.md правильно отметил, что monetization 3/10. Это personal tool, не стартап. Конкурировать с OpenRouter/Portkey — заведомо проигрышная битва без капитала.
- **Не разогревать Mistral как LLM provider.** Уже удалили правильно. Не возвращать.

---

## 10. Финальные оценки

| Измерение | Score | Комментарий |
|---|---|---|
| Engineering execution | 9/10 | Чище, чем большинство production кода в B2B SaaS |
| Architectural clarity | 9/10 | Adapter ABC, контракты, failure taxonomy — учебниковая |
| Test discipline | 9/10 | Слишком хорошо для single-user, но это плюс |
| Strategic alignment с personal use | 5/10 | Over-engineering на ~40% поверхности |
| Maintenance sustainability | 6/10 | ~10 hr/неделя без §7 — это слишком много для personal |
| Real value vs alternatives | 7/10 | Уникальная Perplexity-первой архитектура; всё остальное замещаемо |
| Risk management | 5/10 | ToS-риск не задокументирован, нет план B на ban |
| Documentation | 9/10 | opt.md и phased-roadmap.md — образцовые |

**Aggregate (для personal product):** 7/10 как есть. С Option B Simplify — 8.5/10.

---

## 11. Ключевой вопрос для пользователя

Не «как улучшить GraceKelly?» (это закроет 100 дней работы и поверхность вырастет).

А: **«Это тренировочный полигон или рабочий инструмент?»**

- Если **полигон** — продолжать как есть (Option A). Over-engineering — это feature, проект учит engineering excellence через скоп.
- Если **рабочий инструмент** — Option B Simplify. Срез ~40%, фокус на 3–5 endpoints, maintenance падает в 3×, value не теряется.

Эти две оптики дают противоположные roadmap. Без выбора — drift в Option A by default, и через 3 месяца это будут 800 commits с теми же 70 hr/неделя cost.

Решение — на следующих 2 неделях, после R1 (usage telemetry).

---

**Конец отчёта.**
