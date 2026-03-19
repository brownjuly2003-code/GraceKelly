# Gap Analysis: Perplexity_Orchestrator2 → GraceKelly

Дата: 2026-03-19
Источник: D:\Perplexity_Orchestrator2 (master)
Целевой проект: D:\GraceKelly (main)

---

## 1. Что идейно НЕ реализовано в GraceKelly

### 1.1 Критические идейные пробелы (определяют качество ответов)

| # | Возможность | Старый проект | GraceKelly | Приоритет |
|---|-------------|---------------|------------|-----------|
| G-1 | **Embedding-based consensus** — кластеризация ответов через Mistral embeddings, cosine similarity, AgglomerativeClustering | `orchestrator/consensus.py`, `ConsensusAnalyzer`, порог 85% similarity | Нет. Только `first_success` и `concat` merge strategies — нет семантического сравнения ответов | CRITICAL |
| G-2 | **12-role system** — специализированные роли: Planner, Executor, Verifier, Judge, Devil's Advocate, Synthesizer, Fact Verifier, Logic Verifier, Completeness Verifier, Researcher, Code Executor, Decomposer | `orchestrator/roles.py`, каждая роль = system prompt + preferred model + reasoning flag | Нет. Модели вызываются без ролевых system prompts | HIGH |
| G-3 | **MAXIMUM reliability level** — итеративный цикл: 5 моделей × 3 вариации промпта → кластеризация → cross-validation Claude → повторение до consensus ≥ 95% | `orchestrator/run_modes.py:_run_maximum()` + `_run_consensus_based()` | Нет. Один раунд выполнения, нет итеративного достижения консенсуса | HIGH |
| G-4 | **Task decomposition** — автоматическая оценка сложности запроса, разбивка на подзадачи, выполнение с синтезом | `api/routes/gk_decomposition.py`, `_assess_complexity()`, `_run_decomposed()` | Нет. Prompt выполняется как есть, без декомпозиции | HIGH |
| G-5 | **Prompt variation generator** — 9 вариаций промпта для увеличения diversity ответов | `ConsensusAnalyzer.PromptVariationGenerator`, циклирование по 3 за раунд | Нет. Один prompt → один ответ на модель | MEDIUM |

### 1.2 Операционные пробелы

| # | Возможность | Старый проект | GraceKelly | Приоритет |
|---|-------------|---------------|------------|-----------|
| G-6 | **Adaptive model selection** — выбор моделей по исторической статистике (success rate, task type) | `analytics/model_selector.py`, `IntelligentModelSelector`, 6 типов задач | Нет. Статический MODEL_SPECS, ручной выбор | MEDIUM |
| G-7 | **Statistics collector** — сбор метрик по задачам, моделям, consensus scores в SQLite | `analytics/collector.py`, `StatsCollector` | Нет. Есть events, но нет агрегированной аналитики | MEDIUM |
| G-8 | **Task graph** — граф зависимостей подзадач, resume после прерывания, status tracking | `tasks/task_graph.py`, `TaskGraph`, `SubTask`, statuses | Нет. Нет dependency graph. retry есть, но только task-level | LOW |
| G-9 | **Account rotation** — пул из ~30 аккаунтов Perplexity, ротация при failures | `browser/model_selection.py`, `on_model_selection_failed` callback | Частично. `AccountPool` создан, но не подключён к browser adapter | MEDIUM |
| G-10 | **File attachment** — отправка длинных промптов через файл в Perplexity UI | `browser/query.py`, `send_long_prompt_via_file()` | Нет. Только текстовый ввод | LOW |

### 1.3 Паттерны выполнения (GK Patterns)

| Паттерн | Старый проект | GraceKelly |
|---------|---------------|------------|
| **SONAR** — быстрый поиск, 1 модель без reasoning | ✅ `run_sonar()` | ✅ Через single model execution |
| **SINGLE** — 1 модель с reasoning | ✅ `run_single()` | ✅ Через single model execution + reasoning=true |
| **DUAL** — 2 модели, ответы рядом для сравнения | ✅ `run_dual()`, фиксированные пары | ✅ Через multi-model с quorum=2 + concat |
| **FIVE_MODELS** — все 5 моделей, без анализа | ✅ `run_five_models()` | ✅ Через multi-model с concat |
| **FIVE_MODELS_COMPARE** — 5 моделей + Claude анализирует | ✅ `run_five_models_compare()` | ❌ Нет 2-фазного выполнения (сбор → анализ) |
| **CONSENSUS** — 3 модели × 3 вариации, порог 90% | ✅ `run_consensus()` | ❌ Нет consensus-based execution |
| **MAXIMUM** — 5 моделей × 3 вариации, итеративный цикл до 95% | ✅ `run_maximum()` | ❌ Нет iterative consensus loop |

---

## 2. Дочерние проекты и сервисы

### 2.1 JuHub — AI Daily Debate

