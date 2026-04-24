# Inventory of Both Orchestrators
Date: 2026-04-23
Status: inventory complete
GraceKelly HEAD: `11c3116163a0b615f540d4e3cb0c442bfddfa83e`
Perplexity_Orchestrator2 root: `D:/Perplexity_Orchestrator2` (git HEAD `88d5e2d68d01c60978ad13da2353bf64a3ddd808`)

## 1. HTTP endpoints

### GraceKelly

| Method | Path | Handler file:line | Summary (1 строка) |
|---|---|---|---|
| GET | /api/v1/analytics | api/routes/analytics.py:45 | Model performance analytics |
| POST | /api/v1/batch | api/routes/batch.py:64 | Execute multiple prompts in parallel |
| POST | /api/v1/compare | api/routes/compare.py:63 | Compare answers from multiple models |
| POST | /api/v1/consensus | api/routes/consensus.py:67 | Run iterative consensus V1 |
| POST | /api/v1/debate | api/routes/debate.py:60 | Run a Devil's Advocate debate round |
| GET | /health | api/routes/health.py:317 | health |
| GET | /healthz/live | api/routes/health.py:375 | liveness |
| GET | /healthz/ready | api/routes/health.py:380 | readiness_probe |
| GET | /api/v1/readiness | api/routes/health.py:393 | readiness |
| GET | /metrics | api/routes/health.py:416 | metrics |
| GET | /api/v1/health/detailed | api/routes/health_detailed.py:43 | Detailed adapter and embeddings health |
| GET | /api/v1/models | api/routes/models.py:177 | List all registered models |
| POST | /api/v1/models/refresh | api/routes/models.py:202 | Refresh model catalog |
| POST | /api/v1/orchestrate | api/routes/orchestrate.py:251 | Submit a prompt for orchestrated execution |
| POST | /api/v1/orchestrate/upload | api/routes/orchestrate.py:399 | Submit a prompt with file uploads for orchestrated execution |
| GET | /api/v1/tasks | api/routes/orchestrate.py:607 | List recent tasks |
| GET | /api/v1/tasks/{task_id} | api/routes/orchestrate.py:680 | Get full task detail |
| GET | /api/v1/tasks/{task_id}/export | api/routes/orchestrate.py:728 | Export task as Markdown |
| POST | /api/v1/tasks/{task_id}/retry | api/routes/orchestrate.py:760 | Retry a failed or cancelled task |
| POST | /api/v1/pipeline | api/routes/pipeline.py:65 | Execute a reliability-level pipeline |
| POST | /api/v1/smart | api/routes/smart.py:73 | Auto-routing smart execution |
| POST | /api/v1/smart/v2 | api/routes/smart_v2.py:82 | Auto-routing smart execution with Consensus V2 |
| POST | /api/v1/orchestrate/stream | api/routes/stream.py:128 | orchestrate_stream |

### Perplexity_Orchestrator2

