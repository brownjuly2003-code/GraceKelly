## Task: AUTH-perplexity-overlay
goal: Make Perplexity auth-overlay detection resolve to a stable auth outcome instead of a browser click timeout during browser-backed orchestration.
scope: src/gracekelly/adapters/browser/perplexity.py, src/gracekelly/adapters/browser/playwright_driver.py, src/gracekelly/api/routes/orchestrate.py, tests/test_browser_adapter.py, tests/test_playwright_driver.py, tests/test_http_api.py
done_when: [repro documented against uvicorn on http://127.0.0.1:8012/ using POST /api/v1/orchestrate/stream with a browser-backed default model, overlay detection yields either a persistent authenticated session or an explicit 503 model_auth_required response, no browser click timeout remains when the login modal blocks pointer events]
visual_check: false
blocked_by: []

Notes
- Observed live symptom on 2026-04-20: `POST /api/v1/orchestrate/stream` returned `200`, then `GET /api/v1/tasks/{task_id}` showed `status=failed` because `<div data-testid="login-modal">...</div>` intercepted pointer events during model selection.
- Expected behavior: fail fast with an explicit auth outcome from the adapter (`503 model_auth_required`) instead of timing out on `Locator.click`.