**Статус**: активный, используется.
**Расположение**: `Perplexity_Orchestrator2/juhub/`
**Зависимости**: GK API, Perplexity browser, Mistral API, Ollama (локальные модели), Windows Task Scheduler.

**Что делает**:
- Каждый день в 08:30 запускает дебат на AI-тему
- 8 моделей (4 Perplexity + 4 API) генерируют по 20 утверждений + вердикт
- TF-IDF deduplication → отбор спорных (≥3 голоса с каждой стороны)
- Cross-voting всех 8 моделей за каждое утверждение
- Аргументы pro/con от каждой модели
- Экспорт в JSON + SQLite + frontend

**Связь с GraceKelly**: использует GK как транспорт (паттерны `single` и `five_models`). Не использует consensus/clustering.

**Что нужно от GraceKelly**: стабильный API для single-model и multi-model execution, account pool для надёжности.

### 2.2 English Practice

**Статус**: эксперимент, используется периодически.
**Расположение**: `Perplexity_Orchestrator2/api/routes/english.py` + `static/english.html`

**Что делает**: тренажёр разговорного английского. Диалог с AI (Mistral), анализ grammar/vocabulary/fluency каждого ответа, голосовой ввод.

**Связь с GraceKelly**: минимальная. Вызывает Mistral API напрямую для низкой latency.

### 2.3 Interview Trainer

**Статус**: эксперимент.
**Расположение**: `Perplexity_Orchestrator2/api/routes/interview.py` + `static/interview.html`

**Что делает**: симулятор техн./поведенческого интервью. Тема → уровень → батч вопросов → оценка ответов 1-10 → итоговый отчёт.

**Связь с GraceKelly**: зависит от BrowserWorker для генерации через Perplexity.

### 2.4 Analytics Dashboard

**Статус**: internal tool, активен.
**Расположение**: `Perplexity_Orchestrator2/api/routes/analytics.py` + `static/analytics.html` + `analytics/`

**Что делает**: дашборд использования — модели, паттерны, ошибки, аккаунты. Графики, фильтры по периоду.

**Связь с GraceKelly**: читает SQLite БД оркестратора.

### 2.5 Page Builder

**Статус**: сайд-проект, низкая активность.
**Расположение**: `Perplexity_Orchestrator2/api/routes/webpage.py` + `static/webpage.html`

**Что делает**: генератор HTML-страниц по описанию через AI + пресеты стилей.

### 2.6 A/B Testing Pipelines

**Статус**: контентный pipeline, завершён.
**Расположение**: `Perplexity_Orchestrator2/ab-testing-course/` + `ab-testing-advanced/`

**Что делает**: 5-этапный аудит HTML-глав курсов через GK API (Sonnet → Second audit → Merge → Apply → Validate). 60 глав суммарно.

### 2.7 Telegram Bot

**Статус**: эксперимент, низкая активность.
**Расположение**: `Perplexity_Orchestrator2/telegram_bot/`

**Что делает**: альтернативный интерфейс к GK через Telegram (aiogram).

### 2.8 RAG Support Assistant

**Статус**: отдельный проект.
**Расположение**: `D:\RAG_Support_Assistant` (вне репозитория)
**Порт**: 8000

**Что делает**: RAG pipeline с vector store, document upload (PDF/DOCX/TXT), web chat UI, dashboard с трассами и эскалациями.

---

## 3. План реализации: от текущего GraceKelly к полной замене

### Phase 6: Consensus Engine (приоритет CRITICAL)

**Цель**: Реализовать embedding-based consensus — ключевое отличие от простого multi-model execution.

**Deliverables**:
- [ ] Mistral Embeddings client с кэшированием (`core/embeddings.py`)
- [ ] `ConsensusAnalyzer` — кластеризация ответов через cosine similarity + AgglomerativeClustering
- [ ] `ConsensusResult` — consensus_score, num_clusters, top_cluster, needs_debate
- [ ] `PromptVariationGenerator` — 9 вариаций промпта
- [ ] Интеграция в execution pipeline: `merge_strategy=consensus`
- [ ] Cross-validation через Claude при consensus < 70%

**Audit gate**: Gate 6 — independent review consensus accuracy vs manual assessment на 20 тестовых вопросах.

**Зависимости**: Mistral API key для embeddings.

**Оценка**: 3-4 дня.

### Phase 7: Role System (приоритет HIGH)

**Цель**: Специализированные system prompts для верификации, синтеза, judgment.

