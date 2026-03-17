# Architecture

## Goals

GraceKelly is being rebuilt as a small and explicit orchestration core.
The foundation must stay understandable under failure.

## Phase 0 boundaries

Included now:
- API shell
- model registry and alias resolution
- task submission contract
- in-memory task repository

Explicitly excluded now:
- browser automation
- account pools
- SQLite
- analytics dashboards
- admin UI
- cross-project integration glue

## Module boundaries

- `api.routes`: HTTP contract only
- `core.models`: canonical model catalog and alias resolution
- `core.orchestrator`: use-case orchestration and validation
- `core.contracts`: execution adapter contracts and result envelopes
- `storage.base`: storage contract
- `storage.memory`: phase 0 backend
- `storage.postgres`: durable backend for later phases

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

## Near-term next steps

1. Add execution adapter contracts.
2. Add a dry-run adapter and a minimal API adapter behind the same interface.
3. Add a multi-model execution plan and result envelope.
4. Add PostgreSQL-backed task and event storage.
5. Add browser worker package behind the adapter interface.
6. Add health probes for adapters and storage.
7. Add retry and policy layers after the contract stabilizes.
