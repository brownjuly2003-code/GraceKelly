# Phased Roadmap

Last updated: 2026-04-26 (audit + telemetry + recon cron + test-double drift fix landed; tag `v0.1.0-pre-simplify`)

## 2026-04-26 Audit + telemetry + recon cron

Tag `v0.1.0-pre-simplify` cut on `8518785` as a safety net before any
simplification refactor. BCG-style strategic audit `audit_opus_2026-04-26.md`
landed at the repo root: engineering 9/10, strategic fit for personal use
5/10, four options A/B/C/D, recommendation Option B Simplify (-42% src LOC,
-67% test LOC) once 30-day usage telemetry confirms which endpoints are
actually exercised.

- `batch-109/docs` (`3628def`): BCG audit + README "Operating Risks" section
  (Perplexity ToS/Cloudflare risk, Chrome profile lock, UI drift).
- `batch-109/109-1` (`032a94d`): usage telemetry middleware. Opt-in JSONL
  append per HTTP request to `<repo>/logs/usage.jsonl`, gated by
  `GRACEKELLY_USAGE_TELEMETRY_ENABLED`. Wired as the outermost middleware so
  rate-limited and error responses are still recorded. 13 unit tests.
- `batch-109/109-2` (`76a8e26`): selectors weekly recon cron.
  `gracekelly-recon-weekly` console entry, weekly Friday 03:00 Windows
  Task Scheduler XML, install/uninstall bat helpers, structural drift detection
  with `logs/recon-drift.jsonl` + `.workflow/state/perplexity-selectors-drift.flag`.
  8 unit tests.
- `batch-109/closure` (`0799485`): outbox report and `.done` refresh.
- `batch-110` (`b166de8`): fix three pre-existing fails in
  `tests/test_playwright_driver.py` after `ceeb27d` added `timeout=30_000`
  kwarg to two production `page.goto` sites without updating the
  `_FakePage.goto` / `_HomeNavigationPage.goto` test doubles. Surgical
  4-ins/3-del kwarg addition.
- `batch-111` (`df48b41`): fix `install_recon_cron.bat` — schtasks /XML
  rejects UTF-8 ("(1,40): unable to switch the encoding") and requires UTF-16
  LE; pipe between Get-Content and Set-Content was caret-escaped (`^|`)
  which breaks under bash → cmd; failure-branch echo carried `(rc=%RC%).`
  whose closing paren prematurely terminated the if-block. Production-verified
  by registering, running once against live Perplexity, capturing the
  baseline (13 models including Claude Opus 4.7), and re-registering via the
  fixed bat.

Test status after closure: 2661 passed, 0 failed, 6 skipped, 11 subtests
(was 2658 / 3 / 6 before the pre-existing fix). `mypy --strict` 0 errors on
107 source files (added `tools.recon_weekly`). `ruff check src tests scripts`
clean.

Live smoke (2026-04-26 19:46 UTC):
- `gracekelly-recon-weekly` real-Playwright run captured 13 models / 5 home
  buttons / DOM flags into `.workflow/state/perplexity-selectors-baseline.json`.
- Telemetry middleware wrote one JSONL record per request after uvicorn
  restart with `GRACEKELLY_USAGE_TELEMETRY_ENABLED=true`.
- `scripts/ecosystem_smoke.py --skip-rag --skip-agent-toolkit --skip-juhub`:
  V2 `/smart` and `/orchestrate` PASS.

Open question (carried forward, requires data not decision): which of
Options A/B/C/D in `audit_opus_2026-04-26.md` §7 to take. Decision deferred
until ~30 days of `logs/usage.jsonl` data is available (target
~2026-05-26).

## 2026-04-25 Integration closure

- `batch-101-b/c`: Mistral-as-LLM ripped out; Mistral kept for embeddings.
- `batch-102`: `/api/v1/orchestrate` dry-run profile-gate fix.
- `batch-103`: cross-audit plus smoke over 8 sync routes for the dry-run profile-gate (audit doc `docs/audits/2026-04-25-dry-run-gate-audit.md`).
- `batch-104`: integration story documented across README / architecture / runbook / roadmap.
- `batch-105`: `scripts/ecosystem_smoke.py` — single-command health check across V2 + 3 known clients.
- `batch-106`: `scripts/win-autostart/` — Windows Task Scheduler artefacts so V2 boots on user logon (manual `install_autostart.bat` from Admin to enable).
- `batch-107`: `mypy --strict src tests` cleanup — full stack now type-clean (264 source files).
- Integrators verified end-to-end:
  - `RAG_Support_Assistant` (3 PASS / 5 SKIP / 0 FAIL gracekelly_smoke).
  - `agent_toolkit` (66 unit + 10 integration PASS, including live `test_orchestrator_live::test_single_query` against running V2).
  - `juhub` (V2 endpoints, V1 auto-start dropped, Grok removed; landed in `D:\Perplexity_Orchestrator2` HEAD `8ff3886`).