**Deliverables**:
- [ ] `core/roles.py` — RoleType enum (Verifier, Synthesizer, Judge, Devil's Advocate, Fact Verifier, Decomposer) + system prompt templates
- [ ] Role-aware execution: adapter получает system prompt для роли
- [ ] Многоэтапное выполнение: execute → verify → synthesize
- [ ] FIVE_MODELS_COMPARE паттерн: сбор ответов → анализ Claude с Judge role

**Audit gate**: Gate 7 — review роли Fact Verifier и Devil's Advocate на детекцию галлюцинаций.

**Оценка**: 2-3 дня.

### Phase 8: Task Decomposition (приоритет HIGH)

**Цель**: Автоматическая разбивка сложных запросов на подзадачи.

**Deliverables**:
- [ ] `core/decomposition.py` — complexity assessment (простой/сложный)
- [ ] Декомпозиция через LLM: prompt → JSON список подзадач
- [ ] Выполнение подзадач через тот же pipeline (рекурсивно или плоско)
- [ ] Синтез результатов подзадач в итоговый ответ
- [ ] Тесты: простой вопрос → без декомпозиции, сложный → 3+ подзадач

**Оценка**: 2 дня.

### Phase 9: Reliability Levels (приоритет HIGH)

**Цель**: Режимы QUICK/STANDARD/HIGH/MAXIMUM с разным уровнем верификации.

**Deliverables**:
- [ ] `core/reliability.py` — ReliabilityLevel enum
- [ ] QUICK: 1 execution + fact check
- [ ] STANDARD: 2 executions + comparison + synthesis
- [ ] HIGH: 3 executions + full verification + devil's advocate
- [ ] MAXIMUM: iterative consensus loop до порога
- [ ] API: `reliability_level` параметр в OrchestrateRequest
- [ ] Маппинг reliability level → набор ролей + число моделей + consensus threshold

**Зависимости**: Phase 6 (consensus), Phase 7 (roles).

**Оценка**: 2-3 дня.

### Phase 10: Analytics & Adaptive Routing (приоритет MEDIUM)

**Цель**: Умный выбор моделей на основе исторических данных.

**Deliverables**:
- [ ] `core/task_classifier.py` — классификация задач по типу (analysis, coding, creative, research, math, general)
- [ ] `core/model_stats.py` — агрегация success_rate, latency, consensus contribution по моделям
- [ ] `core/adaptive_selector.py` — выбор лучших моделей для task type
- [ ] Storage: расширить events или отдельная таблица для model performance
- [ ] API: `/api/v1/analytics` endpoint для операторов

**Оценка**: 2 дня.

### Phase 11: Account Pool Integration (приоритет MEDIUM)

**Цель**: Подключить AccountPool к browser adapter для ротации аккаунтов.

**Deliverables**:
- [ ] Загрузка аккаунтов из config (JSON или env)
- [ ] Browser adapter: acquire account → execute → release/cooldown
- [ ] Ротация при rate limit и auth failure
- [ ] Healthcheck: available/busy/cooldown accounts
- [ ] Тесты: concurrent execution через разные аккаунты

**Оценка**: 1-2 дня.

### Phase 12: Child Project APIs (приоритет LOW)

**Цель**: Поддержать нужды дочерних проектов.

**Deliverables**:
- [ ] JuHub: стабильный single/multi-model API уже есть, добавить webhook для scheduler
- [ ] A/B pipeline: batch endpoint для аудита нескольких глав
- [ ] Debate: dedicated debate endpoint или шаблон
- [ ] Evaluate: нужно ли English Practice / Interview Trainer в GraceKelly или они живут отдельно

**Оценка**: по потребности.

---

## 4. Audit Gates

| Gate | Когда | Что проверяется |
|------|-------|-----------------|
| Gate 6 | После Phase 6 (consensus) | Точность consensus vs manual assessment на 20 вопросах |
| Gate 7 | После Phase 7 (roles) | Fact Verifier catch rate на синтетических галлюцинациях |
| Gate 8 | После Phase 8 (decomposition) | Качество декомпозиции на 10 сложных и 10 простых задачах |
| Gate 9 | После Phase 9 (reliability) | End-to-end: MAXIMUM level на 5 спорных и 5 фактических вопросах |
| Gate 10 | После Phase 10 (analytics) | Adaptive selector outperforms random на historical data |

---

## 5. Приоритизация

```
Phase 6 (Consensus)        ████████████████  CRITICAL — core value proposition
Phase 7 (Roles)            ████████████      HIGH — verification quality
Phase 8 (Decomposition)    ████████████      HIGH — complex task support
Phase 9 (Reliability)      ████████████      HIGH — ties everything together
Phase 10 (Analytics)       ████████          MEDIUM — optimization
Phase 11 (Account Pool)    ████████          MEDIUM — operational reliability
Phase 12 (Child Projects)  ████              LOW — incremental
```

Суммарная оценка: **14-18 дней** при фокусированной работе (1-2 агента).

---

## 6. Что НЕ стоит переносить из старого проекта

| Компонент | Причина |
|-----------|---------|
| Legacy `/orchestrate` endpoint | Заменён на GK API |
| SQLite как primary storage | PostgreSQL уже есть |
| In-process `asyncio.create_task` state | GraceKelly имеет proper task persistence |
| `config/accounts.json` с plaintext паролями | Security risk. Использовать env vars |
| `arch/` (774 файла архивов) | Не код |
| Page Builder | Не связан с core value |
| Telegram bot | Отдельный deployment |
| Monitoring с hardcoded credentials | Переписано в GraceKelly middleware |
