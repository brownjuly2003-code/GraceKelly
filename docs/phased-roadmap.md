# Phased Roadmap

Last updated: 2026-04-22 (Phase 17 auth/chrome-strip inline fixes)

## Phase 0: Clean foundation

Status: complete

Deliverables:
- independent project root
- app factory
- public API contract
- canonical model registry
- memory-backed task repository

## Phase 1: Execution contract

Status: complete

Deliverables:
- adapter interface for prompt execution
- execution result envelope
- failure taxonomy and retry policy contract
- multi-model execution plan contract
- cooperative cancel-on-quorum execution flow
- typed task, step, and event contracts
- model timeout and concurrency hints enforced in runtime
- async route offloading via `asyncio.to_thread`
- thread-safe in-memory repository
- strict step/result cardinality enforcement
- event persistence failure logging

Open review gates (not blocking Phase 1 completion, required before production hardening):
- Gate 2: operational review for readiness semantics
- Gate 3: execution-policy review for defaults and failure handling

## Phase 2: Browser worker

Status: partial, first authenticated live-driver smoke proven

Deliverables:
- isolated browser adapter package
- session lifecycle abstraction
- model selection verification rules
- popup and auth recovery hooks
- scripted browser automation backend
- live Perplexity DOM recon note
- centralized selector module
- thin Playwright-backed `BrowserAutomationPort` implementation
- external Gate 4 boundary review completed in `audit2.md`

Delivered after logging hardening:
- circuit breaker state transition logging (trip/close/half-open/fail-fast)
- browser adapter auth check, execution duration, response source logging
- Playwright session reuse and response extraction diagnostics

Delivered after catalog refresh:
- "Thinking" model added from recon evidence
- "Model" text removed from ready_markers and shell_noise_lines (no longer in Perplexity UI)
- Kimi K2.5 kept in registry with runtime `observed_unavailable` handling

Delivered after the first live-driver smoke:
- concrete browser-driver cleanup on top of the app lifespan hook, including idle-session reset and stale runtime detection

Support in place:
- manual-gated live Playwright smoke test in `tests/test_playwright_live.py`
- dedicated profile bootstrap helper via `gracekelly-create-perplexity-profile`

## Phase 3: Durable state

Status: complete for current scope

Deliverables:
- PostgreSQL backend alongside memory storage
- task event log
- health and integrity checks
- packaged SQL migration and schema-diff tooling
- validation CLI and optional live-PostgreSQL tests

Delivered after migration tooling:
- `gk_schema_migrations` tracking table with ordered application
- `gracekelly-migrate-postgres` CLI with `--dry-run`
- migration status (available/applied/pending) in `schema_report()`

Delivered after pooling:
- optional `psycopg_pool` connection pooling via `GRACEKELLY_POSTGRES_POOL_ENABLED`

Delivered after validation tooling:
- JSON snapshot export/import CLIs for PostgreSQL task, step, and event data

## Phase 4: Reliability controls

Status: partial

Deliverables:
- account pool manager
- model fallback policy
- request budget and concurrency limits
- circuit breakers around adapters
- quorum and merge policy for multi-model execution

Already delivered:
- per-model timeout defaults
- in-process concurrency limits
- minimal browser-adapter circuit breaker behavior with readiness visibility
- execution saturation visibility in health/readiness
- fail-fast plan/result cardinality invariants
- explicit retry-schema deferral tests
- API error response sanitization (no internal detail leakage)
- browser profile-dir path-traversal validation
- opt-in API key authentication (`GRACEKELLY_API_KEY`)
- opt-in per-IP rate limiting (`GRACEKELLY_RATE_LIMIT_PER_MINUTE`)

Delivered after account-pool and retry:
- thread-safe `AccountPool` with LRU selection and configurable cooldown
- task-level retry via `retry_of_task_id` linkage and `POST /api/v1/tasks/{id}/retry`
- migration `0002_add_retry_of_task_id.sql`

## Phase 5: Operations surface

Status: complete

Deliverables:
- metrics endpoint
- task inspection endpoint
- operator runbook
- lightweight admin surface if still justified