- V1 orchestrator at `D:\Perplexity_Orchestrator2` (`:8001`, `/api/gk/*`) formally deprecated 2026-04-25 — `DEPRECATED.md` in that repo, `SERVERS.md` updated, deprecation banner in `CLAUDE.md`. No client uses V1; code preserved read-only for archeology.

## 2026-04-23 Closure Timeline

Single-day roadmap closure run. All phases now marked complete; gates PASS; deferred items explicitly scoped as trigger-reactive.

- `batch-86`: silent model-mismatch detection via actual_label unverified (`9f2aa5f`)
- `batch-87`: scoped-menu search port from Perplexity_Orchestrator2 (`f430d39`)
- `batch-88`: pattern-equivalence verification vs Orchestrator2 (`48b5a93`)
- `batch-89`: model fallback policy single-shot (`8665875`)
- `batch-90`: browser request budget (`bd8d978`)
- `batch-91`: live smoke harness 5 patterns (`a76b632`)
- `batch-92`: post-Phase-2 comprehensive audit — health 7.6/10 (`5163cb8`)
- `batch-93`: settings injection + roadmap sync (`8803a0c`, `d3e32d6`)
- `batch-94`: coverage blind spot — unhide playwright_driver (`ca3d68b`)
- `batch-95`: mypy override cleanup + fallback logging (`bfebff2`)
- `batch-96`: README + architecture docs sync (`9108343`, `fa36d49`)
- `batch-97`: Gate 2 / Gate 3 self-review + AUTH3/cyrillic/API-hedge closure (`aeaa9bf`)
- `batch-98`: /healthz/ready semantic readiness (`7e3928f`)
- `batch-99`: Phase 13/14 trigger-reactive relabel (`f356bc6`)
- `batch-100`: final docs polish (`a991b1d` — this batch)

- Audit: [docs/audits/2026-04-23-post-phase-2-audit.md](docs/audits/2026-04-23-post-phase-2-audit.md)
- Gate 2: [docs/gates/2026-04-23-gate-2-operational-review.md](docs/gates/2026-04-23-gate-2-operational-review.md)
- Gate 3: [docs/gates/2026-04-23-gate-3-execution-policy-review.md](docs/gates/2026-04-23-gate-3-execution-policy-review.md)
- Plan: [docs/plans/2026-04-23-final-closure.md](docs/plans/2026-04-23-final-closure.md)

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

Review gates (self-review completed 2026-04-23):
- Gate 2 (operational readiness): PASS for single-user local scope — see `docs/gates/2026-04-23-gate-2-operational-review.md`; use `GET /api/v1/readiness` for the full component breakdown.
- Gate 3 (execution-policy): PASS for single-user local scope — see `docs/gates/2026-04-23-gate-3-execution-policy-review.md`.

## Phase 2: Browser worker

Status: complete, live-smoke harness extended to smart/debate/consensus/compare/upload in batch-91

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

Delivered after Phase 2 closing:
- **batch-91 HARNESS-expand-patterns**: live smoke harness covers smart/debate/consensus/compare/upload with pattern-specific evaluation; operator runbook section added (`a76b632`, `b965c3c`)

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

Status: complete

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
- opt-in per-IP rate limiting (`GRACEKELLY_RATE_LIMIT_RPM`)

Delivered after account-pool and retry:
- thread-safe `AccountPool` with LRU selection and configurable cooldown
- task-level retry via `retry_of_task_id` linkage and `POST /api/v1/tasks/{id}/retry`
- migration `0002_add_retry_of_task_id.sql`

