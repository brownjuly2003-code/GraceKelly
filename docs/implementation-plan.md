# Implementation Plan

This document is the working source of truth for GraceKelly delivery. We update it continuously: completed work gets checked off, new work is appended deliberately, and problems are logged briefly with the decision taken.

## Scope
- In: independent orchestrator core, PostgreSQL-backed durable state, multi-model orchestration, browser adapters, API adapters, healthchecks, tests, operator-facing task inspection.
- Out: legacy code reuse, shared runtime or storage with old projects, admin UI before core stability, analytics dashboards before event log maturity.

## Rules
- Update this file after every meaningful implementation step.
- Keep checklist items atomic and ordered.
- Record blockers briefly in `Issue log`.
- Record scope changes briefly in `Change log`.

## Independent review gates
- Gate 1: request an independent architectural review before freezing the PostgreSQL schema and shipping the first real migration, especially around `gk_task_steps`, `completed_at`, and `duration_ms`.
- Gate 2: request an independent operational review before declaring readiness semantics stable, specifically after introducing `required` vs `optional` adapters and before wiring alerts to overall readiness.
- Gate 3: request an independent execution-policy review before promoting multi-model from smoke-tested flow to production policy, especially for `quorum=1`, `first_success`, `timeout`, and cancel-on-quorum behaviour.
- Gate 4: request an independent boundary review before enabling real browser execution, to confirm that `core/` stays isolated from `adapters/browser/` and that browser-specific complexity is not leaking upward.
- Gate 5: request an independent deployment review before extracting the browser worker into a separate process or service, so IPC, persistence, and failure ownership do not drift early.

## Confirmed decisions
- PostgreSQL schema must be normalized before the first real migration: introduce `gk_task_steps`, add `completed_at`, `duration_ms`, `quorum`, `merge_strategy`, `adapter_hint`, `cancel_on_quorum`, `dry_run`, and `model_count` to `gk_tasks`, remove task-level `model_id` / `model_display_name`, and stop treating execution structure as JSON-only data.
- `metadata` is reserved for user-provided or trace-level data only. Step results, execution plans, and resolved requested models must move out of `metadata` into normalized storage.
- `gk_task_steps` MVP fields are: `task_id`, `step_index`, `model_id`, `model_display_name`, `backend`, `provider`, `status`, `failure_code`, `failure_message`, `output_text`, `duration_ms`, with initial statuses limited to `pending`, `completed`, `failed`, and `cancelled`, and with a 1-based composite primary key of `(task_id, step_index)` rather than a surrogate `step_id`.
- Readiness semantics should move from ad hoc degraded handling to an `ExecutionProfile` domain object resolved from `Settings`, with storage always required and adapter requirement sets derived from the active profile.
- `ModelSpec` should gain only three operational hints now: `timeout_seconds`, `expected_latency_class`, and `concurrency_limit`.
- Production-default execution policy should converge on `quorum=1`, `merge_strategy=first_success`, `cancel_on_quorum=true`, with timeout defined per model rather than globally.
- Step inspection should stay inside `GET /api/v1/tasks/{task_id}` for now by adding `steps` to `TaskView`; a separate steps endpoint is premature, and step `output_text` should be returned by default with truncation at serialization time plus an `output_truncated` flag.
- Dry-run tasks should not create `gk_task_steps` rows. For `dry_run = true`, persist only `gk_tasks` plus the minimal event stream.
- Phase 1 task statuses are `accepted`, `completed`, `failed`, and `cancelled`. Dry-run ends as `completed`; do not add `running` until execution becomes asynchronous.
- Adapter wiring should remain in `main.py` until a real complexity trigger appears, such as a third adapter family or a much larger composition root.
- Browser worker extraction into a separate process is a Phase 4+ concern only after browser mode proves useful in practice.
- `task + steps` persistence must be atomic in one PostgreSQL transaction, while events stay on a separate best-effort path so observability failures cannot roll back execution state.
- `cancel_on_quorum` should use cooperative cancellation via a token checked at adapter safe points; adapters should not be forced into hard interruption mid-I/O.
- `adapter_name` should stop being stored in `gk_tasks`; mixed-adapter semantics belong to step records, and task-level `adapter_name` should remain in the API as a computed field derived from steps.
- Retry attempts should not be modeled yet. No `attempt_no` in Phase 1; if retry becomes real later, it can be introduced through either `(task_id, step_index, attempt_no)` or task-level retry linkage.
- `retry_of_task_id` should not be added in Phase 1 either; retry linkage belongs to a later reliability phase once the retry model is actually chosen.
- `gk_task_events` should gain `sequence_no`, generated in the application, and event reads should order by `sequence_no` rather than `created_at`, with a database-enforced uniqueness constraint on `(task_id, sequence_no)`.
- `backend + provider` is sufficient identity for `gk_task_steps`; `adapter_name` should stay a computed property, not another stored column.
- The minimal canonical `event_type` set is: `task.accepted`, `task.completed`, `task.failed`, `step.completed`, `step.failed`, and `task.cancelled`. Skip `task.cancel_requested`, `step.started`, and `step.cancelled` for Phase 1, and use `task.cancelled` only for cancellation of the whole task, not for quorum-driven cancellation of remaining steps.
- `TaskStepView` v1 should include: `step_index`, `model_id`, `model_display_name`, `backend`, `provider`, `status`, `failure_code`, `failure_message`, `output_text`, `output_truncated`, and `duration_ms`.
- The first migration should rely on application-level validation plus `StrEnum` / Pydantic for statuses and merge strategies. Keep `NOT NULL` and structural constraints in SQL, but do not add DB-level `CHECK` constraints until the schema stabilizes.
- `task.accepted` should always include an execution-plan snapshot in its payload. For dry-run this is the only place where the planned steps live; for real execution it is the canonical plan snapshot that precedes step results.
- `gk_tasks.output_text` is strictly the final merged or winning task output. It is never a per-step output, and it must stay `NULL` for dry-run, failed, or cancelled tasks.
- `gk_tasks.failure_code` and `failure_message` are aggregate task-failure fields only. They are populated only when the task as a whole fails to reach quorum; step-level failures stay in `gk_task_steps` and `step.failed` events.
- Task-level `model_id` and `model_display_name` should be removed from storage. Winning and requested model information must be computed from steps, or from `task.accepted` payload for dry-run tasks.

