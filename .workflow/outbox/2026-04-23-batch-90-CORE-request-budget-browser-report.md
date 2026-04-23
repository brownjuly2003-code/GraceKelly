# CORE-request-budget-browser

Status: success

Summary:
- Added `src/gracekelly/core/budget.py` with `BudgetAcquireResult` and `RequestBudgetTracker`.
- `RequestBudgetTracker` enforces per-task and rolling per-hour browser submit budgets, is thread-safe, exposes `snapshot()`, and stays no-op when both limits are `None`.
- `ExecutionRouter` now checks request budget only on `ExecutionBackend.BROWSER` before browser adapter dispatch, returns `FailureCode.RATE_LIMITED` with `budget_exceeded_kind` and `budget_usage`, and exposes budget state in `healthcheck()`.
- API dispatch path is unchanged and does not consume browser budget.
- Budget `RATE_LIMITED` remains outside the fallback trigger set, so browser budget exhaustion does not fall through to API fallback.

Env keys:
- `GRACEKELLY_MAX_BROWSER_SUBMITS_PER_TASK`
  Default: `None` -> unlimited / backward-compatible.
- `GRACEKELLY_MAX_BROWSER_SUBMITS_PER_HOUR`
  Default: `None` -> unlimited / backward-compatible.
- Both parse as optional positive integers. Non-integer, `0`, or negative values log a warning and fall back to `None`.

Healthcheck snapshot shape:
- `"budget": {"per_task_limit": <int|None>, "per_hour_limit": <int|None>, "active_task_counts": {<task_id>: <count>}, "hourly_submits": <int>}`
- Verified example from the new regression: `{"per_task_limit": 2, "per_hour_limit": 5, "active_task_counts": {}, "hourly_submits": 0}`

New tests in `tests/test_request_budget.py`:
- `test_tracker_allows_all_when_limits_none`: unlimited mode stays permissive and no-op.
- `test_tracker_enforces_per_task_limit`: the fourth acquire on the same task is rejected with `per_task`.
- `test_tracker_per_task_limit_is_per_task_not_global`: per-task counts do not block other task IDs.
- `test_tracker_enforces_per_hour_limit`: the sixth acquire in the same rolling hour is rejected with `per_hour`.
- `test_tracker_hourly_window_expires`: entries older than `3600.0` seconds are evicted from the rolling window.
- `test_tracker_both_limits_earliest_reason_wins`: per-task rejection wins before per-hour when task quota is hit first.
- `test_budget_env_defaults_to_none`: both new env-backed limits default to `None`.
- `test_budget_env_reads_positive_ints`: positive env values are parsed into settings.
- `test_budget_env_non_int_falls_back_to_none_and_logs_warning`: invalid strings warn and disable the limit.
- `test_budget_env_non_positive_falls_back_to_none_and_logs_warning`: `0` and negative values warn and disable the limit.
- `test_router_budget_exceeded_returns_rate_limited`: browser budget rejection returns `RATE_LIMITED` and blocks adapter execution.
- `test_router_budget_not_applied_to_api_backend`: API requests bypass browser budget accounting.
- `test_router_budget_rate_limited_does_not_trigger_fallback`: budget exhaustion does not trigger model fallback.
- `test_router_healthcheck_includes_budget_snapshot`: router healthcheck includes the budget snapshot and default settings wiring.

Red phase:
- Initial `tests/test_request_budget.py` collection failed with `ModuleNotFoundError: No module named 'gracekelly.core.budget'`.

Verification:
- R1: `.venv\Scripts\python.exe -m pytest --tb=short -q` -> `2637 passed / 0 failed / 6 skipped / 11 subtests passed`
- R2: `.venv\Scripts\python.exe -m pytest --tb=short -q --cov=src\gracekelly --cov-report=term` -> `2637 passed / 0 failed / 6 skipped`, total coverage `97%` (`+1%` vs `.workflow/state/test-baseline.json`)
- R3: `.venv\Scripts\python.exe -m pytest --tb=short -q tests/test_request_budget.py tests/test_router.py tests/test_router_fallback.py` -> `49 passed / 0 failed / 0 skipped`
- R4: scoped verbose pytest run collected `49` tests and emitted no warnings/errors/deprecations from pytest itself
- R5 kill check:
  - `test_tracker_enforces_per_task_limit` killed `task_submits >= self._per_task_limit` by failing when mutated to `>`
  - `test_budget_env_non_positive_falls_back_to_none_and_logs_warning` killed `value <= 0` by failing when mutated to `< 0`
  - `test_router_budget_exceeded_returns_rate_limited` killed the router budget gate by failing when the guard was bypassed
- `tests/test_router.py` and `tests/test_router_fallback.py` both remained green in scoped regression; current collected counts are `26` and `9` respectively in this repo state, plus `14` new tests in `tests/test_request_budget.py`
- `ruff check src tests` -> clean
- `.venv\Scripts\python.exe -m mypy src` -> `Success: no issues found in 106 source files`

Scope:
- `src/gracekelly/core/budget.py`
- `src/gracekelly/core/router.py`
- `src/gracekelly/config.py`
- `tests/test_request_budget.py`
