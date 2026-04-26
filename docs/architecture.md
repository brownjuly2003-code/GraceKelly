# Architecture

## Goals

GraceKelly is being rebuilt as a small and explicit orchestration core.
The foundation must stay understandable under failure.

## Current scope

Implemented:
- full API surface: orchestration, task inspection, health, readiness, model catalog, metrics
- auxiliary HTTP surfaces: analytics, detailed health, task export, task retry, and file-upload orchestration
- SSE streaming for single-model execution via `/api/v1/orchestrate/stream`
- canonical model registry with alias normalization
- typed task/step/event contracts with multi-model execution planning
- token counting and cost estimation per step (`input_tokens`, `output_tokens`, `cost_usd`)
- model pricing registry for cost estimation
- bounded browser-submit budgeting for per-task and per-hour quotas
- account-pool primitives and manager for provider cooldown and selection
- session-aware prompt shaping with configurable context-window limits
- dual-backend storage: in-memory (development) and PostgreSQL (durable)
- PostgreSQL operational tooling: schema validation plus JSON export/import snapshots
- execution adapters: dry-run, OpenAI-compatible API, Anthropic API, Perplexity browser (scripted and thin Playwright backends)
- embeddings client: Mistral embeddings for consensus clustering only
- cooperative cancel-on-quorum with per-model timeout, concurrency enforcement, and a minimal browser circuit breaker
- browser adapter lifecycle cleanup that resets idle session state on shutdown and detects stale runtime/session mismatches
- structured key-value logging across orchestrator, browser adapters, API routes, and PostgreSQL degradation paths
- request metrics histograms/counters plus optional OpenTelemetry bootstrap for observability
- optional opt-in usage telemetry middleware appending one JSONL record per HTTP request
  to `<repo>/logs/usage.jsonl` for honest 30-day usage audits before any simplification work
- operator surfaces: recent-task listing with multi-axis filtering, rich task detail with diagnostics
- built-in web UI with single-model, pairwise, five-model, and auto-routing execution patterns
- post-phase audit snapshots preserved under `docs/audits/`; the standalone strategic audit
  `audit_opus_2026-04-26.md` at the repo root scopes simplification options A/B/C/D

Not yet implemented:
- richer retry policies beyond the current deferral
- broader browser catalog refresh if account-tier drift continues
- cross-project integration glue

Excluded by design:
- SQLite

## Module boundaries

- `api.routes`: HTTP contract only - no domain logic, no adapter imports
- `api.routes.stream`: SSE streaming endpoint for real-time execution output
- `api.routes.analytics`: aggregate model performance stats from recent task and step history
- `api.routes.health_detailed`: detailed adapter and embeddings health endpoint
- `core.models`: canonical model catalog and alias resolution
- `core.orchestrator`: use-case orchestration, event building, storage coordination
- `core.contracts`: execution adapter interface, result envelopes, failure taxonomy
- `core.planning`: execution plan construction and request validation
- `core.router`: adapter dispatch, concurrency gate, quorum aggregation
- `core.account_pool`: thread-safe account selection and cooldown tracking
- `core.account_pool_manager`: pool access wrapper for provider-side throttling decisions
- `core.readiness`: component health aggregation across profiles
- `core.concurrency`: thread-safe per-model concurrency gate
- `core.execution_profile`: profile-aware adapter requirement sets
- `core.budget`: per-task and per-hour browser submit budgeting
- `core.embeddings`: Mistral embeddings client used for consensus clustering only
- `core.session_context`: bounded session-history reconstruction for follow-up prompts
- `request_metrics`: in-process HTTP and adapter metrics backing `/metrics`
- `telemetry`: optional OpenTelemetry setup for FastAPI
- `middleware.setup_usage_telemetry`: opt-in JSONL append per request, gated by
  `GRACEKELLY_USAGE_TELEMETRY_ENABLED`; sha256 prompt-hash is recorded only for the
  orchestration POST routes, body itself is not persisted
- `tools.recon_weekly`: weekly Perplexity DOM reconnaissance with structural diff
  against `.workflow/state/perplexity-selectors-baseline.json`; drift writes
  `logs/recon-drift.jsonl` and `.workflow/state/perplexity-selectors-drift.flag`
- `adapters.dry_run`: simulated execution for testing and dry-run mode
- `adapters.api.anthropic`: Anthropic API adapter
- `adapters.api.openai_compat`: OpenAI-compatible API adapter
- `adapters.browser.perplexity`: Perplexity browser adapter (delegates to automation port)
- `adapters.browser.automation`: browser automation port ABC and null implementation
- `adapters.browser.playwright_driver`: thin Playwright browser backend
- `adapters.browser.scripted`: scripted browser backend for testing
- `adapters.browser.selectors`: centralized Perplexity DOM anchors from live recon
- `adapters.browser.session`: browser session state management
- `adapters.browser.policy`: popup, auth, model verification, and submit policies
- `storage.base`: storage contract (TaskRepository ABC)
- `storage.memory`: thread-safe in-memory backend
- `storage.postgres`: PostgreSQL backend with migration tooling

