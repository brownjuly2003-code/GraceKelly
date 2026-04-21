# DIAG-orchestrate-500
Closure status: partial — see decisions/2026-04-21-diag-orchestrate-500.md

## Files changed
- `src/gracekelly/api/routes/orchestrate.py`
- `src/gracekelly/adapters/browser/playwright_driver.py`
- `src/gracekelly/core/orchestrator.py`
- `tests/test_http_api.py`
- `tests/test_orchestrator.py`
- `tests/test_playwright_driver.py`

## Scope reconcile
- Kept `src/gracekelly/core/orchestrator.py` and `tests/test_orchestrator.py` in DIAG because the route-level diagnosis depends on browser-only live plans executing inline inside `submit_snapshot()`, so the repro exercises the real browser adapter failure path and records `task.failed` instead of masking it behind router dispatch.

## Tests: N passed / coverage
- `106 passed`:
  - `tests/test_http_api.py`
  - `tests/test_browser_adapter.py`
  - `tests/test_playwright_driver.py`
  - `tests/test_playwright_threading.py`
  - `tests/test_orchestrate_timeout.py`
- Focused regressions added first, confirmed red, then fixed:
  - route-level unknown exception -> traceable `500`
  - Playwright model selection blocked by sign-in overlay -> `PermissionError`

## ruff/mypy status
- `ruff check src/gracekelly/api/routes/orchestrate.py src/gracekelly/adapters/browser/playwright_driver.py tests/test_http_api.py tests/test_playwright_driver.py` -> green
- `python -m mypy src/gracekelly/api/routes/orchestrate.py src/gracekelly/adapters/browser/playwright_driver.py` -> green

## Traceback / screenshots
- On `2026-04-20`, exact UI repro against a server started with system Python + installed Playwright on `http://127.0.0.1:8012/` did **not** return HTTP `500`.
- Actual network/result chain:
  - `POST /api/v1/orchestrate/stream` -> `200`
  - `GET /api/v1/tasks/{task_id}` -> `200`, task status `failed`
- Root cause observed from logs:

```text
Browser execution failed: Locator.click: Timeout 5000ms exceeded.
...
<div data-testid="login-modal">…</div> subtree intercepts pointer events
```

- Related non-stream repro also showed the same auth gate in a different form:

```text
Requested browser model 'Claude Sonnet 4.6' but UI shows 'Access the top AI models'.
```

- Conclusion: current live failure is browser auth/login overlay during model selection, not an unhandled route crash.

## What changed
- Added explicit fallback handling in `orchestrate` and `orchestrate/upload`:
  - `logger.exception(...)`
  - structured `500` payload with `code=unknown_error`, `message`, `trace_id`
  - preserves existing `422/501/503/504` paths by re-raising `HTTPException`
- Fixed Playwright model-selection path to detect signed-out overlays during picker interaction and raise `PermissionError` instead of falling through as a generic crash.

## Open questions for CC
- The batch repro says "submit any prompt with default model -> 500", but on `2026-04-20` in this workspace I reproduced `200 + task.failed`, not `500`.
- If CC still sees `500`, verify:
  - which Python environment starts Uvicorn
  - which port/UI instance is being exercised
  - whether a different local branch/build is serving static assets