Already delivered:
- `/metrics` endpoint backed by existing readiness/runtime state
- `/health` and `/api/v1/readiness`
- operator runbook for the current browser/storage/runtime surfaces
- structured key-value logging across orchestrator, browser, API route, and PostgreSQL degradation paths
- recent-task list with operator filters
- rich `GET /api/v1/tasks/{task_id}` task, step, and event views
- execution saturation and terminal-summary diagnostics

Evaluation outcome:
- admin UI is not justified at this stage — API endpoints, CLI tools, Prometheus /metrics, operator runbook, and structured logging cover all current operator needs without adding frontend build complexity, dependencies, or security surface

## Parallel track: API adapters

Status: consolidated

Deliverables:
- provider API adapter interface implementation
- first low-cost provider integration path
- provider-specific auth and rate-limit handling

Already delivered:
- Mistral-compatible adapter
- OpenAI-compatible adapter
- shared `BaseApiAdapter` with common execute, post, healthcheck, and error handling

Next:
- expand the API hedge beyond a single OpenAI-compatible model if browser fragility proves material

## Phase 6–10: Core smart endpoints and consensus V1

Status: complete

Deliverables:
- Smart endpoint with execution profile resolution
- Consensus V1 engine with majority voting and confidence scoring
- Analytics endpoint with graceful degradation
- Batch endpoint for parallel multi-prompt execution
- Embeddings client integration

## Phase 11: Consensus V2 + Infrastructure Integration

Status: complete

Deliverables:
- Consensus V2 engine: HAC clustering, cluster confidence, cross-pollination, debate round, divergence handling, adaptive parameters
- Full ConsensusExecutorV2 pipeline with peer review reranking and round weighting
- Infrastructure modules: account loader, account pool manager, execution history, round weighting, multi-model executor, peer review reranker
- 4 new endpoints: POST /api/v1/batch, POST /api/v1/pipeline, GET /api/v1/health/detailed, POST /api/v1/smart/v2
- Route inventory smoke test covering all 15 endpoints
- Audit fixes: consensus error sanitization, analytics graceful degradation

## Phase 12: Child Project APIs

Status: complete

Deliverables:
- POST /api/v1/debate — Devil's Advocate debate endpoint with challenge, defense, improved response
- POST /api/v1/compare — multi-model FIVE_MODELS_COMPARE pattern with Judge analysis
- POST /api/v1/batch — already delivered in Phase 11
- Task graph system: core graph, builder (sequential/parallel/fan-out-fan-in/pipeline), executor with topological sort and skip-on-failure

## Phase 13: Production Hardening

Status: complete

Delivered:
- ✅ GitHub Actions CI pipeline (Python 3.11/3.12, import check, coverage reporting, pip-audit)
- ✅ Dockerfile: Python 3.12-slim, non-root user, HEALTHCHECK
- ✅ docker-compose (standalone + postgres-backed configurations)
- ✅ .dockerignore
- ✅ Security audit: no hardcoded keys, all 44 core modules importable, no silent exception swallowing in routes
- ✅ mypy strict mode: 0 errors across all 98 source files; CI enforces --strict on every push
- ✅ Typed AppState, typed route helpers, cast() for all json.loads returns, typed middleware
- ✅ CORS support (configurable origins, credentials, CORS middleware)
- ✅ Health endpoint security: minimal response by default, details opt-in via GRACEKELLY_HEALTH_EXPOSE_DETAILS
- ✅ Graceful shutdown with configurable drain period (GRACEKELLY_GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS)
- ✅ Orchestrate request timeout: returns HTTP 504 on breach (GRACEKELLY_ORCHESTRATE_TIMEOUT_SECONDS)
- ✅ Analytics N+1 query fix: batch step loading via list_steps_batch
- ✅ Event pagination for GET /tasks/{id}: events_limit / events_offset query params
- ✅ httpx migration for API adapter (replaces requests)
- ✅ Prometheus latency histogram: gracekelly_http_request_duration_seconds (buckets, sum, count)
- ✅ SAST with bandit added to CI pipeline (|| true); nosec annotations for false positives
- ✅ dry_run default changed from True to False (HIGH audit finding — prevents silent DryRunAdapter in production)
- ✅ AnthropicApiAdapter._post_json signature aligned with BaseApiAdapter (extra_headers param)
- ✅ app_state.py: added test coverage
- ✅ 2309 tests passing (from 2229 start of session)