## Current status
- Phase: Phase 1 in progress
- Overall state: normalized task/step/event contracts, profile-aware readiness, packaged PostgreSQL migration tooling, and browser-automation adapter boundaries are implemented in code; the in-memory path is green, the live PostgreSQL path has explicit validation and integration hooks, and the browser execution path is now exercisable end-to-end through a scripted backend
- Last updated: 2026-03-17

## Action items
[x] Create an independent project root at `D:\GraceKelly`.
[x] Add the initial FastAPI shell and phase-0 routes in `src/gracekelly/api/routes/`.
[x] Add a canonical model registry in `src/gracekelly/core/models.py`.
[x] Add a phase-0 in-memory task repository in `src/gracekelly/storage/`.
[x] Validate the scaffold with `compileall` and unit tests.
[x] Decide the durable backend strategy: PostgreSQL.
[x] Decide product scope: multi-model orchestration is required.
[x] Decide adapter strategy: support both browser adapters and API adapters.
[x] Add `src/gracekelly/core/contracts.py` for execution adapter interfaces and result envelopes.
[x] Add a failure taxonomy covering `auth_failed`, `model_mismatch`, `provider_unavailable`, `timeout`, `rate_limited`, `storage_failed`, `unknown_error`.
[x] Refactor `src/gracekelly/core/orchestrator.py` to orchestrate through adapter contracts instead of direct phase-0 logic.
[x] Add a dry-run adapter and contract tests to stabilize the execution pipeline before real providers.
[x] Add an API adapter package for provider-backed execution, starting with a minimal Mistral-compatible adapter boundary.
[x] Add a browser adapter package with isolated session lifecycle, popup handling, auth recovery, model verification, and submit policy.
[x] Add a multi-model execution plan object: requested models, sequencing, fallback rules, quorum policy, and result merge contract.
[x] Add task event models so execution history is append-only and decoupled from the request path.
[x] Add a PostgreSQL storage package with schema bootstrap, repository implementations, and non-blocking failure handling.
[x] Add health endpoints for app state, storage connectivity, and adapter readiness.
[x] Add HTTP/API smoke tests and unit tests for model resolution, orchestration policy, adapter contracts, and storage fallback behavior.
[x] Run the first end-to-end path: submit task -> execute via dry-run or API adapter -> persist task/event -> fetch task status.
[x] Normalize PostgreSQL storage around `gk_task_steps` and add `completed_at`, `duration_ms`, `quorum`, `merge_strategy`, `adapter_hint`, `cancel_on_quorum`, `dry_run`, and `model_count` to `gk_tasks` before the first real migration.
[x] Remove execution structure from `metadata` and keep only user-provided trace data there.
[x] Add `steps` to `TaskView` instead of introducing a separate steps endpoint, and serialize step outputs with a max-length policy plus `output_truncated`.
[x] Keep dry-run persistence out of `gk_task_steps`; for dry-run tasks, persist only `gk_tasks` and the minimal event stream.
[x] Settle Phase 1 task status semantics as `accepted` / `completed` / `failed` / `cancelled`, with dry-run persisted as `completed` and no `running` state yet.
[x] Introduce an `ExecutionProfile` domain object, resolve it from settings, and change readiness aggregation so optional adapters do not degrade overall status.
[x] Add `timeout_seconds`, `expected_latency_class`, and `concurrency_limit` to `ModelSpec`.
[x] Rename internal step sequencing from `step_priority` to 1-based `step_index`, use `(task_id, step_index)` as the primary key, and propagate the rename through planning, routing, contracts, storage, and API views.
[x] Add `pending` / `completed` / `failed` / `cancelled` lifecycle handling to `gk_task_steps`, include `model_display_name`, keep `(task_id, step_index)` as the primary key, and persist `task + steps` atomically.
[x] Change execution defaults toward `merge_strategy=first_success` and implement cooperative `cancel_on_quorum` through a cancellation token.
[x] Remove stored `adapter_name` from `gk_tasks`, keep API `adapter_name` as a computed field, and avoid adding `adapter_name` to `gk_task_steps`.
[x] Add `sequence_no` to `gk_task_events`, generate it in the orchestrator, enforce `UNIQUE (task_id, sequence_no)`, and switch event ordering from timestamp-based to sequence-based reads.
[x] Fix the Phase 1 event taxonomy to `task.accepted`, `task.completed`, `task.failed`, `step.completed`, `step.failed`, and `task.cancelled`, and reserve `task.cancelled` for whole-task cancellation only.
[x] Put execution-plan snapshots into `task.accepted` payloads for both dry-run and real execution, and source dry-run requested models from that payload.
[x] Shape `TaskStepView` v1 around operator diagnostics: include backend/provider, display name, failure message, truncation flag, and duration.
[x] Remove task-level `model_id` / `model_display_name`, derive winning/requested models from steps or `task.accepted` payload, and make task-level API model data reflect that reality.
[x] Lock the `gk_tasks.output_text` contract to final merged/winning output only, with `NULL` for dry-run, failed, and cancelled tasks.
[x] Keep `gk_tasks.failure_code` / `failure_message` aggregate-only and populate them strictly on task-level failure.
[x] Keep status and merge-strategy validation in code for the first migration; postpone DB-level `CHECK` constraints until schema freeze.
[x] Extract the first PostgreSQL schema into a packaged SQL migration, add schema-diff validation helpers, and add a safe validation CLI that can bootstrap and inspect a live DSN without writing task data.
[x] Add optional live PostgreSQL integration coverage gated by `GRACEKELLY_POSTGRES_TEST_DSN`, so full-stack task/event persistence can be exercised without making live DB access mandatory for every test run.
[x] Add a scripted browser automation backend plus HTTP smoke coverage so the browser execution path can be exercised end-to-end before a live browser driver exists.
[x] Make root-level `pytest -q` work without manual `PYTHONPATH` setup by configuring pytest import-path handling in project config.
[x] Enforce `merge_strategy` through code-level enum validation so unsupported execution policies are rejected at the request boundary.
[x] Surface repository failures as explicit `storage_failed` API errors instead of generic 500s, while keeping event persistence best-effort.
[x] Reject duplicate requested models after canonicalization so alias-equivalent names cannot schedule the same model twice.
[x] Include storage schema status in readiness aggregation so PostgreSQL schema drift degrades readiness instead of hiding behind a successful ping.
[x] Reject `concat` plans that can short-circuit before all requested outputs run, and cover the non-short-circuit concat path in router tests.
[x] Enforce `reasoning` capability at planning time so unsupported models are rejected instead of silently downgraded.
[x] Formalize `schema_report()` on the storage interface and add direct tests for step-output truncation and non-applicable memory schema reporting.
[x] Make the in-memory backend enforce per-task event `sequence_no` uniqueness and cover ordering/duplicate rejection directly.
[x] Align live PostgreSQL tests with the actual `POST /orchestrate` summary contract and assert that step/event detail lives on `GET /tasks/{task_id}`.
[x] Add explicit coverage for `first_success` quorum short-circuiting, including cancelled downstream steps and deterministic event sequencing.
[x] Expand HTTP smoke coverage for `/api/v1/models` and schema-aware readiness details.
[x] Add unit coverage for the PostgreSQL validation CLI, including missing-DSN, degraded-schema, and bootstrapped-ok outcomes.
[x] Make dry-run `POST /orchestrate` summary responses resilient to best-effort event logging failure by deriving requested models from the validated request.
[x] Initialize a local git repository on `main` and extend ignore rules for generated Python packaging/test artifacts.
[x] Normalize persisted `merge_strategy` values back to enum form on repository read paths and remove the remaining stringly-typed comparison in event building.
[x] Tighten browser failure taxonomy so unexpected automation crashes map to `unknown_error` instead of `provider_unavailable`.
[x] Remove post-write storage readback from `POST /orchestrate` summaries so accepted submissions can return successfully even if immediate read paths are degraded.
[x] Normalize task/step/event status and failure-code values back to enums on internal storage paths instead of keeping raw strings alive past the DB boundary.
[x] Add `.gitattributes` to enforce repository line-ending policy explicitly instead of relying on host Git defaults.
[x] Validate request metadata for JSON-serializability before orchestration so storage backends do not discover bad payloads late.
[x] Fix adapter-name resolution after enum normalization so completed winning steps remain authoritative over cancelled fallbacks.
[ ] Defer retry schema until a concrete retry policy exists; do not add `attempt_no` or `retry_of_task_id` before a reliability phase chooses the retry model.
[ ] Start browser execution only after the adapter contract and PostgreSQL-backed task/event flow are stable.