| Method | Path | Handler file:line | Summary (1 строка) |
|---|---|---|---|
| GET | /accounts | api/routes/accounts.py:41 | Get all accounts with their status. |
| GET | /accounts/{account_id} | api/routes/accounts.py:72 | Get single account details. |
| GET | /accounts/needing-login | api/routes/accounts.py:90 | Get accounts that need manual login (no session). |
| GET | /api/analytics/overview | api/routes/analytics.py:30 | Overview: total queries, queries 24h, success rate, avg duration, |
| GET | /api/analytics/models | api/routes/analytics.py:107 | Model performance from model_stats table. |
| GET | /api/analytics/accounts | api/routes/analytics.py:154 | Account health from accounts table. |
| GET | /api/analytics/trends | api/routes/analytics.py:208 | Daily trends: queries + avg duration. |
| POST | /api/conversation/create | api/routes/conversation.py:28 | Create a new conversation. |
| GET | /api/conversation/{conv_id} | api/routes/conversation.py:38 | Get conversation details. |
| GET | /api/conversation/{conv_id}/messages | api/routes/conversation.py:56 | Get conversation messages. |
| POST | /api/conversation/{conv_id}/answer | api/routes/conversation.py:71 | Submit an answer to a pending question. |
| GET | /api/debate/latest | api/routes/debate.py:19 | Get the latest debate data. |
| GET | /api/debate/health | api/routes/debate.py:54 | Check if debate data is available and when it was last updated. |
| POST | /api/english/respond | api/routes/english.py:116 | Get natural AI response for conversation. |
| POST | /api/english/analyze | api/routes/english.py:143 | Analyze user responses via Mistral. |
| POST | /api/gk/orchestrate | api/routes/gk_orchestrate.py:73 | GraceKelly orchestration endpoint. |
| GET | /api/gk/patterns | api/routes/gk_orchestrate.py:239 | List available orchestration patterns. |
| GET | /health | api/routes/health.py:11 | Health check endpoint. |
| GET | /health/db | api/routes/health.py:43 | Database health check with migration alerts. |
| GET | /api/interview/levels | api/routes/interview.py:133 | get_levels |
| POST | /api/interview/start | api/routes/interview.py:138 | start_session |
| GET | /api/interview/status/{session_id} | api/routes/interview.py:164 | get_status |
| GET | /api/interview/question/{session_id}/{index} | api/routes/interview.py:179 | get_question |
| POST | /api/interview/evaluate | api/routes/interview.py:196 | evaluate |
| GET | /api/interview/summary/{session_id} | api/routes/interview.py:220 | get_summary |
| POST | /orchestrate | api/routes/orchestrate.py:426 | Start an orchestration task. |
| GET | /status/{task_id} | api/routes/orchestrate.py:465 | Get status of an orchestration task. |
| GET | /tasks | api/routes/orchestrate.py:485 | List all tasks (for debugging). |
| GET | /stats/models | api/routes/stats.py:11 | Получить статистику по моделям. |
| GET | /stats/requests | api/routes/stats.py:30 | Получить последние запросы. |
| GET | /stats/summary | api/routes/stats.py:44 | Получить общую статистику. |
| POST | /api/tasks/complex | api/routes/tasks.py:50 | Create and decompose a complex task. |
| POST | /api/tasks/{task_id}/execute | api/routes/tasks.py:192 | Execute a complex task. |
| POST | /api/tasks/{task_id}/resume | api/routes/tasks.py:226 | Resume execution of an interrupted task. |
| GET | /api/tasks/{task_id} | api/routes/tasks.py:259 | Get status of a complex task. |
| GET | /api/tasks/{task_id}/result | api/routes/tasks.py:286 | Get the final result of a completed task. |
| GET | /api/tasks/ | api/routes/tasks.py:312 | List all complex tasks. |
| DELETE | /api/tasks/{task_id} | api/routes/tasks.py:321 | Delete a task. |
| GET | /api/threads | api/routes/threads.py:92 | Get all threads ordered by most recently updated. |
| POST | /api/threads | api/routes/threads.py:105 | Create a new thread. |
| GET | /api/threads/{thread_id} | api/routes/threads.py:131 | Get a thread with all its queries. |
| PATCH | /api/threads/{thread_id} | api/routes/threads.py:155 | Update a thread's title. |
| DELETE | /api/threads/{thread_id} | api/routes/threads.py:180 | Delete a thread and all its queries. |
| POST | /api/threads/{thread_id}/queries | api/routes/threads.py:201 | Add a query to a thread. |
| GET | /api/webpage/presets | api/routes/webpage.py:109 | Return all presets: palettes, fonts, sections, chart types, etc. |
| POST | /api/webpage/generate | api/routes/webpage.py:115 | Generate HTML page from config. Pure Python, no LLM, <100ms. |
| GET | /api/webpage/preview/{session_id} | api/routes/webpage.py:144 | Serve generated HTML for iframe preview. |
| GET | /api/webpage/download/{session_id} | api/routes/webpage.py:154 | Download generated HTML file. |
| POST | /api/webpage/ai-suggest | api/routes/webpage.py:167 | AI design advisor: suggest palette, fonts, layout, sections for a topic. |
| POST | /api/webpage/ai-content | api/routes/webpage.py:205 | Generate text content for a specific field using AI. |
| POST | /api/webpage/ai-chart | api/routes/webpage.py:241 | Analyze CSV data and suggest best chart type, title, and axis labels. |

## 2. Execution patterns / modes

### GraceKelly

