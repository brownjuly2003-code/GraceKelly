# Phased Roadmap

Last updated: 2026-03-21

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

Status: complete (core hardening delivered)

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
- Event buffering for storage failures (in-memory retry queue)