Remaining:
- Async adapters (async httpx / async playwright) — sync adapters currently block the event loop
- Redis-backed rate limiting for multi-process deployments
- OpenTelemetry distributed tracing
- Error tracking integration (Sentry)
- Load testing framework

---

## Phase 14: Quality Excellence

Status: complete

Deliverables:
- ✅ README.md: Quick Start, Configuration table, API table (15 endpoints), Development, Architecture
- ✅ X-Request-ID correlation middleware: echoes client header or generates UUID; propagated in all responses
- ✅ RFC 7807 Problem Details: all 4xx/5xx responses use `{type, title, status, detail}` format
- ✅ GRACEKELLY_REQUIRE_AUTH=true strict mode: returns 503 when no API key is configured
- ✅ Kubernetes probes: GET /healthz/live (always 200) and GET /healthz/ready (checks storage, 503 if unavailable)
- ✅ Settings.validate(): fail-fast startup validation (postgres+no DSN, timeout<1s)
- ✅ Event buffering: OrchestratorService._event_buffer (deque maxlen=500) buffers events on storage failure, flushes on next submit
- ✅ Property-based tests: hypothesis invariants for similarity symmetry, clustering bounds, confidence normalization
- ✅ Coverage gap tests: smart_v2, base adapter, pipeline, storage/base
- ✅ Multi-stage Docker build: builder + runtime stages, non-root user, HEALTHCHECK
- ✅ playwright_driver.py excluded from coverage (requires live browser)
- ✅ CI coverage gate raised: 90% → 93%
- ✅ 2355 tests passing, 0 failures, coverage 93.85%

Remaining (deferred):
- Async adapters (async httpx.AsyncClient) — current sync adapters already wrapped in asyncio.to_thread, deferred as low-risk high-complexity

---

## Phase 15: Async adapters, observability, HTML SPA UI

Status: complete

Scope: replace Streamlit frontend with an HTML SPA, finish async adapter work,
plug in optional observability and rate-limiting backends.

Delivered:
- `feat: async adapters` (`4fbfe26`) — `execute_async()` on adapter ABC, `AsyncClient` in `BaseApiAdapter`, routes updated to await
- `feat: Sentry error tracking + Redis rate limiting (optional, env-driven)` (`8fc51fe`)
- `feat: OpenTelemetry tracing (optional, env-driven)` (`ba2ca8d`)
- `feat: model refresh endpoint, modern UI, chat robustness` (`2757daf`)
- `feat: context truncation (3000 chars) + chat error recovery` (`df5bfb4`)
- `fix: browser model routing in stream, chat dry_run toggle, UI cleanup` (`0b632b4`)
- `feat: session chain (20 turns), auto-decomposition, file attachments` (`d03bb58`)
- `fix: 3 smoke-дефекта — dry_run output_text, stream ValueError, extra fields 422` (`316242c`)
- `feat: Playwright image upload, UI file uploader, async tests, live smoke` (`466fc80`)
- `refactor: orchestrator split + session chain + file attachments` (`cf2562d`)
- `feat: HTML SPA UI replaces Streamlit (PO2 design)` (`88b8106`)
- `chore: CI hardening + security dependency upgrades` (`3e0c0cd`)
- `fix: smoke regressions — dry_run propagation, healthz/live, stream task_id` (`f7838b7`)
- `feat: browser profile safety + screenshot debugging` (`9da447e`)

mypy-only hardening batches (mypy tests passing under --strict):
- `8340ba7` refactor: remove hasattr guards + async cleanup (-421 errors)
- `9b6cfe2` fix: mypy tests -190 errors
- `38a7c52` fix: mypy src/ tests/ → 0 errors
- `b1bdb6d` fix: coverage 95.66%→97%+, CI mypy src/ tests/ lockdown