| Pattern name | Implementation file:line | Caller entrypoints | Purpose (1 строка) |
|---|---|---|---|
| sonar | core/patterns.py:33 | /api/v1/smart, /api/v1/smart/v2 (`pattern=sonar`) | Single Sonar model, no reasoning. |
| single | core/patterns.py:44 | /api/v1/smart, /api/v1/smart/v2, /api/v1/pipeline (`quick`) | Single model with reasoning enabled. |
| dual | core/patterns.py:55 | /api/v1/smart, /api/v1/smart/v2, /api/v1/pipeline (`standard`) | Two models, both answers returned for comparison. |
| five_models | core/patterns.py:66 | /api/v1/smart, /api/v1/smart/v2 (`pattern=five_models`) | All models, answers returned as-is. |
| five_models_compare | core/patterns.py:77 | /api/v1/smart, /api/v1/smart/v2 (`pattern=five_models_compare`) | All models, then Judge role analyzes differences. |
| consensus | core/patterns.py:88 | /api/v1/consensus, /api/v1/smart, /api/v1/smart/v2 | Three models with embedding-based consensus clustering. |
| maximum | core/patterns.py:99 | /api/v1/smart, /api/v1/smart/v2, /api/v1/pipeline (`maximum`) | All models, iterative consensus loop until threshold. |
| quick | core/reliability.py:31 | /api/v1/pipeline, /api/v1/smart, /api/v1/smart/v2 | Single model with fact verification. |
| standard | core/reliability.py:45 | /api/v1/pipeline, /api/v1/smart, /api/v1/smart/v2 | Two models with comparison and synthesis. |
| high | core/reliability.py:59 | /api/v1/pipeline, /api/v1/smart, /api/v1/smart/v2 | Three+ models with consensus, devil's advocate, and decomposition flags. |
| decomposed | core/decomposition.py:61 | /api/v1/orchestrate (`decompose=true`), /api/v1/smart, /api/v1/smart/v2 | Split a complex prompt into subtasks and synthesize the sub-results. |
| role-based | core/role_executor.py:16 | /api/v1/smart, /api/v1/smart/v2 | Execute verifier/judge/synthesizer role prompts around an answer. |
| consensus_v2 | core/consensus_v2.py:102 | /api/v1/smart/v2 | HAC clustering with adaptive params, debate rounds, confidence scoring, and dissent extraction. |
| multi_model | core/multi_model.py:28 | /api/v1/pipeline (`multi_model=true`) | Fan out one prompt across all configured API providers. |

### Perplexity_Orchestrator2

| Pattern name | Implementation file:line | Caller entrypoints | Purpose (1 строка) |
|---|---|---|---|
| best | api/routes/gk_models.py:15 | /api/gk/orchestrate -> gk_decomposition._dispatch_pattern | Single `Best` model without reasoning. |
| sonar | api/routes/gk_models.py:16 | /api/gk/orchestrate -> gk_decomposition._dispatch_pattern | Single Sonar browser query. |
| single | api/routes/gk_models.py:17 | /api/gk/orchestrate -> gk_decomposition._dispatch_pattern | Single explicit model with reasoning toggle. |
| dual | api/routes/gk_models.py:18 | /api/gk/orchestrate -> gk_decomposition._dispatch_pattern | Two-model comparison with analyzer call. |
| consensus | api/routes/gk_models.py:19 | /api/gk/orchestrate -> gk_decomposition._dispatch_pattern | High-reliability consensus flow via the legacy orchestrator. |
| maximum | api/routes/gk_models.py:20 | /api/gk/orchestrate -> gk_decomposition._dispatch_pattern | Iterative consensus flow until the configured threshold is reached. |
| five_models | api/routes/gk_models.py:21 | /api/gk/orchestrate -> gk_decomposition._dispatch_pattern | Raw multi-model fan-out without consensus analysis. |
| five_models_compare | api/routes/gk_models.py:22 | /api/gk/orchestrate -> gk_decomposition._dispatch_pattern | Five-model comparison plus structured analyzer output. |
| quick | orchestrator/run_modes.py:17 | /orchestrate, HighReliabilityOrchestrator.dispatch, InteractiveMixin.run_interactive | Planner + one executor + fact verification. |
| standard | orchestrator/run_modes.py:77 | /orchestrate, HighReliabilityOrchestrator.dispatch, InteractiveMixin.run_interactive | Two executors with comparison, verification, synthesis, and judgement. |
| high | orchestrator/run_modes.py:205 | /orchestrate, HighReliabilityOrchestrator.dispatch, InteractiveMixin.run_interactive | Three executors plus full verification suite and devil's advocate. |
| maximum_legacy | orchestrator/run_modes.py:353 | /orchestrate, HighReliabilityOrchestrator.dispatch | Repeat the `high` flow until the consensus score or iteration cap is hit. |
| consensus_based | orchestrator/run_modes.py:397 | HighReliabilityOrchestrator.run_with_consensus, gk_patterns.run_consensus, gk_patterns.run_maximum | 4-model x 3-prompt sampling loop with embeddings clustering and synthesis. |
| gk_decomposed | api/routes/gk_decomposition.py:223 | /api/gk/orchestrate | Run the chosen GK pattern per subtask, then synthesize with Claude. |
| legacy_decomposed | orchestrator/orchestrator.py:336 | HighReliabilityOrchestrator.dispatch, /orchestrate | Run subtasks through the reliability pipeline, then synthesize them. |
| FOUR_OPINIONS | api/routes/orchestrate.py:318 | /orchestrate (`level=FOUR_OPINIONS`) | Return raw responses from configured models without synthesis. |
| INTERSECTIONS | api/routes/orchestrate.py:343 | /orchestrate (`level=INTERSECTIONS`) | Compute pairwise agreements/disagreements over model responses. |
| interactive | orchestrator/interactive.py:14 | conversation manager flows | Send progress updates and assistant messages during orchestration. |
| coding | orchestrator/coding.py:14 | MCP coding-task flows | Generate code, apply files, run tests, and optionally save with git. |

