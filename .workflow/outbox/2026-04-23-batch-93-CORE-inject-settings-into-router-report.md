# CORE-inject-settings-into-router

Status: success

Summary:
- `ExecutionRouter` now accepts `settings: Settings | None = None`, stores `self._settings`, and keeps `_default_settings` only as the backward-compatible fallback for direct instantiation.
- Router budget wiring, timeout lookup, and fallback gating now read from `self._settings`, so runtime behavior matches the injected app configuration instead of the module-global singleton.
- `create_app()` now passes `settings=active_settings` into `ExecutionRouter`, closing the audit-reported config leak between `app.state.settings` and `app.state.execution_router`.
- Rewrote 4 existing tests from module-global patching to explicit injection, added 3 new injection regressions, and left 6 older fallback tests patch-based to preserve `_default_settings` backward-compat coverage.

Red phase:
- The new reproducer `tests/test_request_budget.py::RequestBudgetRouterTests::test_create_app_propagates_settings_to_router` failed before the `main.py` fix with `AssertionError: None != 3`, confirming the audit bug: `create_app(Settings(...))` set `app.state.settings`, but the router healthcheck still exposed `budget.per_task_limit=None`.

Injected-settings coverage:
- Existing tests rewritten to explicit injection:
  - `test_router_budget_rate_limited_does_not_trigger_fallback`
  - `test_router_healthcheck_includes_budget_snapshot`
  - `test_fallback_disabled_by_default_even_with_fallback_id`
  - `test_fallback_triggers_on_provider_unavailable_when_enabled`
- New explicit-injection regressions:
  - `test_router_uses_injected_settings_for_budget`
  - `test_router_uses_injected_settings_for_fallback`
  - `test_create_app_propagates_settings_to_router`
- Existing patch-based fallback coverage intentionally kept for 6 scenarios that still exercise direct-instantiation backward compatibility.

Healthcheck evidence:
- After the fix, `create_app(Settings(max_browser_submits_per_task=3, enable_model_fallback=True)).state.execution_router.healthcheck()["budget"]` returns `{"per_task_limit": 3, "per_hour_limit": null, "active_task_counts": {}, "hourly_submits": 0}` at the assertion point in the regression test.

Verification:
- R1: `.venv\Scripts\python.exe -m pytest --tb=short -q` -> `2650 passed / 0 failed / 6 skipped / 11 subtests passed`
- R2: `.venv\Scripts\python.exe -m pytest --tb=short -q --cov=gracekelly --cov-report=term` -> `2650 passed / 0 failed / 6 skipped`, total coverage `97%` (`+1%` vs `.workflow/state/test-baseline.json`)
- R3: `.venv\Scripts\python.exe -m pytest --tb=short -q tests/test_request_budget.py tests/test_router_fallback.py tests/test_router.py tests/test_main.py` -> `67 passed / 0 failed / 0 skipped`
- R4: `.venv\Scripts\python.exe -m pytest --tb=short -vv tests/test_request_budget.py tests/test_router_fallback.py tests/test_router.py tests/test_main.py` -> `67 passed`; grep for `WARNING|ERROR|DeprecationWarning|PytestDeprecationWarning|warning summary|error summary` returned no matches
- R5 kill check:
  - `test_router_uses_injected_settings_for_budget` killed `per_task_limit=self._settings.max_browser_submits_per_task` when temporarily mutated back to `_default_settings.max_browser_submits_per_task`
  - `test_router_uses_injected_settings_for_fallback` killed `if not self._settings.enable_model_fallback:` when temporarily mutated back to `_default_settings.enable_model_fallback`
  - `test_create_app_propagates_settings_to_router` killed `settings=active_settings` when temporarily removed from `ExecutionRouter(...)` in `create_app()`
- `ruff check src tests` -> clean
- `.venv\Scripts\python.exe -m mypy src --strict` -> `Success: no issues found in 106 source files`

Scope:
- `src/gracekelly/core/router.py`
- `src/gracekelly/main.py`
- `tests/test_request_budget.py`
- `tests/test_router_fallback.py`