## Phase 16: Browser-backed orchestration hardening

Status: complete (batches 69 through 74)

Scope: close the 500-on-browser-adapter gap, rebuild the PO2 HTML shell, keep
the browser-side model catalog in sync with what Perplexity actually exposes,
and formalise the auth-overlay handling.

Delivered:
- **batch-69 DIAG-orchestrate-500**: map `PermissionError` and adapter timeouts to structured failure on both sync and async routes (`810b4c1`, `f3fc848`)
- **batch-69 UI1-UI3 PO2 rebuild**: PO2 HTML skeleton, styles, chat.js features restored (`c9751d1`, `f7b067b`, `b6c05ca`)
- **batch-69 MODEL-dynamic-catalog**: runtime snapshot replaces the static browser model registry (`e87498c`)
- **batch-70 CLOSE-69**: ledger + cleanup of 69 scope (`745e66f`, `332f20d`, `d95b7d9`, `36fbbc5`, `8cd7603`)
- **AUTH1/AUTH2 + AUTH-FIX1/FIX2/FIX3**: sync returns `HTTP 503 {"code":"model_auth_required"}`, async task captures the same code in `task.error`; inline UI banner with Retry; shared constants and Playwright regression (`8763c19`, `0aa592d`, `f19ed1b`, `ae4f07e`, `4f7ed1a`)
- **batch-72 BOOTSTRAP-onboarding**: dedicated Chrome profile bootstrap helper + onboarding doc; `chrome-profile/` now gitignored (`014493e`, `2bf3bab`)
- **batch-72/73 consolidated**: catalog async lifespan, profile safety validator, logger visibility fix (`67fc496`)
- **batch-73 SMOKE-rerun**: live Perplexity single-pattern smoke returns `200` (`cffa4fc`)
- **batch-74 UI-PO2-parity-rework**: copy PO2 icons + pages + align DOM/CSS/JS (`48710aa`)
- **batch-74 FLAKY-postgres-test-triage**: hypothesis + bisect plan recorded, fix deferred (`412cee4`)
- **chore**: drain timed-out orchestrate submissions so unhandled futures don't leak into unrelated tests (`772ef34`)
- **batch-74 closure + evidence**: workflow done marker refresh, UI parity screenshots, live catalog snapshot (11 models, no Kimi) (`88e1738`, `e1f7185`)

## Phase 17: Live UI smoke and workflow hygiene

Status: closed for smart/debate arc, adapter-timeout follow-up deferred

Scope: validate complex browser scenarios (file upload, decomposition, debate)
against the real Perplexity UI, and keep the `.workflow/` task queue clean.