## 3. Model catalog

### GraceKelly

| Model id | Display label | Adapter kind (browser / api / embeddings) | Provider | Source file:line |
|---|---|---|---|---|
| gpt-5-4-api | GPT-5.4 API | api | openai | core/models.py:49 |
| claude-sonnet-4-6-api | Claude Sonnet 4.6 API | api | anthropic | core/models.py:61 |
| best | Best | browser | perplexity | core/models.py:37 |
| sonar | Sonar | browser | perplexity | core/models.py:38 |
| claude-sonnet-4-6 | Claude Sonnet 4.6 | browser | perplexity | core/models.py:39 |
| gpt-5-4 | GPT-5.4 | browser | perplexity | core/models.py:40 |
| gemini-3-1-pro | Gemini 3.1 Pro | browser | perplexity | core/models.py:41 |
| kimi-k2-5 | Kimi K2.5 | browser | perplexity | core/models.py:42 |
| claude-opus-4-6 | Claude Opus 4.6 | browser | perplexity | core/models.py:43 |
| max | Max | browser | perplexity | core/models.py:44 |
| nemotron-3-super | Nemotron 3 Super | browser | perplexity | core/models.py:45 |
| mistral-embed | mistral-embed | embeddings | mistral | core/embeddings.py:10 |

### Perplexity_Orchestrator2

| Model id | Display label | Adapter kind (browser / api / embeddings) | Provider | Source file:line |
|---|---|---|---|---|
| gpt | GPT-5.4 | browser | perplexity | config/models.py:13 |
| claude | Claude Opus 4.7 | browser | perplexity | config/models.py:14 |
| gemini | Gemini 3.1 Pro | browser | perplexity | config/models.py:15 |
| kimi | Kimi K2.5 | browser | perplexity | config/models.py:16 |
| grok | Grok 4.1 | browser | perplexity | config/models.py:17 |
| sonar | Sonar | browser | perplexity | config/models.py:18 |
| best | Best | browser | perplexity | config/models.py:19 |
| mistral-embed | mistral-embed | embeddings | mistral | orchestrator/mistral_embeddings.py:17 |

## 4. Adapters / providers

### GraceKelly

| Adapter class | File:line | Backend (browser / api / embeddings) | Models served |
|---|---|---|---|
| OpenAICompatibleApiAdapter | adapters/api/openai_compat.py:6 | api | gpt-5-4-api |
| AnthropicApiAdapter | adapters/api/anthropic.py:10 | api | claude-sonnet-4-6-api |
| PerplexityBrowserAdapter | adapters/browser/perplexity.py:35 | browser | best, sonar, claude-sonnet-4-6, gpt-5-4, gemini-3-1-pro, kimi-k2-5, claude-opus-4-6, max, nemotron-3-super |
| EmbeddingsClient | core/embeddings.py:10 | embeddings | mistral-embed |

### Perplexity_Orchestrator2

