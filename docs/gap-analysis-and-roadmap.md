# Gap Analysis: Perplexity_Orchestrator2 → GraceKelly

Дата: 2026-03-19
Источник: D:\Perplexity_Orchestrator2 (master)
Целевой проект: D:\GraceKelly (main)

---

## 0. Ландшафт: multi-model orchestration в 2024-2026

### Ключевые подходы в индустрии

| Подход | Авторы | Consensus метод | Роли | Decomposition | Итерации |
|--------|--------|-----------------|------|---------------|----------|
| **ReConcile** (ACL 2024) | Chen et al. | Confidence-weighted voting + раунды дискуссии между моделями. Каждая модель видит ответы и confidence-scores остальных, убеждает друг друга | Нет — модели равноправны | Нет | Да — до сходимости |
| **Mixture-of-Agents** (Together AI, 2024) | Wang et al. | Layered: слой Proposers → слой Aggregator. Каждый слой видит выход предыдущего. Exploits "collaborativeness" — модели дают лучшие ответы, видя чужие | 2: Proposer + Aggregator | Нет | Да — N layers |
| **LLM Council** (Karpathy, 2025) | Karpathy | 3 стадии: independent answers → anonymous peer review (модели ранжируют чужие ответы) → Chairman synthesizes | 1: Chairman | Нет | Нет — 1 pass |
| **Consilium** (HF Hackathon, 2025) | Community | Majority voting / Ranked choice. 3 topology: Full (все видят всех), Ring (каждый видит предыдущего), Star (через Lead Analyst) | 1: Lead Analyst | Нет | Нет |
| **DeepMind Delegation** (Feb 2026) | Tomašev et al. | Game-theoretic: Schelling points, dispute panels, cryptographic proofs, escrow mechanics, recursive liability | Delegator/Delegate hierarchy | Да — dynamic decomposition | Да — recursive |
| **Perplexity_Orchestrator2** (наш) | — | Embedding clustering (Mistral, cosine ≥ 0.85) + cross-validation Claude + iterative loop до consensus ≥ 95% с 9 prompt variations | 12 ролей (Verifier, Judge, Devil's Advocate, Synthesizer...) | Да — complexity assessment → subtask graph → synthesis | Да — до порога |

### Оценка нашей модели на фоне state-of-art

**Что наш оркестратор делает ЛУЧШЕ** большинства open-source решений:

1. **Embedding-based clustering** (семантический уровень). ReConcile и LLM Council используют text-level voting/ranking. Наш проект кластеризует через embeddings + AgglomerativeClustering — семантически глубже, чем majority vote.

2. **Итеративный consensus loop до порога**. Ни один open-source фреймворк (кроме ReConcile) не делает итеративные раунды. MAXIMUM mode — уникален: 5 моделей × 3 prompt variations × N раундов до consensus ≥ 95%.

3. **Task decomposition** — из перечисленных только DeepMind (теория без кода) и наш проект (рабочая реализация) делают автоматическую декомпозицию с complexity assessment.

4. **12 ролей** — самая развитая ролевая система. LLM Council: 1 роль (Chairman). MoA: 2 роли. Наши Devil's Advocate + Fact Verifier — уникальная комбинация.

5. **Prompt variations** — 9 переформулировок. Ни один фреймворк не делает автоматические prompt variations.

**Что стоит ВЗЯТЬ из индустрии** (нет в нашей модели):

| Идея | Источник | Приоритет | Обоснование |
|------|----------|-----------|-------------|
| **Anonymous peer review** — модели ранжируют чужие ответы, не зная авторства | LLM Council | HIGH | Снижает self-bias, дополняет embedding clustering |
| **Confidence scores** — каждая модель оценивает уверенность в ответе (1-10) | ReConcile | HIGH | Weighted voting точнее простого clustering |
| **Layered aggregation** — proposers → aggregator в 2+ слоя | MoA | MEDIUM | +10% quality по AlpacaEval, но дорого по токенам |
| **Communication topologies** — Star/Ring/Full | Consilium | LOW | Нишевое, Ring экономит токены |
| **Verifiable execution** — cryptographic proofs | DeepMind | LOW | Overkill для текущего scope |

**Итоговая оценка старой модели**:

| Аспект | Оценка | Комментарий |
|--------|--------|-------------|
| Идейная глубина | **9/10** | Сочетание consensus + roles + decomposition + prompt variations — нет аналога в open-source |
| Уникальность | **8/10** | Embedding clustering + iterative loop + 12 ролей уникальны |
| Реализация | **5/10** | Хрупкий browser, нет тестов consensus, plaintext secrets |
| Production-readiness | **3/10** | Vs CrewAI/LangGraph — не в одной лиге |
| Научная обоснованность | **7/10** | Consensus ближе к ReConcile, чем к простому voting |

**Вывод**: идейно это одна из самых продвинутых моделей оркестрации. Проблема в реализации, не в концепции. GraceKelly должна перенести идеи + обогатить peer review и confidence scores из индустрии.

### Источники

- [ReConcile: Round-Table Conference (ACL 2024)](https://arxiv.org/abs/2309.13007)
- [Mixture-of-Agents (Together AI, 2024)](https://arxiv.org/abs/2406.04692)
- [LLM Council (Karpathy, 2025)](https://github.com/karpathy/llm-council)
- [Consilium: Multi-LLM Collaboration (HF, 2025)](https://huggingface.co/blog/consilium-multi-llm)
- [Google DeepMind Intelligent AI Delegation (Feb 2026)](https://arxiv.org/pdf/2602.11865)
- [CrewAI vs LangGraph vs AutoGen 2026](https://dev.to/synsun/autogen-vs-langgraph-vs-crewai-which-agent-framework-actually-holds-up-in-2026-3fl8)
- [Multi-Agent LLM for Incident Response (2025)](https://arxiv.org/abs/2511.15755)

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

**Цель**: Реализовать embedding-based consensus — ключевое отличие от простого multi-model execution. Обогатить peer review (LLM Council) и confidence scoring (ReConcile).

**Deliverables**:
- [ ] Mistral Embeddings client с кэшированием по SHA256 (`core/embeddings.py`)
- [ ] `ConsensusAnalyzer` — кластеризация ответов через cosine similarity + AgglomerativeClustering (порог ≥ 0.85)
- [ ] `ConsensusResult` — consensus_score, num_clusters, top_cluster, needs_debate, clusters detail
- [ ] `PromptVariationGenerator` — 9 вариаций промпта, циклирование по 3 за раунд
- [ ] Интеграция в execution pipeline: `merge_strategy=consensus`
- [ ] Cross-validation через Claude при consensus < 70% (из старого проекта)
- [ ] **[NEW from LLM Council]** Anonymous peer review: после сбора ответов каждая модель ранжирует чужие ответы (анонимизированные) — peer_rankings дополняют embedding score
- [ ] **[NEW from ReConcile]** Confidence scoring: каждая модель оценивает уверенность в своём ответе (1-10), используется для weighted voting при близких кластерах
- [ ] Итеративный loop: раунды до consensus ≥ threshold (настраиваемый, default 95% для MAXIMUM)

**Архитектурные решения**:
- Embedding clustering — основной сигнал (как в старом проекте)
- Peer review — дополнительный сигнал (из LLM Council), опциональный (дорогой по токенам)
- Confidence — вес при голосовании (из ReConcile), почти бесплатный (одно число в ответе)
- Layered aggregation (MoA) — НЕ берём в Phase 6 (слишком дорого, можно добавить позже)

**Audit gate**: Gate 6 — consensus accuracy vs manual assessment на 20 тестовых вопросах. Сравнить: (a) только clustering, (b) clustering + confidence, (c) clustering + peer review.

**Зависимости**: Mistral API key для embeddings, API adapter для cross-validation.

**Оценка**: 4-5 дней (расширено из-за peer review + confidence).

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

### Phase 9: Reliability Levels & Execution Patterns (приоритет HIGH)

**Цель**: Режимы QUICK/STANDARD/HIGH/MAXIMUM + именованные паттерны (SONAR, SINGLE, DUAL, FIVE_MODELS, CONSENSUS).

**Deliverables**:
- [ ] `core/reliability.py` — ReliabilityLevel enum + ReliabilityConfig dataclass
- [ ] QUICK: 1 execution + fact check (Fact Verifier role)
- [ ] STANDARD: 2 executions + comparison (Judge role) + synthesis (Synthesizer role)
- [ ] HIGH: 3 executions + full verification + devil's advocate + synthesis
- [ ] MAXIMUM: iterative consensus loop до порога (Phase 6) + all roles
- [ ] `core/patterns.py` — ExecutionPattern enum:
  - SONAR: 1 model (Sonar), no reasoning, max speed
  - SINGLE: 1 model with reasoning
  - DUAL: 2 models, both answers returned for comparison
  - FIVE_MODELS: all models, answers returned as-is
  - FIVE_MODELS_COMPARE: all models + Judge analyzes differences
  - CONSENSUS: embedding clustering + cross-validation
  - MAXIMUM: CONSENSUS + iterative loop + all roles
- [ ] API: `reliability_level` и/или `pattern` параметр в OrchestrateRequest
- [ ] Маппинг: reliability level → pattern → набор ролей + число моделей + consensus threshold + peer_review enabled
- [ ] Decomposition integration: сложные задачи (Phase 8) автоматически decompose на reliability ≥ HIGH

**Зависимости**: Phase 6 (consensus), Phase 7 (roles), Phase 8 (decomposition).

**Оценка**: 3-4 дня (расширено из-за patterns).

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
| Gate 6 | После Phase 6 (consensus) | Consensus accuracy на 20 вопросах: (a) clustering only, (b) +confidence, (c) +peer review. Сравнить с manual assessment |
| Gate 7 | После Phase 7 (roles) | Fact Verifier catch rate на 10 синтетических галлюцинациях. Devil's Advocate false positive rate |
| Gate 8 | После Phase 8 (decomposition) | Декомпозиция на 10 сложных и 10 простых задачах. Простые НЕ должны decompose |
| Gate 9 | После Phase 9 (reliability+patterns) | End-to-end: MAXIMUM на 5 спорных + 5 фактических вопросах. QUICK vs SINGLE — latency comparison |
| Gate 10 | После Phase 10 (analytics) | Adaptive selector outperforms random model selection на historical data (>10% improvement) |

---

## 5. Приоритизация

```
Phase 6 (Consensus + Peer Review)  ████████████████  CRITICAL — core value proposition
Phase 7 (Roles)                    ████████████      HIGH — verification quality
Phase 8 (Decomposition)            ████████████      HIGH — complex task support
Phase 9 (Reliability + Patterns)   ████████████      HIGH — ties everything together
Phase 10 (Analytics)               ████████          MEDIUM — optimization
Phase 11 (Account Pool)            ████████          MEDIUM — operational reliability
Phase 12 (Child Projects)          ████              LOW — incremental
```

Суммарная оценка: **16-22 дня** при фокусированной работе (1-2 агента).

### Зависимости между фазами

```
Phase 6 (Consensus) ──┐
Phase 7 (Roles) ──────┼──→ Phase 9 (Reliability + Patterns)
Phase 8 (Decomposition)┘

Phase 6 ──→ Phase 10 (Analytics needs consensus scores)
Phase 9 ──→ Phase 11 (Account Pool needs patterns for concurrent execution)
Phase 11 ──→ Phase 12 (Child projects need stable API)

Параллельно:
- Phase 6 и Phase 7 можно делать одновременно
- Phase 8 можно начинать параллельно с Phase 7
- Phase 10 и Phase 11 можно делать одновременно (после Phase 9)
```

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
