# Phased Roadmap

Last updated: 2026-03-17

## Phase 0: Clean foundation

Status: complete

Deliverables:
- independent project root
- app factory
- public API contract
- canonical model registry
- memory-backed task repository

## Phase 1: Execution contract

Status: substantially complete

Deliverables:
- adapter interface for prompt execution
- execution result envelope
- failure taxonomy and retry policy contract
- multi-model execution plan contract
- cooperative cancel-on-quorum execution flow
- typed task, step, and event contracts
- model timeout and concurrency hints enforced in runtime

Remaining before this phase is production-stable:
- Gate 2 operational review for readiness semantics
- Gate 3 execution-policy review for defaults and failure handling

## Phase 2: Browser worker

Status: partial, ready for live-driver spike

Deliverables:
- isolated browser adapter package
- session lifecycle abstraction
- model selection verification rules
- popup and auth recovery hooks
- scripted browser automation backend
- external Gate 4 boundary review completed in `audit2.md`

Next:
- DOM reconnaissance against the live provider UI
- selector extraction into a dedicated browser-layer module
- thin Playwright-backed `BrowserAutomationPort` implementation
- lifecycle cleanup once a real browser process exists

## Phase 3: Durable state

Status: complete for current scope

Deliverables:
- PostgreSQL backend alongside memory storage
- task event log
- health and integrity checks
- packaged SQL migration and schema-diff tooling
- validation CLI and optional live-PostgreSQL tests

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
- execution saturation visibility in health/readiness
- fail-fast plan/result cardinality invariants
- explicit retry-schema deferral tests

Remaining:
- circuit breaker behavior
- account-pool abstractions
- any real retry model beyond the current deferral

## Phase 5: Operations surface

Status: substantially complete

Deliverables:
- metrics endpoint
- task inspection endpoint
- operator runbook
- lightweight admin surface if still justified

Already delivered:
- `/health` and `/api/v1/readiness`
- recent-task list with operator filters
- rich `GET /api/v1/tasks/{task_id}` task, step, and event views
- execution saturation and terminal-summary diagnostics

## Parallel track: API adapters

Status: started

Deliverables:
- provider API adapter interface implementation
- first low-cost provider integration path
- provider-specific auth and rate-limit handling

Already delivered:
- Mistral-compatible adapter

Next:
- OpenAI-compatible adapter as a hedge against browser fragility