Delivered after Phase 4 closing:
- **batch-89 CORE-model-fallback-policy**: `ModelSpec.fallback_model_id` + single-shot `ExecutionRouter` fallback on `AUTH_FAILED` / `PROVIDER_UNAVAILABLE` / `TIMEOUT`; env `GRACEKELLY_ENABLE_MODEL_FALLBACK` default off (`8665875`)
- **batch-90 CORE-request-budget-browser**: `RequestBudgetTracker` with per-task + rolling-hourly caps; browser-only gate; env `GRACEKELLY_MAX_BROWSER_SUBMITS_PER_TASK` / `GRACEKELLY_MAX_BROWSER_SUBMITS_PER_HOUR` default `None` (`bd8d978`)
- **batch-93 CORE-inject-settings-into-router**: `ExecutionRouter` accepts explicit `Settings` via `create_app`, eliminating the module-global config leak (`8803a0c`)

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
- initially shipped a Mistral-compatible adapter; later removed when Mistral was constrained to embeddings-only usage
- OpenAI-compatible adapter
- shared `BaseApiAdapter` with common execute, post, healthcheck, and error handling

Trigger-reactive follow-up (not scheduled):
- expand the API hedge beyond a single OpenAI-compatible model only if browser fragility becomes material under production-like load; this is not a currently open item for the single-user local deployment path

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
- ✅ Health endpoint security: minimal response by default, details opt-in via GRACEKELLY_HEALTH_EXPOSE_DETAILS
- ✅ Startup/shutdown lifecycle closes browser adapters, executors, and PostgreSQL pools cleanly
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

Trigger-reactive follow-up (production/multi-user scope):
These items are not open work for the single-user local deploy. Each activates on its own trigger:
- Async adapters (async httpx / async playwright) — **trigger**: sustained event-loop stalls under concurrent load. Current sync adapters wrapped in `asyncio.to_thread` are sufficient for single-user throughput.
- Redis-backed rate limiting for multi-process deployments — **trigger**: horizontal scale-out beyond one uvicorn worker. In-process limiting is sufficient single-process.
- OpenTelemetry distributed tracing — **trigger**: multi-service topology or collecting perf data across requests. Single-user local has structured logs.
- Error tracking integration (Sentry) — **trigger**: production fleet where operator not the user. Single-user local reads logs directly.
- Load testing framework — **trigger**: SLA-bound deploy or before a material scale change. Not required for local scope.

---

## Phase 14: Quality Excellence

Status: complete

Deliverables:
- ✅ README.md: Quick Start, Configuration table, API table (23 endpoints), Development, Architecture
- ✅ X-Request-ID correlation middleware: echoes client header or generates UUID; propagated in all responses
- ✅ RFC 7807 Problem Details: all 4xx/5xx responses use `{type, title, status, detail}` format
- ✅ API key authentication documented and enforced through `GRACEKELLY_API_KEY` for protected endpoints
- ✅ Kubernetes probes: GET /healthz/live (always 200) and GET /healthz/ready (checks storage, 503 if unavailable)
- ✅ Settings.validate(): fail-fast startup validation (postgres+no DSN, timeout<1s)
- ✅ Event buffering: OrchestratorService._event_buffer (deque maxlen=500) buffers events on storage failure, flushes on next submit
- ✅ Property-based tests: hypothesis invariants for similarity symmetry, clustering bounds, confidence normalization
- ✅ Coverage gap tests: smart_v2, base adapter, pipeline, storage/base
- ✅ Multi-stage Docker build: builder + runtime stages, non-root user, HEALTHCHECK
- ✅ playwright_driver.py excluded from coverage (requires live browser)
- ✅ CI coverage gate raised: 90% → 93%
- ✅ 2355 tests passing, 0 failures, coverage 93.85%

