# CORE-model-fallback-policy

Status: success

Summary:
- Added `fallback_model_id: str | None = None` to `ModelSpec`.
- Browser catalog now sets `claude-sonnet-4-6 -> claude-sonnet-4-6-api` and `gpt-5-4 -> gpt-5-4-api`.
- `ExecutionRouter._dispatch_step` now performs a single fallback retry when `GRACEKELLY_ENABLE_MODEL_FALLBACK=true` and the primary failure code is `auth_failed`, `provider_unavailable`, or `timeout`.
- Fallback results now enrich `details` with `fallback_used`, `fallback_from_model`, `fallback_reason`, and `primary_failure_message`.
- Default behavior is unchanged when the env flag is off.

Fallback-enabled catalog entries:
- `claude-sonnet-4-6` -> `claude-sonnet-4-6-api`
- `gpt-5-4` -> `gpt-5-4-api`

New tests in `tests/test_router_fallback.py`:
- `test_fallback_disabled_by_default_even_with_fallback_id`
- `test_fallback_triggers_on_auth_failed_when_enabled`
- `test_fallback_triggers_on_provider_unavailable_when_enabled`
- `test_fallback_triggers_on_timeout_when_enabled`
- `test_fallback_does_not_trigger_on_rate_limited`
- `test_fallback_does_not_trigger_on_model_mismatch`
- `test_fallback_does_not_trigger_without_fallback_model_id`
- `test_fallback_no_second_level_on_fallback_failure`
- `test_model_spec_fallback_field_serializes`

Red phase:
- `tests/test_router_fallback.py` failed 9/9 before implementation because `ModelSpec` did not yet expose `fallback_model_id`.

Verification:
- Targeted new tests: `9 passed`
- R3: `35 passed / 0 failed / 0 skipped` (`.venv\Scripts\python.exe -m pytest tests/test_router_fallback.py tests/test_router.py`)
- R1: `2623 passed / 0 failed / 6 skipped` (`.venv\Scripts\python.exe -m pytest`)
- `ruff check src tests` -> clean
- `.venv\Scripts\python.exe -m mypy src` -> `Success: no issues found in 105 source files`

Scope:
- `src/gracekelly/core/models.py`
- `src/gracekelly/core/router.py`
- `src/gracekelly/config.py`
- `tests/test_router_fallback.py`
