# GraceKelly Gate 4 Audit Brief

Date: 2026-03-17
Status: awaiting independent review before live browser execution
Working tree: clean at the moment this brief was prepared
Local test status: `68 passed, 3 skipped`

## Why this audit exists

GraceKelly has reached the plan's Gate 4 boundary:

- The scripted browser backend is already wired end-to-end.
- Core contracts, task/event persistence, readiness, and operator surfaces are stable enough to support a real browser spike.
- The next real implementation step would be replacing the scripted browser path with a live browser/site driver.

Per the implementation plan, that change must not start until an independent review confirms that browser-specific complexity will stay inside `adapters/browser/` and will not leak upward into `core/`.

## Current system state

Implemented and regression-covered:

- Typed execution contracts in `src/gracekelly/core/contracts.py`
- Execution planning, routing, cancellation, and per-model runtime hints in `src/gracekelly/core/`
- `memory` and `postgres` repositories with task, step, and event persistence in `src/gracekelly/storage/`
- Dry-run adapter, Mistral API adapter, and scripted Perplexity browser path in `src/gracekelly/adapters/`
- Health and readiness surfaces in `src/gracekelly/api/routes/health.py` and `src/gracekelly/core/readiness.py`
- Operator task inspection in `GET /api/v1/tasks` and `GET /api/v1/tasks/{task_id}`
- Event payload diagnostics, recent-task filters, and top-level task summaries for execution policy and terminal outcomes

Recently completed before this audit stop:

- richer task-list summaries
- `execution_mode` filtering for recent-task triage
- top-level terminal execution summary on `TaskView`
- top-level execution-policy fields on `TaskView`

Recent commits:

- `eb44ef8` `Extend task list operator summaries`
- `8fa043f` `Add execution-mode task filtering`
- `db2fb97` `Expose terminal task summaries`
- `b3bfd54` `Expose task execution policy`

## Scope of this audit

Review only the boundary for the next step: introducing a real browser driver.

In scope:

- whether current `ExecutionAdapter` / `ExecutionRequest` / `ExecutionResult` seams are sufficient for live browser work
- whether `ExecutionRouter` and `OrchestratorService` are still cleanly browser-agnostic
- whether `adapters/browser/` owns enough of session, auth, popup, and model-selection behavior
- whether the current task/event contracts are sufficient for live browser debugging without widening normalized storage
- whether `main.py` wiring is still an acceptable composition root for the first live browser increment

Out of scope:

- browser worker extraction into another process or service
- retry modeling or retry schema
- account pooling
- queueing/background jobs
- admin UI
- broader production hardening beyond what is strictly required for the first live browser spike

## Audit questions

1. Can a live browser driver be added behind the current adapter boundary without introducing browser-aware branches into `core/`?
2. Is `ExecutionRequest` expressive enough for real browser execution, or is one more abstraction needed before a live driver lands?
3. Should browser session state, auth recovery, popup handling, and DOM/model verification remain entirely inside `adapters/browser/`, or is any of that pressure already leaking into shared layers?
4. Are the current task, step, and event contracts sufficient for operator forensics once a live browser is involved?
5. Is the current synchronous execution model acceptable for the first live browser slice, or must off-thread/async execution be addressed first?
6. Does the current composition root in `src/gracekelly/main.py` remain acceptable for a first live driver, or is refactoring required before adding real browser runtime dependencies?
7. What is the smallest safe live-browser milestone that keeps rollback easy if the provider UI changes?
8. What browser-specific data must remain out of normalized storage for now?

## Constraints that must hold

- `core/` must stay provider- and browser-agnostic.
- Browser-specific failure handling must stay in `adapters/browser/`.
- `gk_task_steps` must not be widened just to accommodate browser debug data.
- Memory and PostgreSQL behavior must stay aligned at the contract level.
- The current scripted backend must remain available as a stable fallback/test path.
- This phase must not implicitly smuggle in worker extraction, retries, or queue infrastructure.

## Suggested review entry points

- `src/gracekelly/core/contracts.py`
- `src/gracekelly/core/router.py`
- `src/gracekelly/core/orchestrator.py`
- `src/gracekelly/adapters/browser/perplexity.py`
- `src/gracekelly/adapters/browser/session.py`
- `src/gracekelly/adapters/browser/policy.py`
- `src/gracekelly/main.py`
- `docs/implementation-plan.md`

## Expected outcome

One of:

- approve the current boundary and proceed with a minimal live browser driver
- approve with conditions, listing the exact seam or contract change required first
- reject the current boundary and name the specific layering violation that must be fixed before any live browser work starts