| Adapter class | File:line | Backend (browser / api / embeddings) | Models served |
|---|---|---|---|
| BrowserWorker (imported) | api/routes/orchestrate.py:13 | browser | gpt, claude, gemini, kimi, grok, sonar, best |
| OrchestratorAdapter (imported) | api/routes/gk_patterns.py:15 | browser | BrowserWorker-backed query bridge for GK consensus/maximum flows |
| MistralEmbeddings | orchestrator/mistral_embeddings.py:17 | embeddings | mistral-embed |

## 5. External services & SDKs

### GraceKelly

- Perplexity web UI — main.py:134 — primary browser-backed execution path via `PerplexityBrowserAdapter`.
- Playwright — main.py:115 — browser automation backend for live Perplexity sessions and model-catalog refresh.
- OpenAI API — main.py:362 — OpenAI-compatible adapter registration for `gpt-5-4-api`.
- Anthropic API — main.py:370 — Anthropic adapter registration for `claude-sonnet-4-6-api`.
- Mistral Embeddings API — main.py:405 — embeddings client initialization for consensus and clustering.
- PostgreSQL — main.py:95 — optional task repository backend and model-catalog snapshot store.
- Redis — main.py:419 — optional rate-limit backend.
- Sentry — main.py:414 — FastAPI error reporting setup.
- OpenTelemetry OTLP — main.py:329 — telemetry export setup.

### Perplexity_Orchestrator2

- Perplexity web UI — api/routes/orchestrate.py:145 — `BrowserWorker` submits live queries to Perplexity models.
- Playwright — config/settings.py:15 — headless/browser runtime toggle consumed by browser-worker startup.
- Mistral Chat Completions API — api/routes/english.py:171 — direct conversation and response-analysis calls with `mistral-small-latest`.
- Mistral Embeddings API — orchestrator/mistral_embeddings.py:22 — embeddings for consensus clustering and pairwise similarity.
- SQLite (`data/orchestrator.db`) — api/routes/analytics.py:16 — dashboard/analytics storage for accounts, requests, model stats, and queries.
- Telegram Bot API — api/routes/orchestrate.py:122 — optional result mirroring via `telegram_bot.bot`.
- Email SMTP / yagmail — config/settings.py:68 — sender/recipient credentials exposed for email forwarding features.

## 6. Environment variables

### GraceKelly

