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
- operator surfaces: recent-task listing with multi-axis filtering, rich task detail with diagnostics
- built-in web UI with single-model, pairwise, five-model, and auto-routing execution patterns
- post-phase audit snapshots preserved under `docs/audits/`

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

External clients integrate through the local V2-compatible HTTP API on `http://127.0.0.1:8011`.
The current verified clients are `RAG_Support_Assistant` and `agent_toolkit`.

The dry-run profile gate is expected to cover all eight sync routes used by external clients:
`/api/v1/smart`, `/api/v1/smart/v2`, `/api/v1/orchestrate`, `/api/v1/consensus`,
`/api/v1/debate`, `/api/v1/compare`, `/api/v1/batch`, and `/api/v1/pipeline`.
Mistral remains embeddings-only for consensus clustering and is not an LLM execution backend.

## Next steps

1. Improve consensus/debate streaming beyond the current single-model streaming path.
2. Broaden retry policies beyond the current deferral if operational demand appears.
3. Add more models to the pricing registry as providers are added.
