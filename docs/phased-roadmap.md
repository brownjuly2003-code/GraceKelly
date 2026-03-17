# Phased Roadmap

## Phase 0: Clean foundation

Status: in progress

Deliverables:
- independent project root
- app factory
- public API contract
- canonical model registry
- memory-backed task repository

## Phase 1: Execution contract

Deliverables:
- adapter interface for prompt execution
- execution result envelope
- failure taxonomy and retry policy contract
- multi-model execution plan contract

## Phase 2: Browser worker

Deliverables:
- isolated browser adapter package
- session lifecycle abstraction
- model selection verification rules
- popup and auth recovery hooks

## Phase 3: Durable state

Deliverables:
- replace memory storage with PostgreSQL backend
- task event log
- health and integrity checks
- backup and restore strategy

## Phase 4: Reliability controls

Deliverables:
- account pool manager
- model fallback policy
- request budget and concurrency limits
- circuit breakers around adapters
- quorum and merge policy for multi-model execution

## Phase 5: Operations surface

Deliverables:
- metrics endpoint
- task inspection endpoint
- operator runbook
- lightweight admin surface if still justified

## Parallel track: API adapters

Deliverables:
- provider API adapter interface implementation
- first low-cost provider integration path
- provider-specific auth and rate-limit handling