| Var name | Consumed at file:line | Type (str/bool/int/...) | Default | Required? |
|---|---|---|---|---|
| GRACEKELLY_ENV | config.py:138 | str | development | No |
| GRACEKELLY_HOST | config.py:139 | str | 127.0.0.1 | No |
| GRACEKELLY_PORT | config.py:140 | int | 8011 | No |
| GRACEKELLY_LOG_LEVEL | config.py:141 | str | INFO | No |
| GRACEKELLY_API_KEY | config.py:142 | optional str | None | No |
| GRACEKELLY_STORAGE_BACKEND | config.py:143 | str | memory | No |
| GRACEKELLY_POSTGRES_DSN | config.py:144 | optional str | None | Conditional (postgres backend) |
| GRACEKELLY_POSTGRES_CONNECT_TIMEOUT_SECONDS | config.py:145 | int | 5 | No |
| GRACEKELLY_POSTGRES_POOL_ENABLED | config.py:146 | bool | false | No |
| GRACEKELLY_POSTGRES_POOL_MIN_SIZE | config.py:147 | int | 1 | No |
| GRACEKELLY_POSTGRES_POOL_MAX_SIZE | config.py:148 | int | 5 | No |
| GRACEKELLY_EXECUTION_PROFILE | config.py:149 | str | dry-run | No |
| GRACEKELLY_MISTRAL_API_KEY | config.py:150 | optional str | None | No |
| GRACEKELLY_MISTRAL_BASE_URL | config.py:151 | str | https://api.mistral.ai/v1 | No |
| GRACEKELLY_MISTRAL_TIMEOUT_SECONDS | config.py:152 | float | 30 | No |
| GRACEKELLY_MISTRAL_MAX_RETRIES | config.py:153 | int | 0 | No |
| GRACEKELLY_MISTRAL_RETRY_BACKOFF_SECONDS | config.py:154 | float | 1.0 | No |
| GRACEKELLY_OPENAI_API_KEY | config.py:155 | optional str | None | No |
| GRACEKELLY_OPENAI_BASE_URL | config.py:156 | str | https://api.openai.com/v1 | No |
| GRACEKELLY_OPENAI_TIMEOUT_SECONDS | config.py:157 | float | 60 | No |
| GRACEKELLY_OPENAI_MAX_RETRIES | config.py:158 | int | 0 | No |
| GRACEKELLY_OPENAI_RETRY_BACKOFF_SECONDS | config.py:159 | float | 1.0 | No |
| GRACEKELLY_ANTHROPIC_API_KEY | config.py:160 | optional str | None | No |
| GRACEKELLY_ANTHROPIC_BASE_URL | config.py:161 | str | https://api.anthropic.com | No |
| GRACEKELLY_ANTHROPIC_TIMEOUT_SECONDS | config.py:162 | float | 120 | No |
| GRACEKELLY_ANTHROPIC_MAX_RETRIES | config.py:163 | int | 0 | No |
| GRACEKELLY_ANTHROPIC_RETRY_BACKOFF_SECONDS | config.py:164 | float | 1.0 | No |
| GRACEKELLY_BROWSER_ENABLED | config.py:165 | bool | false | No |
| GRACEKELLY_BROWSER_AUTOMATION_BACKEND | config.py:166 | str | null | No |
| GRACEKELLY_BROWSER_PROFILE_DIR | config.py:167 | optional str | None | No |
| GRACEKELLY_BROWSER_BASE_URL | config.py:168 | str | https://www.perplexity.ai | No |
| GRACEKELLY_BROWSER_PLAYWRIGHT_CHANNEL | config.py:169 | str | chrome | No |
| GRACEKELLY_BROWSER_PLAYWRIGHT_HEADLESS | config.py:170 | bool | false | No |
| GRACEKELLY_BROWSER_CALL_TIMEOUT_SECONDS | config.py:172 | int | 120 | No |
| GRACEKELLY_MAX_BROWSER_SUBMITS_PER_TASK | config.py:173 | optional int | None | No |
| GRACEKELLY_MAX_BROWSER_SUBMITS_PER_HOUR | config.py:174 | optional int | None | No |
| GRACEKELLY_BROWSER_CIRCUIT_BREAKER_ENABLED | config.py:175 | bool | true | No |
| GRACEKELLY_BROWSER_CIRCUIT_BREAKER_FAILURE_THRESHOLD | config.py:180 | int | 3 | No |
| GRACEKELLY_BROWSER_CIRCUIT_BREAKER_COOLDOWN_SECONDS | config.py:183 | int | 60 | No |
| GRACEKELLY_BROWSER_SCRIPTED_LOGGED_IN | config.py:186 | bool | true | No |
| GRACEKELLY_BROWSER_SCRIPTED_MODEL_LABEL | config.py:191 | optional str | None | No |
| GRACEKELLY_BROWSER_SCRIPTED_OUTPUT_TEXT | config.py:192 | str | scripted browser result | No |
| GRACEKELLY_BROWSER_SCREENSHOTS_DIR | config.py:196 | optional str | None | No |
| GRACEKELLY_SENTRY_DSN | config.py:197 | optional str | None | No |
| GRACEKELLY_SENTRY_ENVIRONMENT | config.py:198 | str | production | No |
| GRACEKELLY_OTEL_ENDPOINT | config.py:199 | optional str | None | No |
| GRACEKELLY_OTEL_SERVICE_NAME | config.py:200 | str | gracekelly | No |
| GRACEKELLY_REDIS_URL | config.py:201 | optional str | None | No |
| GRACEKELLY_RATE_LIMIT_RPM | config.py:202 | int | 60 | No |
| GRACEKELLY_RATE_LIMIT_BURST | config.py:203 | int | 10 | No |
| GRACEKELLY_ORCHESTRATE_TIMEOUT_SECONDS | config.py:204 | optional float | None (0 disables) | No |
| GRACEKELLY_ENABLE_MODEL_FALLBACK | config.py:205 | bool | false | No |
| GRACEKELLY_CONTEXT_WINDOW_TURNS | config.py:206 | int | 20 | No |
| GRACEKELLY_MAX_CONTEXT_CHARS | config.py:207 | int | 50000 | No |
| GRACEKELLY_HEALTH_EXPOSE_DETAILS | config.py:208 | bool | false | No |

### Perplexity_Orchestrator2