Trigger-reactive follow-up (merged with Phase 13):
- Async adapters (async httpx.AsyncClient) — merged with Phase 13 async-adapter item above (same underlying work, same trigger). `asyncio.to_thread` wrapper remains in place until triggered.

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
- **batch-86 BROWSER-actual-label-unverified-reflects-ui**: unverified `select_model` returns parsed actual UI label (button-text-after or menu-snapshot first line) instead of echoing `provider_model_id`; `_model_matches_expected` now detects silent Sonar-for-Claude swaps (`9f2aa5f`)
- **batch-87 TOOL-extend-recon-with-attrs + RECON-best-alias-live**: `capture_perplexity_recon.py` emits new `recon-03-model-menu-attrs.json` with per-item attributes; live recon bundle captured in `tmp/browser-recon/2026-04-23/` confirms `Best` is a `div[role="menuitemradio"]` inside `[data-radix-popper-content-wrapper]`, shares class patterns with other entries — nested-text-node ambiguity, not duplicate items (`11f4a9a`, `9203f50`)
- **batch-87 BROWSER-scoped-menu-search**: `PlaywrightBrowserAutomation.select_model` now tries menu-scoped option lookup (`model_menu_candidates` → `model_menu_item_selector` role-filter) before falling back to the legacy global `get_by_role/text` path; `model_menu_candidates` extended with `[role="menu"]`; `details["option_lookup_source"]` records which path matched. Pattern ported from `D:/Perplexity_Orchestrator2/browser/model_selection.py:182-240` (`f430d39`)
- **batch-88 VERIFY-scoped-menu-vs-orchestrator2**: scoped-menu-search pattern verified equivalent to `D:/Perplexity_Orchestrator2/browser/model_selection.py:182-240` (production on ~30 Perplexity Pro accounts); multi-match nested-text-node behavior covered by regression tests — Best-alias follow-up closed (`48b5a93`)
- **inline AUTH-settle-unknown-state**: `auth_status` makes a bounded `_wait_for_shell` retry when neither signed-out markers nor the prompt input are visible; unblocks smart auto-decomposition sub-execs that previously hit `[auth_failed]` mid-flight after exec #1 landed. Structured `browser_auth_unknown` diagnostic log added for any remaining logged-out decisions (`66a64a8`)
- **inline RESPONSE-strip-streaming-chrome**: `shell_noise_lines` extended with `Thinking`, `Ask a follow-up`, `Stop response`, `Regenerate`, `Sources`, `Answer` so candidate-text cleanup filters them out (`d0acbd4`)
- **inline SMOKE-live-smart-acceptance**: `scripts/live_smart_smoke.py` reusable harness drives PO2 SPA + captures `/api/v1/smart` response; inline run against a live chrome-profile returned `status=200 model_id=claude-sonnet-4-6 answer_len=990` with a structured EV-markets answer in 49.7s, no `[auth_failed]` or shell-chrome markers (`352c6b8`, `94fd2d9`)
- **inline SMOKE-live-debate-acceptance**: harness extended with `--pattern debate`; live run returned `status=200 model_id=claude-sonnet-4-6 answer_len=3293` with a full initial_position/challenge/defense/improved_response chain on an EV CO2 debate topic, 61.2s (`fc6307f`)
- **inline BROWSER-reset-page-state-between-execs**: `PerplexityBrowserAdapter.execute` now calls `automation.reset_page_state()` (navigates to home via `_navigate_home_for_model_selection`) after `dismiss_popups`, so role-based fan-out / decomposition sub-execs no longer collide on a stale thread URL. Live SMART role-based fan-out proven: three real Perplexity sub-execs (123s/100s/53s, 9429/8962/5102 chars — each distinct), final 8962-char multi-region analysis (`66ddfdb`)

Incidents (deprecated follow-up specs recorded for history, not in Delivered):
- **batch-78 Live UI smoke SMART/DEBATE (first attempt)**: failed — UI did not expose the patterns; superseded by batch-77 + batch-79 work.
- **batch-81 Live SMART on `"best"` alias**: failed — Perplexity UI non-deterministically selected Sonar instead of Best, one run extracted shell chrome text (`"Thinking / Ask a follow-up / Model"`) instead of the answer. Workaround landed in batch-82 (pin to explicit model); the root-cause fix landed later in the batch-87/batch-88 browser adapter work.
- **batch-82 Live SMART with cyrillic prompt**: failed — CX harness' PowerShell pipeline converted the cyrillic prompt to `?` before it reached Playwright. `POST /api/v1/smart` still returned `200` with the expected model_id, confirming the batch-80 backend fix, but the acceptance (meaningful answer) could not be validated.
- **batch-83 Live SMART with UTF-8 harness**: failed — smart auto-decomposition fired three Perplexity calls for the prompt; adapter timeout of 60s per call clipped two of them, the third extracted 2730 chars at 53s. Route-level response was not captured within the harness' outer 180s window.

Closed / Scoped out (2026-04-23):
- **Cyrillic prompts via some harnesses lose encoding** — closed as out-of-scope: the corruption happens on the PowerShell/automation-harness side, not in GraceKelly. See `docs/operator-runbook.md` under `Harness limitations`.
- **AUTH3 persistent session reuse** — closed by design via the batch-69 rationale: `AUTH1` sync mapping, `AUTH2` inline banner recovery, and the dedicated Chrome profile directory already cover the single-user local recovery path. Batch-72/bootstrap already covered profile lifecycle.
