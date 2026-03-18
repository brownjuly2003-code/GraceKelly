# Architecture

## Goals

GraceKelly is being rebuilt as a small and explicit orchestration core.
The foundation must stay understandable under failure.

## Current scope

Implemented:
- full API surface: orchestration, task inspection, health, readiness, model catalog, metrics
- canonical model registry with alias normalization
- typed task/step/event contracts with multi-model execution planning
- dual-backend storage: in-memory (development) and PostgreSQL (durable)
- execution adapters: dry-run, Mistral API, OpenAI-compatible API, Perplexity browser (scripted and thin Playwright backends)
- cooperative cancel-on-quorum with per-model timeout, concurrency enforcement, and a minimal browser circuit breaker
- browser adapter lifecycle cleanup that resets idle session state on shutdown and detects stale runtime/session mismatches
- structured key-value logging across orchestrator, browser adapters, API routes, and PostgreSQL degradation paths
- operator surfaces: recent-task listing with multi-axis filtering, rich task detail with diagnostics

Not yet implemented:
- account pools
- richer retry policies beyond the current deferral
- broader browser catalog refresh if account-tier drift continues
- analytics dashboards
- admin UI
- cross-project integration glue

Excluded by design:
- SQLite

## Module boundaries

- `api.routes`: HTTP contract only - no domain logic, no adapter imports
- `core.models`: canonical model catalog and alias resolution
- `core.orchestrator`: use-case orchestration, event building, storage coordination
- `core.contracts`: execution adapter interface, result envelopes, failure taxonomy
- `core.planning`: execution plan construction and request validation
- `core.router`: adapter dispatch, concurrency gate, quorum aggregation
- `core.readiness`: component health aggregation across profiles
- `core.concurrency`: thread-safe per-model concurrency gate
- `core.execution_profile`: profile-aware adapter requirement sets
- `adapters.dry_run`: simulated execution for testing and dry-run mode
- `adapters.api.mistral`: Mistral API adapter
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
4. Provider-specific naming drift must be normalized through the central model registry.
5. Event logging must not be a critical dependency for accepting or executing a task.

## Design rules

1. Every external dependency must sit behind an adapter boundary.
2. Persistence is replaceable. Memory first, PostgreSQL next.
3. Model names are canonicalized once at the edge.
4. Browser execution is a plugin, not the center of the system.
5. API execution is also a plugin, using the same orchestration contract.
6. Observability must be append-only and isolated from request execution.

## Next steps

1. Refresh browser catalog strategy if Perplexity account-tier drift keeps diverging from the canonical registry.
2. Backup and restore strategy for PostgreSQL.
3. Production migration tooling (version-tracked SQL or Alembic).
4. Account pools and any real retry model beyond the current deferral.
