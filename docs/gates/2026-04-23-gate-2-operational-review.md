# Gate 2 - Operational readiness self-review

Date: 2026-04-23
Reviewer: CC/CX internal self-review (single-user local deploy scope)
HEAD: `beb8a0e`

## Scope of review

`docs/phased-roadmap.md:33-35` kept Gate 2 open for "operational review for readiness semantics".
This review checks whether liveness/readiness probes, metrics, startup/shutdown handling, structured
logs, error surfacing, and operator-facing docs are adequate for a single-user local deployment.

## Criteria and verification

1. Criterion: `/healthz/live` returns HTTP 200 without external dependencies.
   - How verified: `src/gracekelly/api/routes/health.py:374-376` returns a literal `{"status": "ok"}`
     and does not touch storage, adapters, or the execution router.
   - Evidence: `tests/test_healthz_live.py:16-25`.
   - Status: PASS.

2. Criterion: `/healthz/ready` gates on browser-adapter and storage readiness.
   - How verified: `src/gracekelly/api/routes/health.py:379-384` only checks whether
     `state.task_repository` is present and returns `{"status": "ok"}` otherwise.
     Component-level browser/execution gating actually lives on `/api/v1/readiness` via
     `src/gracekelly/api/routes/health.py:387-407` and `src/gracekelly/core/readiness.py:24-53`.
   - Evidence: `tests/test_healthz_live.py:27-47`; `tests/test_http_api.py:90-105`;
     `tests/test_http_api.py:137-178`.
   - Status: FAIL.

3. Criterion: `/metrics` exposes runtime state and does not break when a component is degraded.
   - How verified: `src/gracekelly/api/routes/health.py:110-286,410-423` emits readiness,
     execution, storage, circuit-breaker, and request-metric gauges from the runtime snapshot.
   - Evidence: `tests/test_http_api.py:122-136`; `tests/test_http_api.py:180-231`;
     `tests/test_http_api.py:233-261`.
   - Status: PASS.

4. Criterion: the startup path initialises runtime state and shutdown flushes/closes resources.
   - How verified: `src/gracekelly/main.py:358-405` builds the task repository, adapters,
     executors, and router during app creation; `src/gracekelly/main.py:271-311` validates the
     browser profile, refreshes the model catalog on startup, and closes the browser adapter,
     executors, and PostgreSQL pool on shutdown.
   - Evidence: `tests/test_app_startup.py:112-131`; `tests/test_app_startup.py:135-183`;
     `tests/test_main.py:126-154`.
   - Status: PASS.

5. Criterion: structured logging exists for major operational state transitions.
   - How verified: request/acceptance logs exist in
     `src/gracekelly/api/routes/orchestrate.py:258-329`; fallback attempt/success/failure logs live
     in `src/gracekelly/core/router.py:335-452`; model-catalog and shutdown logs live in
     `src/gracekelly/main.py:251-311`; browser-auth diagnostics are documented through the
     `browser_auth_unknown` operator path.
   - Evidence: `tests/test_http_api.py:609-630`; `tests/test_router_fallback.py:600-664`;
     `tests/test_app_startup.py:221-238`; `docs/operator-runbook.md:124-137`;
     `.workflow/outbox/2026-04-23-batch-95-CLEANUP-mypy-and-fallback-logging-report.md:16-22`.
   - Status: PASS.

6. Criterion: auth/budget/fallback failures are surfaced to operators at sync and task-polling
   surfaces.
   - How verified: sync `/api/v1/orchestrate` maps browser auth failure to HTTP 503 with
     `model_auth_required` in `src/gracekelly/api/routes/orchestrate.py:296-310`; the upload route
     mirrors that at `492-506`; task views include `failure_code`, `failure_message`,
     `retry_of_task_id`, and `execution_details` via `src/gracekelly/schemas.py:133-174,223-283`.
   - Evidence: `tests/test_http_api.py:1479-1520`; `tests/test_http_api.py:1523-1571`;
     `tests/test_http_api.py:1573-1601`; `tests/test_ui_auth_banner.py:69-117`;
     `tests/test_ui_auth_banner.py:120-173`; `tests/test_request_budget.py:241-283`;
     `tests/test_request_budget.py:314-365`; `tests/test_router_fallback.py:156-203`.
   - Status: PASS.

7. Criterion: operator observability documentation is current and discoverable.
   - How verified: the runbook documents primary endpoints, readiness/metrics interpretation,
     browser failure handling, storage validation, and live-smoke operator flow.
   - Evidence: `docs/operator-runbook.md:58-118`; `docs/operator-runbook.md:120-215`;
     `docs/operator-runbook.md:290-357`.
   - Status: PASS.

## Findings / deviations

- `/healthz/ready` is a storage-only shallow probe. Full browser/execution readiness currently lives
  on `/api/v1/readiness`, so the Gate 2 criterion is not satisfied as written.

## Verdict

PASS with conditions for single-user local deployment scope

The conditioned pass assumes operators treat `/api/v1/readiness` as the semantic readiness endpoint
and treat `/healthz/ready` as a minimal storage probe until a follow-up aligns the shallow probe
with browser/execution readiness expectations.

## Limitations of this review

Not covered: multi-user concurrency, cluster deployment, external SLA contracts, and disaster
recovery drills. Those require a deployment context beyond the single-user local scope reviewed here.

## Signature

Reviewed by CC (Claude Code orchestrator) on 2026-04-23, commit pending.