## Architectural decisions

1. PostgreSQL is the first durable backend. SQLite is not part of the target architecture.
2. Multi-model orchestration is a first-class requirement, not a later enhancement.
3. Execution must support two adapter families:
   - browser adapters for UI-routed providers
   - API adapters for provider-backed execution
4. A solo-user web UI is part of the primary operating surface for experimentation and inspection.
5. Provider-specific naming drift must be normalized through the central model registry.
6. Browser execution via Perplexity is the primary adapter. The user's Perplexity Pro subscription
   provides access to multiple frontier models at no additional API cost. API adapters exist as
   optional fallbacks for direct provider access. Mistral is retained only for embeddings in
   consensus clustering, not as an LLM execution backend.
7. Event logging must not be a critical dependency for accepting or executing a task.

## Design rules

1. Every external dependency must sit behind an adapter boundary.
2. Persistence is replaceable. Memory first, PostgreSQL next.
3. Model names are canonicalized once at the edge.
4. Browser execution is the primary path - Perplexity subscription gives access to frontier
   models. API execution is a fallback, using the same orchestration contract.
5. Observability must be append-only and isolated from request execution.

## Known integrators

External clients integrate through the local V2 HTTP API on `http://127.0.0.1:8011`.
Verified clients (all migrated from V1 by 2026-04-25):

- **`RAG_Support_Assistant`** (`D:\RAG_Support_Assistant`) — provider-aware support bot with
  GraceKelly as a fallback LLM provider. Smoke harness `scripts/gracekelly_smoke.py`
  walks 8 steps (healthz, profile, simple ask, tool loop, schema dispatch, streaming,
  metrics, failover).
- **`agent_toolkit`** (`D:\agent_toolkit`) — LangGraph agent building blocks. The
  `OrchestratorChatModel` LangChain adapter dispatches one of six `GKPattern`s
  (SINGLE / SONAR / DUAL / FIVE_MODELS / CONSENSUS / MAXIMUM) to the matching V2
  route (`/orchestrate`, `/compare`, `/consensus`, `/smart` with `reliability_level=high`).
- **`juhub`** (`D:\Perplexity_Orchestrator2\juhub`) — daily AI debate scheduled at 08:30
  via Windows Task Scheduler. `backend/scheduler.py` performs a pre-flight `:8011/healthz/ready`
  check and gracefully skips the run if V2 is not reachable; it does not auto-spawn V2
  on its own.

The legacy V1 orchestrator at `D:\Perplexity_Orchestrator2` (port 8001, endpoints `/api/gk/*`)
is deprecated as of 2026-04-25. See `D:\Perplexity_Orchestrator2\DEPRECATED.md`.

The dry-run profile gate covers all eight sync routes used by external clients
(`/api/v1/smart`, `/smart/v2`, `/orchestrate`, `/consensus`, `/debate`, `/compare`,
`/batch`, `/pipeline`) — verified in `docs/audits/2026-04-25-dry-run-gate-audit.md`.
Mistral remains embeddings-only for consensus clustering and is not an LLM execution backend
(formerly an unintended baggage adapter; ripped out in batches 101-b/c).

## Operations tooling

- `scripts/ecosystem_smoke.py` — single-command health check across V2 + 3 known clients.
  Used as the integrator regression gate.
- `scripts/win-autostart/` — Windows Task Scheduler artefacts to keep V2 always-on under
  user logon, with a `set_profile.bat` toggle for execution profile.
- `scripts/win-autostart/install_recon_cron.bat` — registers a weekly Friday 03:00 task
  `GraceKelly Selectors Recon` that runs `gracekelly-recon-weekly`, captures the live
  Perplexity DOM via Playwright, and diffs it against the stored baseline. Drift surfaces
  in `logs/recon-drift.jsonl` and as `.workflow/state/perplexity-selectors-drift.flag`.
- `docs/audits/2026-04-25-dry-run-gate-audit.md` — per-route audit table proving dry-run
  profile coverage.
- `audit_opus_2026-04-26.md` (repo root) — BCG-style strategic audit. Scores engineering
  9/10 vs strategic fit for personal use 5/10; recommends Option B Simplify (-42% src
  LOC, -67% test LOC) once 30-day usage telemetry confirms which endpoints are actually
  exercised.

## Next steps

1. Improve consensus/debate streaming beyond the current single-model streaming path.
2. Broaden retry policies beyond the current deferral if operational demand appears.
3. Add more models to the pricing registry as providers are added.
