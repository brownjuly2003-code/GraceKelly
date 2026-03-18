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
- In this plan, `audit` always means an external evaluation by a separate reviewer/colleague. Internal self-checks or prep notes do not satisfy an audit gate.

## Independent review gates
- Gate 1: request an independent architectural review before freezing the PostgreSQL schema and shipping the first real migration, especially around `gk_task_steps`, `completed_at`, and `duration_ms`.
- Gate 2: request an independent operational review before declaring readiness semantics stable, specifically after introducing `required` vs `optional` adapters and before wiring alerts to overall readiness.
- Gate 3: request an independent execution-policy review before promoting multi-model from smoke-tested flow to production policy, especially for `quorum=1`, `first_success`, `timeout`, and cancel-on-quorum behaviour.
- Gate 4: request an independent boundary review before enabling real browser execution, to confirm that `core/` stays isolated from `adapters/browser/` and that browser-specific complexity is not leaking upward.
- Gate 5: request an independent deployment review before extracting the browser worker into a separate process or service, so IPC, persistence, and failure ownership do not drift early.

## Audit timing
- Audit definition: an audit gate is satisfied only by an external review artifact from a separate reviewer/colleague, not by the implementation agent's own summary or prep brief.
- Gate 1 timing: before proposing the first non-bootstrap PostgreSQL migration for a real environment, or before any schema-freeze decision that would make `gk_task_steps` and task timing fields hard to change.
- Gate 2 timing: before treating readiness semantics as stable enough for alerts, runbooks, or production SLO interpretation; not due yet while readiness details and operator surfaces are still moving.
- Gate 3 timing: before calling the current multi-model defaults production policy; not due yet while `first_success`, per-model timeout, and cancel-on-quorum behaviour are still being exercised mainly through smoke and operator workflows.
- Gate 4 timing: immediately before replacing the scripted browser backend with a live browser/site driver. This is the next likely audit trigger if browser execution work resumes.
- Gate 5 timing: immediately before splitting browser execution into a separate worker, process, or service boundary.
- Current audit status: Gate 4 external boundary review is complete via `audit2.md` on 2026-03-17, with follow-up notes captured in `audit2-recommendations.md`. Browser-layer preparation may continue, and the first thin Playwright slice is now in code; Gates 2 and 3 still remain before production alerting or policy hardening.

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
- Phase: Phase 1 complete, Phase 2 browser spike next
- Overall state: the core orchestration contract is stable with normalized task/step/event models, profile-aware readiness, and dual-backend storage (memory + PostgreSQL with packaged migration, validation, and task-scoped export/import tooling). Browser execution is exercisable end-to-end through a scripted backend, and the first headed Playwright slice has now passed a dedicated-profile authenticated smoke against the real Perplexity UI. API execution works through the Mistral and OpenAI-compatible adapters. In-process per-model concurrency limits, per-model timeouts, and a minimal browser-adapter circuit breaker are enforced at runtime. Operator surfaces include recent-task listing with multi-axis filtering (status, dry_run, failure_code, execution_mode), rich task detail with execution-plan policy and terminal summary diagnostics, and execution-plane saturation plus browser-breaker visibility through health/readiness and `/metrics`. The blocking sync execution path is offloaded from async HTTP routes via `asyncio.to_thread`. Structured key-value logs now cover orchestrator event-persistence failures, browser execution, API route request/response summaries, and PostgreSQL degraded health/schema paths, with `metadata.trace_id` propagated through route and orchestrator lifecycle logs when present. PostgreSQL connect timeout is explicitly configurable. In-memory repository is thread-safe via `RLock`. Step/result cardinality is enforced with `strict=True` zip.
- Gate status: Gate 1 (schema) — open, Gate 2 (operational) — open, Gate 3 (execution policy) — open, Gate 4 (browser boundary) — completed
- Last updated: 2026-03-18

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
[x] Normalize `adapter_hint` to an enum across request parsing, planning, and storage read paths.
[x] Normalize `execution_mode` to an enum across adapters, router aggregation, and storage read paths.
[x] Apply per-model timeout hints in the API adapter path and expose model operational hints through `/api/v1/models`.
[x] Enforce `ModelSpec.concurrency_limit` in-process inside `ExecutionRouter` and fail fast with `rate_limited` when a model is saturated.
[x] Expose execution-plane concurrency diagnostics through readiness/health so operators can see active and saturated models.
[x] Carry adapter result details into `step.completed` / `step.failed` event payloads so `GET /tasks/{id}` preserves operator diagnostics without widening the step table.
[x] Add `GET /api/v1/tasks` as a recent-task summary listing for operators, without widening the existing per-task detail contract.
[x] Add `status` and `dry_run` filters to `GET /api/v1/tasks` so recent-task inspection supports basic triage workflows.
[x] Enrich `GET /api/v1/tasks` summaries with `adapter_name` and `requested_models` so the list is useful without drilling into every task.
[x] Extend optional live PostgreSQL coverage to include recent-task summary listing and filter behavior so operator surfaces stay aligned across backends.
[x] Add `failure_code` filtering to `GET /api/v1/tasks` so operator triage can target specific failure classes directly.
[x] Carry aggregate execution-router details into final task events so task history preserves batch-level routing context alongside per-step diagnostics.
[x] Make audit timing explicit beside the independent review gates so the next external audit point is unambiguous during autonomous implementation.
[x] Extend `GET /api/v1/tasks` summaries with winning-model and short-circuit context so quorum outcomes are visible without fetching full task detail.
[x] Add `execution_mode` filtering to `GET /api/v1/tasks` so operator triage can isolate browser, API, mixed, or dry-run executions without client-side filtering.
[x] Lift terminal execution summary fields onto `GET /api/v1/tasks/{task_id}` so operators do not need to parse the final event for winning-step, cancellation, or aggregate batch context.
[x] Lift scalar execution-plan policy fields onto `GET /api/v1/tasks/{task_id}` so operators do not need the accepted event for basic plan context.
[x] Clarify in the plan that every audit gate requires an external review by a separate reviewer/colleague, not an internal self-check.
[x] Prepare an internal Gate 4 prep brief in `gate4-audit-brief.md` and keep `audit*.md` reserved for external reviewer artifacts.
[x] Record the external Gate 4 review outcome from `audit2.md` and sync roadmap/planning docs with the reviewer recommendations.
[x] Offload blocking orchestration and readiness work from async FastAPI routes via `asyncio.to_thread`, and make the in-memory repository thread-safe enough for that execution model.
[x] Log best-effort event-persistence failures at warning level so observability drops are visible without changing request success semantics.
[x] Add an explicit PostgreSQL connect timeout setting and thread it through repository wiring so storage/readiness paths fail fast on unreachable databases.
[x] Make router and orchestrator fail fast on any step/result cardinality mismatch instead of truncating corrupted execution state silently.
[x] Defer retry schema until a concrete retry policy exists; do not add `attempt_no` or `retry_of_task_id` before a reliability phase chooses the retry model.
[x] Add browser-layer session locking and adapter logging before the first live browser spike so state transitions and failures are observable.
[x] Add an OpenAI-compatible API adapter boundary and distinct API model as a hedge against browser fragility.
[x] Add an application lifespan cleanup hook so future browser automation can release resources on shutdown.
[x] Start browser execution only after the adapter contract and PostgreSQL-backed task/event flow are stable.
[x] Capture live Perplexity DOM reconnaissance in-repo and extract the first centralized selector module for the browser layer.
[x] Add a thin headed Playwright backend behind `BrowserAutomationPort` without changing router/orchestrator boundaries.
[x] Add a manual-gated live Playwright smoke harness so authenticated browser checks can run locally without entering CI.
[x] Add a dedicated-profile bootstrap helper so the first authenticated browser smoke does not depend on copying a live Chrome profile.
[x] Prove one authenticated prompt -> response smoke through the Playwright backend using a dedicated browser profile.
[x] Revisit the default-storage switch now that the first real Playwright smoke is proven, and keep `memory` as the zero-config development default while requiring explicit `postgres` for durable browser runs.
[x] Add a repeatable authenticated Perplexity DOM recon tool so browser UI drift can be captured into dated screenshot/JSON/HTML artifacts before selector changes are attempted.
[x] Continue hardening Playwright logged-in response extraction and selector diagnostics beyond the current composer-scoped model-button path, including post-response recon and structured answer-source verification.
[x] Add account-aware browser model availability handling so `/api/v1/models` does not overpromise static browser models that are absent from the current authenticated Perplexity menu.
[x] Distinguish observed browser-menu presence from verified browser model selection in `/api/v1/models`, using `observed_unverified` plus `last_verified_at` so catalog honesty survives temporary picker drift.
[x] Add a minimal in-process circuit breaker around the browser adapter and surface its state through readiness/health diagnostics without moving browser reliability logic into the router.
[x] Add a lightweight Prometheus-style `/metrics` endpoint using existing readiness, execution-router, storage, and browser-breaker diagnostics rather than introducing a separate metrics subsystem.
[x] Add an operator runbook for the current health/readiness/metrics/browser/storage surfaces so recovery steps are documented before any admin UI exists.
[x] Add structured key-value logging across API route entrypoints and PostgreSQL degraded paths so operator diagnostics extend beyond the orchestrator/browser layers.
[x] Tighten browser runtime cleanup so adapter `close()` leaves the session idle and healthcheck can detect stale session-vs-driver mismatches.
[x] Add a PostgreSQL export CLI that writes JSON task/step/event snapshots so durable-state backup work starts with a simple operator-friendly path.
[x] Add a PostgreSQL import CLI that restores exported task/step/event snapshots by replacing matching task IDs in place.
[x] Expose PostgreSQL task/step/event row counts through storage health so `/metrics` reports durable storage volume alongside in-memory counts.
[x] Add a built-in snapshot checksum to PostgreSQL export/import artifacts so corrupted JSON is rejected before restore.
[x] Make snapshot replacement an explicit storage contract via `replace_task_snapshot(...)` instead of relying on repository duck-typing in the import path.
[x] Harden snapshot import validation so duplicate `task_id`, `step_index`, and event `sequence_no` values are rejected before any restore writes begin.
[x] Add explicit `snapshot_format_version` metadata to PostgreSQL snapshot artifacts so future import compatibility is not inferred only from migration names.
[x] Add `--dry-run` to PostgreSQL snapshot import so operators can validate artifacts and repository health without writing.
[x] Include repository health/schema details in successful import and import `--dry-run` output so the preflight result is self-contained.
[x] Include repository health/schema details in successful export output so snapshot creation and storage preflight share the same operator surface.
[x] Support gzip-compressed PostgreSQL snapshots via `.json.gz` export/import paths so larger backups do not require manual compression steps.
[x] Allow PostgreSQL snapshot import to target specific `task_id` values from a larger artifact and surface missing IDs as a partial restore outcome.
[x] Expose `requested_task_ids` and `exported_task_ids` in PostgreSQL export summaries so partial or deduplicated selection is visible without opening the artifact.
[x] Add an offline snapshot inspection CLI so operators can verify checksum and manifest metadata without a PostgreSQL DSN.
[x] Extend offline snapshot inspection with an `import_ready` compatibility verdict based on checksum, format version, and migration metadata.
[x] Echo source snapshot selection and exported task IDs in successful import output so restore and dry-run results stay self-contained.
[x] Add top-level `step_count` and `event_count` manifest totals to snapshot export, offline inspection, and import summaries so nested volume is visible without opening task payloads.
[x] Expose artifact-level path metadata and checksum status across export/import/inspect summaries so operators can identify the exact snapshot file without re-reading it.
[x] Validate top-level snapshot manifest totals and exported task IDs against nested task payloads, and surface manifest verification statuses in offline inspection/import summaries.
[x] Validate snapshot `selection` metadata against exported and missing task IDs, and surface `selection_status` in offline inspection/import summaries.

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
- 2026-03-18: Snapshot export already supported task selection, but import still forced whole-artifact replay even when the operator only needed one bundle back. Decision: add repeatable `--task-id` filters on import and surface missing IDs via an explicit `partial` result instead of silently restoring everything.
- 2026-03-18: Export selection still required opening the snapshot file to confirm which task bundles actually landed after deduplication or missing-ID filtering. Decision: expose both requested and exported task IDs in the export summary and manifest.
- 2026-03-18: Snapshot checksum and selection metadata were present, but there was still no DSN-free operator path to validate an artifact before considering restore. Decision: add an offline inspection CLI that verifies checksum and reports manifest fields directly from the snapshot file.
- 2026-03-18: Offline snapshot inspection could verify checksum but still left operators guessing whether a file matched the current import contract. Decision: add an explicit `import_ready` verdict plus format/migration status fields to the inspection output.
- 2026-03-18: Import and import `--dry-run` summaries still hid the source artifact manifest unless the operator reran a separate inspect command. Decision: echo source selection and exported-task metadata directly in successful import output.
- 2026-03-18: Snapshot manifests still surfaced only task totals, leaving step and event volume implicit unless the operator opened nested payloads. Decision: add top-level `step_count` and `event_count` across export, inspect, and import summaries.
- 2026-03-18: Snapshot summaries still lacked file-level identity details such as size, compression mode, and explicit checksum status, so operators had to inspect the filesystem or rerun a different command to confirm which artifact they were looking at. Decision: expose artifact-level metadata directly in export/import/inspect output.
- 2026-03-18: Top-level manifest fields in snapshot artifacts were informative but still not enforced, so a hand-edited or truncated file could present misleading totals while leaving nested payloads intact. Decision: validate manifest counts and exported task IDs on import, and expose manifest verification status in offline inspection and import output.
- 2026-03-18: Snapshot `selection` metadata still was not checked against the actual exported and missing task IDs, so a manually edited artifact could claim a different request scope than the nested payloads. Decision: validate `selection` consistency and expose `selection_status` alongside the broader manifest verdict.
- 2026-03-17: The project was still being managed without local git history. Decision: initialize a repository on `main` and ignore generated Python packaging/test artifacts before further iteration.
- 2026-03-17: `MergeStrategy` had been introduced at the request/planning layer, but repository read paths and one event-building branch still fell back to raw strings. Decision: normalize storage reads back to `MergeStrategy` and remove the last internal string comparison.
- 2026-03-17: Browser adapter generic runtime failures were still reported as `provider_unavailable`, conflating internal crashes with upstream availability problems. Decision: map unexpected browser exceptions to `unknown_error` and reserve `provider_unavailable` for actual configuration/provider reachability issues.
- 2026-03-17: `POST /orchestrate` still performed immediate storage readback after a successful write, so accepted tasks could surface as `503` if read paths were degraded. Decision: return submission summaries from the in-memory snapshot produced during submit and leave storage reads to `GET /tasks/{task_id}`.
- 2026-03-17: Task, step, and event records were still carrying raw string enums internally after leaving the DB/API boundaries. Decision: normalize repository read paths back to `TaskStatus`, `StepStatus`, `EventType`, and `FailureCode` so internal comparisons stay typed.
- 2026-03-17: Git on this Windows host still emitted LF/CRLF warnings because repository line-ending policy was implicit. Decision: add `.gitattributes` so line endings are controlled by the repo, not by per-machine Git defaults.
- 2026-03-17: `metadata` was still allowed to carry arbitrary Python objects for non-HTTP callers, leaving JSON-serialization failures to appear only during persistence. Decision: validate JSON-serializability at request-model construction time.
- 2026-03-17: One adapter-name resolver branch was still comparing enum-backed step statuses to string values, which could misclassify completed-plus-cancelled plans as mixed. Decision: finish the enum migration in summary serialization and pin it with a direct response-contract test.
- 2026-03-17: `adapter_hint` still remained a raw string even after `merge_strategy` and status enums were normalized. Decision: move `adapter_hint` onto an enum as well so request validation, planning, and storage reads all share the same typed contract.
- 2026-03-17: `execution_mode` was still stringly-typed across adapters, router aggregation, and repository reads, even though it represents a small fixed vocabulary. Decision: normalize it to an enum before more mixed-backend logic accumulates around string comparisons.
- 2026-03-17: `ModelSpec.timeout_seconds` existed in the registry, but the Mistral adapter still used only a global transport timeout and `/api/v1/models` hid the operational hints entirely. Decision: treat per-model timeout as the execution default and expose timeout/latency/concurrency hints in the model catalog.
- 2026-03-17: `ModelSpec.concurrency_limit` still had no runtime effect, so the catalog exposed a limit the router would never actually honor. Decision: add a small in-process per-model concurrency gate in `ExecutionRouter` and fail fast with `rate_limited` instead of inventing queueing in Phase 1.
- 2026-03-17: After concurrency enforcement, operators still had no visibility into active or saturated models from the standard health surfaces. Decision: expose execution-router concurrency state through readiness and the lightweight health summary instead of waiting for a future metrics system.
- 2026-03-17: Step events still dropped adapter-specific diagnostics even though operator debugging increasingly depends on timeout, auth, driver, and concurrency context. Decision: keep normalized step storage minimal, but include sanitized adapter `details` in `step.completed` and `step.failed` payloads.
- 2026-03-17: Operator task inspection still required already knowing a `task_id`, which is weak for a fresh service shell. Decision: add a summary-only recent-tasks endpoint and keep deep inspection on `GET /tasks/{task_id}`.
- 2026-03-17: A recent-task list without filters still forces manual scanning when operators are looking specifically for failures or real executions. Decision: add low-cardinality `status` and `dry_run` filters now instead of waiting for a full search surface.
- 2026-03-17: A task list that omits adapter and requested-model context still forces extra drill-down for basic triage. Decision: accept light N+1 reads on the operator list path and include `adapter_name` plus `requested_models` in the summary contract.
- 2026-03-17: The new recent-task operator surface was covered on the in-memory path only, leaving room for backend drift on PostgreSQL. Decision: extend the existing gated live-Postgres test suite to cover listing and filters as part of the storage contract.
- 2026-03-17: Operators often care about failure class more than generic `failed` status, and task-level `failure_code` is already normalized and stored. Decision: expose it as a first-class filter on the recent-task list instead of forcing client-side filtering.
- 2026-03-17: Final task events still omitted aggregate router details, forcing operators to reconstruct batch-level routing context from step events alone. Decision: include sanitized batch execution `details` in `task.completed`, `task.failed`, and `task.cancelled` payloads.
- 2026-03-17: Independent review gates were documented, but the exact pre-change timing for each audit was still implicit. Decision: add an explicit `Audit timing` section so autonomous work does not drift past the next required external review point.
- 2026-03-17: A recent-task list that still hides the winning model and quorum short-circuit outcome forces extra `GET /tasks/{id}` calls during basic triage. Decision: add winning-model and cancel-summary fields to the list contract while keeping full event detail on the task view.
- 2026-03-17: Operators can already filter recent tasks by status and failure class, but not by stored execution mode even though that field is normalized and cheap to query. Decision: expose `execution_mode` as another low-cardinality list filter instead of pushing that work to clients.
- 2026-03-17: Final task context still lived only inside the terminal event payload, forcing clients to parse the event stream just to find winning-step or batch-summary data. Decision: surface terminal summary fields at the top level of `GET /tasks/{id}` while keeping the raw events intact.
- 2026-03-17: Even after lifting terminal summary data, operators still needed `task.accepted` just to read scalar execution policy like quorum or merge strategy. Decision: expose the persisted execution-plan scalars directly on `TaskView`.
- 2026-03-17: Gate 4 became the next real implementation boundary once scripted browser execution and operator surfaces were stable. Decision: prepare an internal prep brief, but keep audit artifacts themselves external and stop before any live browser driver code is introduced.
- 2026-03-17: The term `audit` was still ambiguous between external review and internal preparation. Decision: define audit explicitly as a separate external evaluation and reserve `audit*.md` for reviewer-authored outputs.
- 2026-03-17: FastAPI routes were still `async`, but orchestration, storage, and readiness work underneath them remained synchronous and could block the event loop once real adapters or PostgreSQL are used. Decision: offload those route bodies with `asyncio.to_thread` and add locking to the in-memory repository so the local backend remains safe under threaded access.
- 2026-03-17: Best-effort event persistence was intentionally non-blocking, but failures still disappeared without any trace in logs. Decision: keep the request path non-fatal, but emit a warning with task/event context whenever append_event fails.
- 2026-03-17: PostgreSQL connect paths still relied on driver defaults, so readiness and storage operations could hang too long against an unreachable database. Decision: add an explicit connect-timeout setting and pass it through repository construction.
- 2026-03-17: Router and orchestrator loops still used lenient `zip()` semantics between planned steps and execution results, so any corrupted cardinality could be truncated silently in summaries, step rows, or events. Decision: enforce strict cardinality and fail fast anywhere step/result pairs are materialized.
- 2026-03-17: Retry shape remains intentionally unchosen, but the deferral still lived mostly as prose. Decision: pin the absence of `attempt_no` and `retry_of_task_id` with schema and contract tests so Phase 1 cannot drift into an implicit retry model.
- 2026-03-17: External Gate 4 review is now available in `audit2.md`, and the follow-up notes highlight two low-risk browser-layer gaps before the live spike: session-state locking and minimal adapter logging. Decision: treat the boundary review as satisfied and close the low-risk hardening immediately before any Playwright work begins.
- 2026-03-17: Gate 4 recommendations also called for an API hedge against browser fragility. Decision: add one OpenAI-compatible adapter plus a distinct API-only model entry now, without changing the live-browser boundary or reusing browser-model names.
- 2026-03-17: Gate 4 also noted the lack of a shutdown hook for future browser runtime resources. Decision: add a minimal FastAPI lifespan hook now, with adapter-level `close()` delegation, so a Playwright driver can clean up without refactoring the composition root later.
- 2026-03-17: The next browser-spike step now requires live DOM reconnaissance against the real Perplexity UI before any Playwright slice can be implemented safely. Decision: stop before live-browser coding in this session, record the blocker in `questions.md`, and wait for either a recon artifact or an environment with real-site access.
- 2026-03-17: Live Perplexity reconnaissance is now available and shows a split reality: headless Chromium is blocked by Cloudflare, but headed persistent Chrome reaches the app shell. Decision: keep the first Playwright slice headed by default and centralize the discovered selectors in one browser-layer module.
- 2026-03-17: Copying a live Chrome `Default` profile while the source browser is open did not preserve authenticated state because cookie/session stores were locked. Decision: treat a dedicated unlocked user-data directory as the supported input for authenticated live-browser smoke, not the actively used default profile.
- 2026-03-17: The first Playwright slice now exists in code, but it still needs a repeatable manual entrypoint for real authenticated smoke. Decision: add an env-gated unittest that exercises the adapter contract directly and skips cleanly when auth is missing.
- 2026-03-17: The first manual Playwright smoke against a copied profile reached prompt entry but hit a late `Sign in or create an account` overlay during submit. Decision: map that overlay path to `auth_failed`, keep the smoke harness as a skip in that case, and continue treating a dedicated authenticated profile as the prerequisite for the first true end-to-end success.
- 2026-03-17: The blocker is no longer "unknown browser behavior" but "no dedicated authenticated Playwright profile yet". Decision: add a small helper CLI that bootstraps a persistent profile by opening a manual-login browser window against the repo-local default profile directory.
- 2026-03-17: The dedicated-profile authenticated smoke now passes, but Playwright model selection is still best-effort and the driver still requires exclusive access to its profile directory. Decision: keep the profile-lock path explicit in diagnostics, mark the first smoke proof complete, and treat selector hardening plus storage-default review as the next follow-up work.
- 2026-03-17: The authenticated model menu no longer contains every static browser model in the registry; for example, `Kimi K2.5` was absent while `Best`, `Sonar`, `Claude Opus 4.6`, and `Nemotron 3 Super` were present. Decision: fail missing menu options as model mismatch now, and treat account-aware browser model availability as the next catalog-hardening task.
- 2026-03-17: The catalog now consumes the last observed authenticated browser model menu and annotates browser entries as `observed_available`, `observed_unavailable`, or `unknown` instead of pretending the static registry is the same thing as the current account tier. Decision: keep the canonical registry for planning, but expose observation freshness and availability state through `/api/v1/models`.
- 2026-03-17: Hardening work on the live Playwright path confirmed that prompt submission still works from the dedicated authenticated profile, but the current authenticated shell often exposes only `New Thread` / `More` controls and no visible model picker. Decision: keep the browser path honest by surfacing selector-verification evidence and response-source diagnostics, but leave the final model-selection stabilization open until the new UI path is captured.
- 2026-03-18: Based on the follow-up answers in `questions.md`, the live browser path now degrades gracefully when the model picker is unavailable: prompt execution continues, but `model_selection_verified=false`, `model_selection_attempted=false`, and `model_picker_unavailable=true` are surfaced explicitly. Decision: keep prompt transport alive while selector rediscovery remains open, instead of failing the entire browser step.
- 2026-03-18: Browser catalog semantics still conflated "seen in the authenticated menu" with "selection verified in the live driver", which would overstate confidence after the picker disappeared. Decision: expose `observed_unverified` and `last_verified_at` so `/api/v1/models` separates menu observation freshness from proven selection success.
- 2026-03-18: Browser selector rediscovery still depended on ad hoc manual screenshots and console output, which is too lossy for repeated Perplexity UI drift. Decision: add a repeatable headed DOM recon tool that captures dated screenshot, button-inventory, composer-HTML, and manifest artifacts from the dedicated authenticated profile.
- 2026-03-18: Fresh authenticated recon showed that the current model-picker path is no longer `aria-label="Model"` but a composer-scoped menu button labeled with the active model itself, for example `GPT-5.4`. Decision: prefer that composer-scoped current-model button in Playwright, keep the legacy `Model` selector only as a fallback, and focus subsequent hardening on response extraction plus future UI drift detection.
- 2026-03-18: Live model switching is restored, but the response path still often resolves through `body_after_prompt` rather than a stable assistant-message selector. Decision: prefer structured response sources over body fallback when they exist, preserve multiline text instead of flattening it, and surface candidate-length diagnostics so the next DOM hardening step has concrete evidence.
- 2026-03-18: Post-response authenticated recon is now available, and it showed that early body-fallback captures were racing against an active `Stop response` state. Decision: keep a generation-active guard, add prompt-driven response recon artifacts, and verify that the stable answer path resolves through `main div.prose` before considering this browser slice hardened.
- 2026-03-18: The live browser path is now proven enough that repeated infrastructure-grade failures would otherwise hammer the same broken session or driver state. Decision: add a small app-boundary circuit breaker around the browser adapter, count only `provider_unavailable` / `timeout` / `unknown_error`, and expose the breaker state through adapter health instead of pushing browser reliability policy into `ExecutionRouter`.
- 2026-03-18: Operator surfaces were rich for ad hoc inspection, but there was still no scrape-friendly endpoint for dashboards or alerts. Decision: add a small Prometheus-style `/metrics` endpoint backed by existing readiness/router/storage diagnostics instead of introducing a separate metrics store or background sampler in Phase 1/2.
- 2026-03-18: Even with health, readiness, metrics, and task inspection in place, the concrete recovery path for browser profile issues and storage validation still lived only in code and commit history. Decision: add a focused operator runbook before any admin UI exists, so current operators have one stable reference for diagnostics and recovery.
- 2026-03-18: Observability still dropped sharply outside the orchestrator and browser adapters, especially on API route entrypoints and PostgreSQL degraded paths. Decision: add a tiny shared `key=value` log formatter and use it in orchestration routes plus PostgreSQL health/schema warnings instead of introducing a full structured-logging stack now.
- 2026-03-18: Route and storage logs improved operator visibility, but correlating one API request with later task persistence still depended on manually jumping to `task_id`. Decision: propagate `metadata.trace_id` through route and orchestrator lifecycle logs whenever present, so external callers can stitch request, task creation, and event-persistence failures together without a tracing backend.
- 2026-03-18: The browser lifespan hook could release Playwright resources, but the session manager could still remain `active=true`, making stale runtime state look healthier than it was. Decision: make browser `close()` explicitly mark the session idle and degrade adapter health when session and automation launched-state disagree.
- 2026-03-18: PostgreSQL durability had validation tooling and an export path, but still no built-in restore flow that could replay a task snapshot cleanly. Decision: add a task-scoped import CLI that replaces matching `task_id` bundles in place via PostgreSQL cascade semantics instead of pretending an upsert-only merge is a real restore.
- 2026-03-18: `/metrics` exposed storage counts only for the in-memory backend even though operators now have a durable PostgreSQL restore path. Decision: include PostgreSQL row counts in storage health so the same metrics surface can reflect durable-state volume without a separate stats endpoint.
- 2026-03-18: Export/import snapshot files were structurally valid JSON but had no built-in integrity signal, so a truncated or manually edited artifact could still reach restore logic. Decision: stamp each export with `snapshot_sha256` and verify it on import before any database writes.
- 2026-03-18: Snapshot restore semantics had become real enough that the import CLI should not depend on `hasattr(...)` duck-typing against repositories. Decision: promote `replace_task_snapshot(...)` to the explicit storage contract and implement it on both memory and PostgreSQL backends.
- 2026-03-18: Snapshot restore still relied on database or repository write failures to catch duplicate task bundles, step indexes, or event sequence numbers. Decision: reject those duplicate shapes in the import validator before any write path starts.
- 2026-03-18: Snapshot compatibility was still inferred indirectly through migration naming, which is too weak once export/import artifacts become longer-lived. Decision: stamp each snapshot with an explicit `snapshot_format_version` and reject unknown versions on import.
- 2026-03-18: Operators could validate snapshot structure and repository health separately, but the import path still had no built-in no-write rehearsal. Decision: add `gracekelly-import-postgres --dry-run` so the exact restore validator path can run without touching task data.
- 2026-03-18: Even after `--dry-run`, operators still had to infer repository state from separate commands instead of the import result itself. Decision: echo `repository_health` and `repository_schema` on successful import/dry-run so the preflight payload is sufficient on its own.
- 2026-03-18: Export already captured repository health/schema into the snapshot file, but the command summary still hid that state unless the file was opened separately. Decision: include the same repository state in the successful export stdout payload.
- 2026-03-18: Snapshot tooling still assumed plain JSON files, forcing operators to compress or decompress backups manually. Decision: support gzip transparently based on a `.gz` path suffix for both export and import.
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
- 2026-03-17: Added enum-backed `adapter_hint` validation and normalization across request parsing, planning, and repository read paths.
- 2026-03-17: Added enum-backed `execution_mode` normalization across adapters, router aggregation, and repository reads.
- 2026-03-17: Applied per-model timeout hints on the Mistral execution path and exposed timeout, latency class, and concurrency hints through `/api/v1/models`.
- 2026-03-17: Enforced per-model in-process concurrency limits in `ExecutionRouter`, returning `rate_limited` when a model is already saturated and covering slot release with concurrent router tests.
- 2026-03-17: Added execution-plane concurrency diagnostics to readiness and `/health`, including active execution counts, configured model limits, and saturated model IDs.
- 2026-03-17: Added sanitized adapter diagnostics to step events so task retrieval now shows driver/provider/concurrency context through the existing event stream.
- 2026-03-17: Added `GET /api/v1/tasks` backed by both memory and PostgreSQL repositories so operators can inspect recent task summaries before drilling into a specific task.
- 2026-03-17: Extended `GET /api/v1/tasks` with `status` and `dry_run` filters for lightweight operator triage across both memory and PostgreSQL backends.
- 2026-03-17: Enriched `GET /api/v1/tasks` summaries with adapter and requested-model context derived from step/event data, keeping the operator list useful without changing the task table.
- 2026-03-17: Extended the gated live PostgreSQL integration suite to cover recent-task summaries and filter behavior on `/api/v1/tasks`.
- 2026-03-17: Extended `GET /api/v1/tasks` with task-level `failure_code` filtering so operator triage can target specific failure classes across both backends.
- 2026-03-17: Added aggregate execution details to final task events, so task history now preserves batch-level adapter, quorum, cancellation, and failure-summary context alongside per-step diagnostics.
- 2026-03-17: Clarified audit timing in the implementation plan, including which review gate is next and when an external audit becomes mandatory.
- 2026-03-17: Extended `GET /api/v1/tasks` summaries with winning-model and short-circuit context so operators can spot quorum outcomes from the list view on both memory and PostgreSQL backends.
- 2026-03-17: Extended `GET /api/v1/tasks` with `execution_mode` filtering so operator triage can isolate browser, API, mixed, or dry-run executions across both backends.
- 2026-03-17: Lifted terminal execution summary fields onto `GET /api/v1/tasks/{task_id}`, so winning-step, cancellation, and aggregate batch details are available without parsing the final event payload.
- 2026-03-17: Lifted persisted execution-plan scalars onto `GET /api/v1/tasks/{task_id}`, so quorum and merge-policy context are visible without parsing the accepted event.
- 2026-03-17: Prepared `gate4-audit-brief.md` as the internal Gate 4 prep note, clarified that `audit*.md` is reserved for external reviewer output, and paused further browser-runtime work pending independent audit.
- 2026-03-17: Offloaded blocking orchestration and readiness work from async HTTP routes into worker threads and added HTTP regression coverage plus in-memory repository locking for the new access pattern.
- 2026-03-17: Added warning logging for best-effort event persistence failures and covered the behavior directly in orchestrator tests.
- 2026-03-17: Added an explicit PostgreSQL connect-timeout setting, wired it through app configuration and repository construction, documented it in `.env.example` / README, and covered env parsing plus repository wiring in tests.
- 2026-03-17: Ingested the external Gate 4 review from `audit2.md`, updated the phased roadmap to match actual progress, and added browser-layer logging plus session-state locking ahead of the first live driver slice.
- 2026-03-17: Added an OpenAI-compatible API adapter, wired it into settings and app composition, exposed a distinct `GPT-5.4 API` catalog model, and covered the new path in adapter, HTTP, config, and main wiring tests.
- 2026-03-17: Added a FastAPI lifespan cleanup hook plus adapter-level close delegation, so future browser automation drivers can release resources cleanly on shutdown without changing the app boundary.
- 2026-03-17: Captured real Perplexity DOM reconnaissance in `docs/perplexity-dom-recon.md`, extracted centralized browser selectors, added a thin headed Playwright backend plus config wiring, and covered the new browser path with unit tests.
- 2026-03-17: Added `tests/test_playwright_live.py` as a manual-gated authenticated browser smoke so the new Playwright path can be exercised locally without changing the default CI suite.
- 2026-03-17: Tightened the thin Playwright slice after the first live smoke by making model selection best-effort, mapping late sign-in overlays to `auth_failed`, and fixing Playwright shutdown to stop the runtime cleanly.
- 2026-03-17: Added `gracekelly-create-perplexity-profile` plus direct tool coverage so a dedicated persistent Playwright profile can be created without copying a live Chrome `Default` directory.
- 2026-03-17: Passed the first authenticated Playwright smoke against a dedicated Perplexity profile and added explicit browser-profile-in-use diagnostics so the runtime no longer reports a generic crash when the same profile is already open in Chrome.
- 2026-03-17: Hardened Playwright model-menu handling with authenticated recon data, moved the live smoke onto `GPT-5.4`, and documented that `memory` remains the development default while durable browser runs should opt into PostgreSQL explicitly.
- 2026-03-18: Changed the Playwright path to degrade gracefully when the model picker is unavailable, while carrying explicit `model_picker_unavailable` diagnostics and verified-selection timestamps into `/api/v1/models` as `observed_unverified` / `last_verified_at`.
- 2026-03-18: Added `gracekelly-capture-perplexity-recon`, a repeatable headed recon CLI that writes dated authenticated Perplexity screenshots, toolbar inventories, composer HTML, and a manifest bundle for selector-rediscovery work.
- 2026-03-18: Re-ran authenticated recon, discovered the live composer-scoped current-model button path, updated Playwright to use it first, tightened debug inventories to the composer controls, and passed a live smoke that switched from `GPT-5.4` to `Claude Sonnet 4.6` with `model_selection_verified=true`.
- 2026-03-18: Hardened Playwright response picking so structured selectors outrank `body_after_prompt`, multiline answers are preserved, and execution details now include candidate lengths plus an explicit `response_used_body_fallback` flag; the live smoke still completes on `Claude Sonnet 4.6`.
- 2026-03-18: Extended `gracekelly-capture-perplexity-recon` with post-response prompt mode, captured the final answer DOM, added a generation-active guard around response picking, and revalidated the live adapter path with `response_source=main div.prose` and `response_used_body_fallback=false` on `Claude Sonnet 4.6`.
- 2026-03-18: Added a configurable in-process circuit breaker wrapper around `browser.perplexity`, wired it through app composition, exposed breaker state in adapter health/readiness, and expanded the local suite to `125 passed, 4 skipped`.
- 2026-03-18: Added a lightweight Prometheus-style `/metrics` endpoint with readiness, component-state, execution saturation, storage-count, and browser circuit-breaker gauges, plus direct HTTP smoke coverage; local suite now passes `128` tests with `4` optional skips.
- 2026-03-18: Added `docs/operator-runbook.md` covering startup checks, readiness/metrics interpretation, browser triage, circuit-breaker recovery, storage validation, and task-inspection workflow so the current operator surface is usable without an admin UI.
- 2026-03-18: Added `logging_utils.py` plus structured `key=value` logs for orchestration routes, degraded readiness snapshots, and PostgreSQL health/schema failures, with regression coverage; local suite now passes `133` tests with `4` optional skips.
- 2026-03-18: Extended the new structured-log path so `metadata.trace_id` flows through orchestration-route and orchestrator lifecycle logs, including task submission and event-persistence warnings; local suite now passes `134` tests with `4` optional skips.
- 2026-03-18: Tightened browser cleanup semantics so adapter shutdown now marks the session idle and adapter health degrades on session/runtime mismatch, closing the stale-state gap left after the first lifespan hook; local suite now passes `136` tests with `4` optional skips.
- 2026-03-18: Added `gracekelly-export-postgres`, a JSON snapshot CLI for PostgreSQL task, step, and event data with health/schema manifest metadata, and covered it with unit tests.
- 2026-03-18: Added `gracekelly-import-postgres`, a PostgreSQL restore CLI that replays exported task/step/event bundles by replacing matching task IDs in place, and documented the task-scoped restore semantics in the runbook and README.
- 2026-03-18: Extended PostgreSQL storage health with task/step/event row counts so `/metrics` now exposes durable-state volume through the same gauges previously limited to the in-memory backend.
- 2026-03-18: Added `snapshot_sha256` integrity stamping to PostgreSQL exports and checksum verification on import, with regression coverage for both the happy path and checksum-mismatch rejection.
- 2026-03-18: Promoted snapshot replacement to an explicit repository contract and removed the remaining duck-typed restore branch from the import CLI, with direct in-memory replacement coverage.
- 2026-03-18: Hardened snapshot import validation to reject duplicate task bundles, duplicate step indexes, and duplicate event sequence numbers before restore writes begin.
- 2026-03-18: Added `snapshot_format_version` and `gracekelly_version` to PostgreSQL snapshot artifacts and made import reject mismatched format versions before restore begins.
- 2026-03-18: Added `--dry-run` to `gracekelly-import-postgres`, so restore validation and target-repository checks can be rehearsed without writing any task, step, or event rows.
- 2026-03-18: Extended successful import output with `repository_health` and `repository_schema`, making the import dry-run result a self-contained preflight report.
- 2026-03-18: Extended successful export output with `repository_health` and `repository_schema`, so snapshot creation and storage preflight now expose the same operator-facing repository summary.
- 2026-03-18: Added transparent `.json.gz` support to PostgreSQL snapshot export/import paths, with regression coverage for compressed output and compressed input.
- 2026-03-18: Added selective `--task-id` filtering to `gracekelly-import-postgres`, including partial-result reporting when only some requested task bundles are present in the snapshot artifact.
- 2026-03-18: Extended PostgreSQL export artifacts and summaries with explicit requested/exported task ID lists, so partial or deduplicated selection is visible without inspecting nested task payloads.
- 2026-03-18: Added `gracekelly-inspect-snapshot`, an offline manifest/checksum inspection CLI for JSON or `.json.gz` snapshot artifacts, with regression coverage and runbook documentation.
- 2026-03-18: Extended offline snapshot inspection with `format_status`, `migration_status`, and `import_ready`, so artifact compatibility can be evaluated before any restore dry-run or DSN setup.
- 2026-03-18: Extended successful import output with source manifest fields such as `source_selection` and `source_exported_task_ids`, keeping restore and dry-run results self-contained.
- 2026-03-18: Added top-level `step_count` and `event_count` manifest totals to snapshot export plus inspect/import summaries, so nested durable-state volume is visible without inspecting task bodies.
- 2026-03-18: Added artifact-level metadata such as compression mode, file size, and explicit checksum status across snapshot export/import/inspect summaries, making the operator surface fully traceable to a concrete artifact.
- 2026-03-18: Added manifest validation plus `manifest_status` reporting for snapshot artifacts, so mismatched top-level totals or `exported_task_ids` are caught before restore and called out in offline inspection.
- 2026-03-18: Extended manifest validation to cover `selection` metadata and added `selection_status` to inspect/import summaries, so reported request scope cannot drift from the actual task bundles in the artifact.