## Issue log
- 2026-03-16: Legacy reference project has corrupted SQLite databases. Decision: no storage design or migration path in GraceKelly may depend on SQLite integrity.
- 2026-03-16: Legacy browser flow shows model-name drift around `Kimi K2.5` vs `Kimi K2`. Decision: model equivalence must be canonicalized in one registry at the edge.
- 2026-03-16: Legacy runtime mixes execution, logging, and operator concerns. Decision: event logging in GraceKelly must not be a critical dependency for request acceptance.
- 2026-03-16: Browser adapter is still intentionally absent. Decision: mixed multi-model plans can already be represented, but browser execution remains gated until the adapter package exists.
- 2026-03-17: PostgreSQL schema bootstrap is no longer only embedded DDL; it now has a packaged migration file plus CLI/schema-diff tooling, but an actual live DSN was not exercised in this session.
- 2026-03-16: Browser adapter package now exists as a skeleton, but real browser automation is still intentionally deferred behind readiness gating.
- 2026-03-17: Browser execution is now runnable through a scripted automation backend, but no live site driver exists yet. Decision: stabilize orchestration, readiness, and operator views against the scripted path before adding a real browser engine.
- 2026-03-17: Test collection failed from the repository root unless `PYTHONPATH=src` was set manually, and pytest cache writes are noisy in the current execution environment. Decision: configure pytest in-project so `pytest -q` is the default local entrypoint and disable cacheprovider for now.
- 2026-03-17: `merge_strategy` was still effectively open-ended at the API boundary even though execution policy is part of the stable contract. Decision: validate it explicitly in code via enum-backed request parsing instead of treating unknown strings as implicit concatenation.
- 2026-03-17: Repository failures during submit and fetch still surfaced as generic 500s despite `storage_failed` already being part of the canonical failure taxonomy. Decision: wrap repository access in the orchestrator service and translate those failures to explicit `503 storage_failed` API responses.
- 2026-03-17: Alias-equivalent model names could still be scheduled twice in one request because canonicalization happened without duplicate detection. Decision: reject duplicate canonical models at planning time instead of silently running redundant steps.
- 2026-03-17: Storage readiness still only reflected connectivity and could miss PostgreSQL schema drift even though schema validation tooling already exists. Decision: aggregate `schema_report()` into storage readiness whenever a backend provides it.
- 2026-03-17: `concat` could still be paired with short-circuit quorum cancellation, producing silently partial merged output. Decision: reject that policy combination during planning; `concat` may still run with `cancel_on_quorum=false` or with quorum covering all requested models.
- 2026-03-17: `reasoning` was exposed as a request flag and model capability, but unsupported models still accepted it silently. Decision: reject those requests during planning instead of allowing capability drift between catalog and execution.
- 2026-03-17: Storage schema reporting had become duck-typed after readiness started consuming it, and step-output truncation was still untested. Decision: make `schema_report()` a default repository capability and add direct contract tests for truncation behavior.
- 2026-03-17: The in-memory backend still allowed duplicate event sequence numbers even though PostgreSQL enforces `UNIQUE (task_id, sequence_no)`. Decision: mirror that invariant in memory so local tests can catch sequence-generation bugs earlier.
- 2026-03-17: Optional live PostgreSQL tests had drifted to an older assumption that `POST /orchestrate` returns step detail. Decision: keep `POST` as a summary contract and fetch step/event detail only through `GET /tasks/{task_id}`.
- 2026-03-17: Cooperative quorum cancellation was implemented in code, but there was still no direct assertion that downstream adapters are skipped and that task events remain sequence-stable. Decision: add explicit router and orchestrator coverage for short-circuit cancellation semantics.
- 2026-03-17: Public API routes for model catalog and schema-aware readiness existed, but their richer response shapes were still mostly implicit. Decision: lock them down with smoke tests so future refactors do not silently flatten those contracts.
- 2026-03-17: The PostgreSQL validation CLI was part of the documented operator workflow, but it had no automated coverage at all. Decision: add unit tests around DSN resolution, degraded reporting, and successful bootstrapped runs.
- 2026-03-17: Best-effort event persistence could strip `requested_models` out of dry-run submission responses even when task acceptance succeeded. Decision: build the `POST /orchestrate` summary from the validated request model list rather than depending on accepted-event persistence.
- 2026-03-17: The project was still being managed without local git history. Decision: initialize a repository on `main` and ignore generated Python packaging/test artifacts before further iteration.
- 2026-03-17: `MergeStrategy` had been introduced at the request/planning layer, but repository read paths and one event-building branch still fell back to raw strings. Decision: normalize storage reads back to `MergeStrategy` and remove the last internal string comparison.
- 2026-03-17: Browser adapter generic runtime failures were still reported as `provider_unavailable`, conflating internal crashes with upstream availability problems. Decision: map unexpected browser exceptions to `unknown_error` and reserve `provider_unavailable` for actual configuration/provider reachability issues.
- 2026-03-17: `POST /orchestrate` still performed immediate storage readback after a successful write, so accepted tasks could surface as `503` if read paths were degraded. Decision: return submission summaries from the in-memory snapshot produced during submit and leave storage reads to `GET /tasks/{task_id}`.
- 2026-03-17: Task, step, and event records were still carrying raw string enums internally after leaving the DB/API boundaries. Decision: normalize repository read paths back to `TaskStatus`, `StepStatus`, `EventType`, and `FailureCode` so internal comparisons stay typed.
- 2026-03-17: Git on this Windows host still emitted LF/CRLF warnings because repository line-ending policy was implicit. Decision: add `.gitattributes` so line endings are controlled by the repo, not by per-machine Git defaults.
- 2026-03-17: `metadata` was still allowed to carry arbitrary Python objects for non-HTTP callers, leaving JSON-serialization failures to appear only during persistence. Decision: validate JSON-serializability at request-model construction time.
- 2026-03-17: One adapter-name resolver branch was still comparing enum-backed step statuses to string values, which could misclassify completed-plus-cancelled plans as mixed. Decision: finish the enum migration in summary serialization and pin it with a direct response-contract test.
- 2026-03-16: Health can legitimately report `degraded` in development when optional adapters are intentionally unconfigured. Decision: treat degraded readiness as operationally informative, not as a startup failure.
- 2026-03-16: HTTP smoke tests exposed a missing `requested_models` field in `TaskView`. Decision: keep smoke coverage mandatory for API contract changes; bug fixed immediately.
- 2026-03-16: answers1.md made it clear that several current choices are transitional only: JSON-heavy execution storage, degraded-on-optional readiness, and `best_effort` merge semantics should not be treated as stable architecture.
- 2026-03-16: answers2.md confirmed that the current persistence contract is still underspecified: `gk_tasks` needs execution-plan columns, step output serialization needs truncation policy, and cancellation must be cooperative rather than hard-interrupt based.
- 2026-03-16: Mixed-adapter tasks make task-level `adapter_name` semantics inconsistent. Decision: move adapter identity to step records and treat any task-level adapter label as computed compatibility output only.
- 2026-03-16: Timestamp-only ordering is too weak for append-only events. Decision: add per-task `sequence_no` now before any real data accrues.
- 2026-03-16: Internal naming still says `step_priority`, but the field is positional rather than prioritization semantics. Decision: rename it to 1-based `step_index` before schema freeze.
- 2026-03-16: Retry shape is still intentionally unknown. Decision: keep both `attempt_no` and `retry_of_task_id` out of Phase 1 so the first schema does not encode an unchosen retry model.
- 2026-03-16: Dry-run data can pollute step analytics if stored alongside real execution steps. Decision: do not create `gk_task_steps` rows for dry-run tasks.
- 2026-03-16: Enum-like values are still evolving. Decision: enforce statuses and merge strategies in code first, and postpone SQL `CHECK` constraints until the schema stops moving.
- 2026-03-16: Task-level model fields are misleading in multi-model flows because they currently point at the first requested step rather than a stable semantic. Decision: remove them from `gk_tasks` and compute requested/winning model data from steps or accepted-event payload.
- 2026-03-16: Quorum-driven step cancellation is not the same as cancelling the whole task. Decision: keep `task.cancelled` for whole-task cancellation only and carry `cancelled_steps` in `task.completed` payload when quorum short-circuits the plan.
- 2026-03-16: The normalized repository and API contract are now implemented and green against the in-memory test path. Decision: keep PostgreSQL live validation as the next storage-specific checkpoint before schema freeze.
- 2026-03-16: Readiness semantics are now profile-aware in code, but alerting and production expectations are still unvalidated against a live deployment. Decision: keep the independent operational review gate before treating readiness as stable.
- 2026-03-17: `questions.md` now contains only truly open blockers. Decision: remove future-looking placeholders and keep the file empty until a real design or implementation question appears.

