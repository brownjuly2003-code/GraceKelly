# GraceKelly Gate 1 Audit Brief

Date: 2026-03-18
Status: ready for independent review
Working tree: not clean; ignore unrelated local note updates in `questions.md` and `audit2-recommendations.md`
Local test status: `180 passed, 4 skipped`

## Why this audit exists

GraceKelly still marks Gate 1 as open in `docs/implementation-plan.md`.

The project now has a real normalized PostgreSQL shape in code:

- packaged SQL migration at `src/gracekelly/storage/migrations/0001_initial.sql`
- normalized `gk_tasks`, `gk_task_steps`, and `gk_task_events`
- PostgreSQL repository read/write paths
- snapshot export/import/inspect tooling built on top of the storage contract

This is the right time to ask for an external schema review before any schema-freeze claim, real-environment adoption, or follow-up migration that would make the current shape harder to change.

## Current system state

Implemented and regression-covered:

- normalized task, step, and event contracts
- PostgreSQL bootstrap migration and repository implementation
- task-scoped export/import/inspect tooling for PostgreSQL artifacts
- memory/PostgreSQL contract alignment for task, step, and event behavior
- operator task inspection and readiness surfaces built on top of the current storage model

Not yet introduced:

- retry schema (`attempt_no`, retry linkage)
- non-bootstrap production migration flow
- background workers or queue-owned execution state

## Scope of this audit

Review the storage and event schema boundary only.

In scope:

- whether the current normalized task/step/event split is the right Phase 1 shape
- whether `gk_task_steps` fields are sufficient without premature widening
- whether task-level vs step-level vs event-level responsibilities are drawn correctly
- whether `completed_at`, `duration_ms`, `quorum`, `merge_strategy`, `adapter_hint`, and `cancel_on_quorum` live at the right level
- whether best-effort event persistence is the right boundary versus transactional task/step writes
- whether current identifiers, primary keys, uniqueness rules, and JSON payload responsibilities are sound
- whether the schema is leaving dangerous blind spots for future retry/import/export work

Out of scope:

- browser DOM/runtime design
- readiness semantics and alert policy
- production execution defaults
- worker/process extraction
- admin UI

## Audit questions

1. Is the current split between `gk_tasks`, `gk_task_steps`, and `gk_task_events` correct for the next 2-3 iterations, or is a structural change still advisable now?
2. Are `gk_task_steps` fields sufficient, especially around step identity, failure detail, and per-step output, without adding premature retry columns?
3. Is `(task_id, step_index)` the right primary key for steps at this phase, or are we likely to regret not reserving room for retries/attempts earlier?
4. Is application-generated `sequence_no` with `UNIQUE (task_id, sequence_no)` the right event-ordering model?
5. Is the boundary between normalized columns and JSON event payloads correct, or are we leaving important operator/debug data too implicit in payloads?
6. Is keeping task+steps transactional while event writes remain best-effort the right durability tradeoff?
7. Are current task-level fields (`output_text`, `failure_code`, `failure_message`) correctly limited to aggregate task outcomes?
8. Do export/import/inspect capabilities suggest any missing invariants or manifest fields at the storage layer itself?
9. Is the current schema acceptable to treat as the baseline for a real environment, or should one more migration happen before that point?

## Constraints that must hold

- `core/` stays storage-backend-agnostic above the repository contract
- memory and PostgreSQL semantics stay aligned at the contract level
- retry modeling stays explicitly deferred unless the review concludes deferral is unsafe
- browser/API-specific debug details should not force widening normalized step tables prematurely
- export/import tooling should not become the accidental owner of schema invariants that belong in the repository/schema layer

## Suggested review entry points

- `src/gracekelly/storage/migrations/0001_initial.sql`
- `src/gracekelly/storage/base.py`
- `src/gracekelly/storage/postgres.py`
- `src/gracekelly/storage/schema.py`
- `src/gracekelly/core/orchestrator.py`
- `src/gracekelly/schemas.py`
- `docs/implementation-plan.md`

## Expected outcome

One of:

- approve the current schema boundary and proceed without structural changes
- approve with conditions, naming the exact migration or invariant to add next
- reject the current shape and identify the specific schema/design issue that must be corrected before schema freeze or real-environment use
