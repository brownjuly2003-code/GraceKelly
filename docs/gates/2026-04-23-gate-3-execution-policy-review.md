# Gate 3 - Execution policy self-review

Date: 2026-04-23
Reviewer: CC/CX internal self-review (single-user local deploy scope)
HEAD: `beb8a0e`

## Scope of review

`docs/phased-roadmap.md:33-35` kept Gate 3 open for "execution-policy review for defaults and
failure handling". This review checks per-model timeouts, concurrency limits, fallback behavior,
request budget rules, retry linkage, injected settings flow, failure taxonomy, and saturation
visibility for the single-user local deployment path.

## Criteria and verification

1. Criterion: per-model timeouts are defined in `ModelSpec.timeout_seconds` for all browser and API
   models.
   - How verified: `src/gracekelly/core/models.py:8-20` defines the contract; API defaults are set
     at `48-85`; browser defaults are set at `148-171`.
   - Evidence: `tests/test_http_api.py:341-367`.
   - Status: PASS.

2. Criterion: `ModelConcurrencyGate` plus per-model `concurrency_limit` is enforced in the router.
   - How verified: `src/gracekelly/core/concurrency.py:6-35` implements guarded acquire/release;
     `src/gracekelly/core/router.py:48-57` snapshots per-model limits; `498-529` enforces the
     limit and returns `RATE_LIMITED` when a slot is unavailable.
   - Evidence: `tests/test_concurrency.py:13-54`; `tests/test_concurrency.py:56-99`;
     `tests/test_stress.py:25-41`.
   - Status: PASS.

3. Criterion: model fallback is single-shot, limited to explicit failure codes, and env-gated off by
   default.
   - How verified: `src/gracekelly/core/router.py:329-452` gates fallback behind
     `self._settings.enable_model_fallback`, allows only `AUTH_FAILED`, `PROVIDER_UNAVAILABLE`, and
     `TIMEOUT`, and rewrites the result once per failed step; `src/gracekelly/config.py:113-115`
     and `204-205` define the default-off setting.
   - Evidence: `tests/test_router_fallback.py:108-154`; `tests/test_router_fallback.py:156-257`;
     `tests/test_router_fallback.py:262-357`; `tests/test_router_fallback.py:506-564`;
     `tests/test_router_fallback.py:600-715`.
   - Status: PASS.

4. Criterion: request budget is browser-only, tracks per-task plus rolling-hourly limits, and is
   env-gated to unlimited by default.
   - How verified: `src/gracekelly/core/budget.py:20-97` implements per-task and rolling-hour
     tracking; `src/gracekelly/core/router.py:49-52,184-187,273-287` wires the tracker only to the
     browser path and exposes the snapshot; `src/gracekelly/config.py:97-98,173-174` defines the
     env-backed defaults.
   - Evidence: `tests/test_request_budget.py:116-189`; `tests/test_request_budget.py:192-238`;
     `tests/test_request_budget.py:241-313`.
   - Status: PASS.

5. Criterion: `RATE_LIMITED` from request budget/concurrency does not trigger fallback.
   - How verified: `src/gracekelly/core/router.py:346-360` excludes `RATE_LIMITED` from the
     fallback trigger set, while budget/concurrency failures are emitted at `474-529`.
   - Evidence: `tests/test_request_budget.py:314-365`; `tests/test_router_fallback.py:359-409`.
   - Status: PASS.

6. Criterion: task-level retry is exposed via `retry_of_task_id` and `POST /api/v1/tasks/{task_id}/retry`.
   - How verified: `src/gracekelly/api/routes/orchestrate.py:742-813` defines the retry route and
     passes `retry_of_task_id`; `src/gracekelly/schemas.py:223-283` exposes the linkage on task
     views.
   - Evidence: `tests/test_http_api.py:1573-1601`.
   - Status: PASS.

7. Criterion: injected `Settings(...)` flow reaches `ExecutionRouter` instead of relying on the
   module-global config.
   - How verified: `src/gracekelly/main.py:314-405` builds the app from explicit settings and
     injects them into `ExecutionRouter`; `src/gracekelly/core/router.py:33-57` stores
     `self._settings` and uses it for budget/fallback behavior.
   - Evidence: `tests/test_request_budget.py:366-443`; `tests/test_router_fallback.py:156-203`.
   - Status: PASS.

8. Criterion: `FailureCode` covers auth, model mismatch, provider outage, timeout, rate limit,
   storage failure, and unknown error.
   - How verified: `src/gracekelly/core/contracts.py:13-20` defines the taxonomy.
   - Evidence: `tests/test_contracts.py:39-47`.
   - Status: PASS.

9. Criterion: health/readiness surfaces expose saturation and budget state for operators.
   - How verified: `src/gracekelly/core/router.py:273-287` returns `active_by_model`,
     `model_limits`, `saturated_models`, and `budget`; readiness and metrics consume that payload in
     `src/gracekelly/api/routes/health.py:45-61,120-188`.
   - Evidence: `tests/test_request_budget.py:413-427`; `tests/test_http_api.py:99-105`;
     `tests/test_http_api.py:122-136`.
   - Status: PASS.

## Findings / deviations

No deviations identified.

## Verdict

PASS for single-user local deployment scope

## Limitations of this review

Not covered: adversarial load testing, production-grade SLO tracking, and multi-tenant quota
fairness. Those are out of scope for the single-user local deployment path reviewed here.

## Signature

Reviewed by CC (Claude Code orchestrator) on 2026-04-23, commit pending.