Delivered:
- **batch-75 FLAKY-postgres-fix**: flaky `test_main_rejects_checksum_mismatch` no longer reproduces on the current tip; full suite runs `2579 passed / 0 failed` twice back-to-back, no skip/xfail/ordering workaround added (`98b8835`)
- **batch-75 INBOX-cleanup**: six processed task specs archived, `.ready` cleared, batch-75 spec moved to `.workflow/done/` (`2b909d6`, `deebc5a`)
- **batch-76 UI-SMOKE-prep + upload**: `/` lives at `http://127.0.0.1:8011/`; live Claude 4.6 single-pattern smoke with attachment returns `200` and the sentinel in `output_text` (not committed — artefacts only)
- **batch-77 UI-MENU-extend**: smart and debate exposed as user-selectable items ("Умный выбор", "Дебаты") in the `Авто` group of the PO2 model menu (`f456067`)
- **batch-77 UI-BROWSER-regressions**: three Playwright regression tests drive the real SPA with mocked `/api/v1/smart`, `/api/v1/debate`, `/api/v1/orchestrate/upload` — no live Perplexity dependency (`063f29b`)
- **batch-79 FIX-ui-contract**: debate/smart items now carry `pinned_model`; `_resolveItem` short-circuit resolves it so `getSelection().model` is never null (`a89ca78`). Mock regressions extended to assert the body carries a non-empty model.
- **batch-79 FIX-env-docs**: README corrected to describe `GRACEKELLY_EXECUTION_PROFILE` as `dry-run` / `api-only` / `hybrid` (prior value `default` was never valid) (`614b181`)
- **batch-80 BACKEND-smart-debate-browser-support**: `/api/v1/smart` and `/api/v1/debate` accept browser-backed models via `state.browser_adapter`; unit tests cover browser-path success + API-path regression (`dd632c7`)
- **batch-80 FLAKE-triage-http-api**: `test_list_tasks_exposes_winning_model_and_short_circuit_summary` stabilised with a deterministic cancellable adapter; three back-to-back full runs + one coverage run green (`5c62065`)
- **batch-82 UI-PIN-claude-sonnet**: smart/debate `pinned_model` switched from the unstable `"best"` Perplexity alias to explicit `"claude-sonnet-4-6"`; mock regressions updated (`1e448e0`)
- **batch-84 BACKEND-unify-browser-adapter**: shared adapter-lookup helper across smart/debate/smart_v2/consensus/compare; `/api/v1/smart/v2`, `/api/v1/consensus`, and `/api/v1/compare` now accept browser-backed models (`e877527`)
- **batch-85 ADAPTER-raise-call-timeout**: default browser adapter per-call timeout raised 60s → 120s with `GRACEKELLY_BROWSER_CALL_TIMEOUT_SECONDS` env override (`43d29b2`)
- **inline AUTH-settle-unknown-state**: `auth_status` makes a bounded `_wait_for_shell` retry when neither signed-out markers nor the prompt input are visible; unblocks smart auto-decomposition sub-execs that previously hit `[auth_failed]` mid-flight after exec #1 landed. Structured `browser_auth_unknown` diagnostic log added for any remaining logged-out decisions (`66a64a8`)
- **inline RESPONSE-strip-streaming-chrome**: `shell_noise_lines` extended with `Thinking`, `Ask a follow-up`, `Stop response`, `Regenerate`, `Sources`, `Answer` so candidate-text cleanup filters them out (`d0acbd4`)

Incidents (deprecated follow-up specs recorded for history, not in Delivered):
- **batch-78 Live UI smoke SMART/DEBATE (first attempt)**: failed — UI did not expose the patterns; superseded by batch-77 + batch-79 work.
- **batch-81 Live SMART on `"best"` alias**: failed — Perplexity UI non-deterministically selected Sonar instead of Best, one run extracted shell chrome text (`"Thinking / Ask a follow-up / Model"`) instead of the answer. Workaround landed in batch-82 (pin to explicit model); root-cause fix in the browser adapter is a Remaining item.
- **batch-82 Live SMART with cyrillic prompt**: failed — CX harness' PowerShell pipeline converted the cyrillic prompt to `?` before it reached Playwright. `POST /api/v1/smart` still returned `200` with the expected model_id, confirming the batch-80 backend fix, but the acceptance (meaningful answer) could not be validated.
- **batch-83 Live SMART with UTF-8 harness**: failed — smart auto-decomposition fired three Perplexity calls for the prompt; adapter timeout of 60s per call clipped two of them, the third extracted 2730 chars at 53s. Route-level response was not captured within the harness' outer 180s window.

Remaining:
- **Live SMART/DEBATE end-to-end acceptance** — unit + mock coverage is green and the three known blockers (adapter timeout, mid-decomposition `[auth_failed]`, streaming-chrome extraction) are fixed in code. A fresh live smoke against a logged-in Perplexity profile is needed to confirm end-to-end behaviour on the real UI.
- **Browser adapter non-deterministic selection for the `"Best"` alias** — Perplexity's auto-router item is not stably picked; the workaround is to pin explicit model ids, but the auto-router path is still visible in the menu and will surface again for any user selecting "Best". DOM recon required.
- **Cyrillic prompts via some harnesses lose encoding** (observed in batch-82) — lives on the automation side, not in GraceKelly, but worth documenting for anyone driving live smokes from PowerShell.
- **AUTH3 persistent session reuse** — still deferred from batch-69; friction is tolerable at the current single-user local scale.