| Var name | Consumed at file:line | Type (str/bool/int/...) | Default | Required? |
|---|---|---|---|---|
| HEADLESS | config/settings.py:15 | bool | false | No |
| MISTRAL_API_KEY | config/settings.py:60 | str | "" | No |
| OPENROUTER_API_KEY | config/settings.py:61 | str | "" | No |
| GROQ_API_KEY | config/settings.py:62 | str | "" | No |
| TELEGRAM_BOT_TOKEN | config/settings.py:65 | str | "" | No |
| EMAIL_SENDER | config/settings.py:68 | str | "" | No |
| EMAIL_PASSWORD | config/settings.py:69 | str | "" | No |
| EMAIL_RECIPIENT | config/settings.py:70 | str | "" | No |

## 7. Python dependencies

### GraceKelly

| Package | Version pin | Purpose (если очевидно из usage, иначе пусто) |
|---|---|---|
| fastapi | >=0.115,<1.0 | HTTP API framework |
| uvicorn[standard] | >=0.30,<1.0 | ASGI server |
| httpx | >=0.27,<1.0 | API HTTP client for adapters |
| python-multipart | >=0.0.9,<1.0 | multipart/form-data uploads |
| python-dotenv | >=1.0 | load `.env` configuration |
| hypothesis [dev] | >=6.100,<7.0 | property-based tests |
| pypdf [dev,pdf] | >=6.10.2,<7.0 | PDF tooling |
| pytest [dev] | >=9.0.3,<10.0 | test runner |
| pytest-cov [dev] | >=5.0,<6.0 | coverage reporting |
| ruff [dev] | >=0.4 | linting |
| mypy [dev] | >=1.10 | type checking |
| psycopg[binary] [postgres] | >=3.2,<4.0 | PostgreSQL driver |
| psycopg_pool [postgres] | >=3.2,<4.0 | PostgreSQL connection pooling |
| playwright [browser] | >=1.56,<2.0 | browser automation |
| sentry-sdk[fastapi] [observability] | >=2.0,<3.0 | error monitoring |
| opentelemetry-sdk [observability] | >=1.25,<2.0 | telemetry SDK |
| opentelemetry-instrumentation-fastapi [observability] | >=0.46b0,<1.0 | FastAPI tracing instrumentation |
| opentelemetry-exporter-otlp-proto-http [observability] | >=1.25,<2.0 | OTLP HTTP export |
| redis[asyncio] [redis] | >=5.0,<6.0 | async Redis rate-limit backend |

### Perplexity_Orchestrator2

| Package | Version pin | Purpose (если очевидно из usage, иначе пусто) |
|---|---|---|
| annotated-doc | ==0.0.4 |  |
| annotated-types | ==0.7.0 |  |
| anyio | ==4.12.1 |  |
| cachetools | ==7.0.0 |  |
| certifi | ==2026.1.4 |  |
| charset-normalizer | ==3.4.4 |  |
| click | ==8.3.1 |  |
| colorama | ==0.4.6 |  |
| cssselect | ==1.4.0 | CSS selector support |
| cssutils | ==2.11.1 | CSS parsing |
| fastapi | ==0.128.0 | HTTP API framework |
| greenlet | ==3.3.0 |  |
| h11 | ==0.16.0 |  |
| httpcore | ==1.0.9 |  |
| httpx | ==0.28.1 | HTTP client for Mistral and other external calls |
| idna | ==3.11 |  |
| joblib | ==1.5.3 |  |
| lxml | ==6.0.2 | HTML/XML processing |
| more-itertools | ==10.8.0 |  |
| numpy | ==2.4.1 | vector math for embeddings/similarity |
| playwright | ==1.57.0 | browser automation |
| python-dotenv | ==1.1.0 | load `.env` configuration |
| premailer | ==3.10.0 | HTML email/style inlining |
| pydantic | ==2.12.5 | request/response models |
| pydantic_core | ==2.41.5 |  |
| pyee | ==13.0.0 |  |
| requests | ==2.32.5 | synchronous HTTP client |
| schedule | ==1.2.2 | scheduled jobs |
| scikit-learn | ==1.8.0 | AgglomerativeClustering for consensus |
| scipy | ==1.17.0 | scientific computing / sklearn support |
| starlette | ==0.50.0 | FastAPI runtime |
| threadpoolctl | ==3.6.0 |  |
| typing-inspection | ==0.4.2 |  |
| typing_extensions | ==4.15.0 |  |
| urllib3 | ==2.6.3 |  |
| uvicorn | ==0.40.0 | ASGI server |
| yagmail | ==0.15.293 | email delivery |