## Change log
- 2026-03-16: Chosen PostgreSQL as the first durable backend.
- 2026-03-16: Confirmed multi-model orchestration is in scope from the mainline design, not as a later add-on.
- 2026-03-16: Confirmed API adapters are first-class citizens alongside browser adapters.
- 2026-03-16: Added execution contracts, dry-run adapter, and first adapter-based orchestration flow.
- 2026-03-16: Added multi-model planning, execution routing, and a minimal Mistral API adapter boundary.
- 2026-03-16: Added append-only task events and a PostgreSQL storage skeleton with schema bootstrap.
- 2026-03-16: Added readiness reporting and the first browser adapter skeleton for Perplexity.
- 2026-03-16: Added HTTP/API smoke coverage for health, readiness, orchestration, and task retrieval.
- 2026-03-16: Added explicit independent-review gates so external audit is pulled in at irreversible architecture moments, not ad hoc.
- 2026-03-16: Incorporated second-round architecture answers into the plan: normalized step storage, execution profiles, per-model timeouts, and `first_success` policy.
- 2026-03-16: Incorporated third-round architecture answers into the plan: normalized `gk_tasks` execution columns, step-status boundaries, transactional `task + steps`, default step-output truncation, cooperative cancellation, and an explicit `ExecutionProfile` domain object.
- 2026-03-16: Incorporated fourth-round architecture answers into the plan: composite step keys, removal of stored task-level adapter identity, deferred retry schema, and deterministic event ordering via `sequence_no`.
- 2026-03-16: Incorporated fifth-round architecture answers into the plan: computed API `adapter_name`, `step_index` rename, explicit rejection of `retry_of_task_id` in Phase 1, `UNIQUE (task_id, sequence_no)`, and keeping adapter identity normalized as `backend + provider`.
- 2026-03-16: Incorporated sixth-round architecture answers into the plan: dry-run without step rows, the Phase 1 event taxonomy, the diagnostic shape of `TaskStepView`, and postponing DB `CHECK` constraints until schema freeze.
- 2026-03-16: Incorporated seventh-round architecture answers into the plan: final Phase 1 task statuses, corrected `task.cancelled` semantics, removal of task-level model identity, accepted-event plan snapshots, final `output_text` semantics, and aggregate-only task failure fields.
- 2026-03-16: Implemented the first normalized task/step/event slice in code, rewired the API onto computed task views, and verified the in-memory path with `16/16` unit and smoke tests passing.
- 2026-03-16: Implemented `ExecutionProfile` resolution from settings and profile-aware readiness aggregation, with the test suite now passing `17/17`.
- 2026-03-17: Extracted the first PostgreSQL schema into packaged SQL, added schema-diff validation helpers, and introduced the `gracekelly-validate-postgres` operational entrypoint.
- 2026-03-17: Added optional live PostgreSQL integration tests gated by `GRACEKELLY_POSTGRES_TEST_DSN` and expanded the local test suite to `24/24` green without requiring a running database.
- 2026-03-17: Added a configurable scripted browser automation backend, wired it through `Settings` and `main.py`, documented the mode, covered both success and auth-failure browser flows through HTTP smoke tests, and expanded the local test suite to `28` passing tests with `2` optional live-PostgreSQL skips.
- 2026-03-17: Configured pytest to add `src` to the import path and disable cacheprovider, so `pytest -q` now works from the repository root without manual environment setup.
- 2026-03-17: Added enum-backed merge-strategy validation across request parsing, planning, and routing, and covered unknown strategies with unit and HTTP tests.
- 2026-03-17: Wrapped repository failures in a service-level storage exception and mapped them to explicit `503 storage_failed` API responses, with unit and HTTP coverage for submit and fetch paths.
- 2026-03-17: Added duplicate-model rejection after canonicalization so alias variants like `Kimi K2` and `Kimi K2.5` cannot create redundant execution steps.
- 2026-03-17: Extended readiness aggregation to include storage schema status, so repository connectivity and schema integrity now both influence the storage component result.
- 2026-03-17: Tightened execution-policy validation so `concat` cannot silently short-circuit, and added router coverage for the valid mixed-backend concat path.
- 2026-03-17: Added capability-aware planning validation so `reasoning=true` is rejected for models that do not advertise reasoning support.
- 2026-03-17: Promoted `schema_report()` to a default repository contract and added direct tests for operator-facing step-output truncation.
- 2026-03-17: Brought the in-memory event store closer to PostgreSQL semantics by enforcing per-task `sequence_no` uniqueness and testing deterministic ordering explicitly.
- 2026-03-17: Realigned live PostgreSQL tests with the current HTTP contract: `POST /orchestrate` returns summary fields only, while step and event detail remain on task retrieval.
- 2026-03-17: Added direct coverage for quorum-driven short-circuit execution, including cancelled step persistence, skipped downstream adapters, and ordered event sequences.
- 2026-03-17: Expanded HTTP smoke coverage for the model catalog and readiness detail payloads, including reasoning capability exposure and schema-aware storage reporting.
- 2026-03-17: Added unit coverage for the PostgreSQL validation CLI so its operator-facing exit codes and JSON reports are now regression-checked.
- 2026-03-17: Hardened dry-run submission responses against event-log failures by sourcing requested model summaries directly from the validated request payload.
- 2026-03-17: Initialized local git tracking on `main` and extended `.gitignore` to cover generated packaging and coverage artifacts.
- 2026-03-17: Removed the last stringly-typed `merge_strategy` branch from orchestration internals and normalized repository read paths back to enum values.
- 2026-03-17: Corrected browser error taxonomy so unexpected automation crashes now surface as `unknown_error` rather than being mislabeled as provider availability failures.
- 2026-03-17: Reworked `POST /orchestrate` to return from the submit-time snapshot instead of re-reading storage immediately, improving resilience when event or step read paths are temporarily degraded.
- 2026-03-17: Extended enum normalization through task, step, and event repository records so typed status/failure comparisons survive persistence round-trips.
- 2026-03-17: Added repository-level line-ending policy via `.gitattributes` to stabilize Git behavior across Windows environments.
- 2026-03-17: Added request-level metadata validation so non-serializable Python objects are rejected before orchestration reaches persistence.
- 2026-03-17: Fixed adapter-name summary resolution after enum normalization and added direct coverage for completed-plus-cancelled short-circuit responses.
