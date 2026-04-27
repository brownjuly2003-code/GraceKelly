# GraceKelly: глобальный аудит Codex от 2026-04-26

## Контекст и baseline

- Репозиторий: `D:\GraceKelly`
- HEAD: `8f46e68`
- Git-tracked files: `667`
- Аудируемая зона: `src/`, `tests/`, `static/`, `scripts/`, `docs/`, `.github`
- Python source: `106` файлов, `13883` строк
- Tests: `161` файл, `30190` строк
- Static UI: `20` файлов, `346512` байт (`.html` 216951, `.js` 97290, `.css` 30141, `.svg` 2130)
- i18n/locale JSON: не найдено, key count `0/n/a`
- Существующие незакоммиченные изменения до аудита: `?? CLAUDE.md`, `?? docs/plans/`
- Файл аудита создан отдельно; исходники не менялись.

## Проверки

- `.venv\Scripts\python -m pytest -p no:schemathesis --tb=short -q tests`
  - `2661 passed, 6 skipped, 11 subtests passed in 499.84s`
- `.venv\Scripts\python -m ruff check src/ tests/`
  - `All checks passed!`
- `.venv\Scripts\python -m mypy src/gracekelly/`
  - `Success: no issues found in 106 source files`
- `.venv\Scripts\python -m mypy src/ tests/`
  - FAIL: `tests\test_middleware_usage_telemetry.py:146`
- `.venv\Scripts\python -m pytest -p no:schemathesis --cov=gracekelly --cov-report=term --cov-fail-under=97 -q tests`
  - FAIL: total coverage `94.18%`, required `97%`
- `python -m pytest --tb=short -q`
  - FAIL before collection: global Python loads broken `schemathesis` pytest plugin.
- `.venv\Scripts\python -m pytest -p no:schemathesis --tb=short -q`
  - FAIL during collection: pytest walks stale temp dirs under `.tmp`, `.workflow/tmp-tests`, `pytest-temp`.
- `pip-audit` and `bandit` were not installed in `.venv`; CI installs them dynamically, so I did not mutate the local venv.

## Findings

### P0 - CI is currently red

The GitHub workflow runs stricter gates than the project instructions and current local "green" command:

- `.github/workflows/ci.yml:47-48` runs `python -m mypy src/ tests/`
- `.github/workflows/ci.yml:50-53` runs coverage with `--cov-fail-under=97`

Current results:

- `mypy src/ tests/` fails at `tests/test_middleware_usage_telemetry.py:146`:
  - unused `type: ignore[arg-type]`
  - uncovered `call-overload` on `pathlib.Path.open(...)`
- coverage gate fails:
  - `TOTAL 7632 stmts, 444 miss, 94.18%`
  - required: `97%`

Impact: PRs should fail CI even though `ruff`, `mypy src/gracekelly/`, and `pytest tests` pass locally.

Recommendation:

1. Fix `tests/test_middleware_usage_telemetry.py:146` or relax CI back to source-only mypy intentionally.
2. Either restore coverage to 97% or lower the CI threshold to the actual project target.
3. Align `AGENTS.md`, README, and CI so developers run the same gates before commit.

### P1 - Enabling `GRACEKELLY_API_KEY` makes the built-in UI inaccessible

Evidence:

- Auth middleware treats everything outside `_PUBLIC_PATHS` as protected:
  - `src/gracekelly/middleware.py:20-26`
  - `src/gracekelly/middleware.py:29-53`
- Static UI is mounted under `/`:
  - `src/gracekelly/main.py:445-447`
- README documents both the built-in UI and optional API key:
  - `README.md:103`
  - `README.md:112-121`

Reproduction via `TestClient` with `Settings(api_key="secret")`:

- `GET /` -> `401`
- `GET /js/app.js` -> `401`
- `GET /api/v1/models` without auth -> `401`

Impact: the "optional bearer token" protects the API, but also blocks direct browser loading of `/` and static assets because ordinary navigation does not attach the bearer header. A user following README and adding `GRACEKELLY_API_KEY` loses the built-in SPA.

Recommendation:

- Decide the intended model:
  - API-only auth: exempt static pages/assets and have JS send the key for API calls.
  - Full UI auth: add cookie/session/login flow.
  - Local-only no-auth UI: document that `GRACEKELLY_API_KEY` is incompatible with the static SPA.

### P1 - Global CSP breaks several linked static pages

Evidence:

- CSP is strict:
  - `src/gracekelly/middleware.py:73-84`
  - `script-src 'self'`
  - `style-src 'self'`
  - `connect-src 'self'`
- Static pages use inline handlers and inline scripts/styles:
  - `static/index.html:172-175`
  - `static/analytics.html:286`, `static/analytics.html:400-405`, `static/analytics.html:677-685`, `static/analytics.html:688-691`
  - `static/webpage.html:677`, `static/webpage.html:727`, many more inline `onclick` usages
  - `static/english.html:481`, `static/english.html:529-883`, `static/english.html:886-889`
  - `static/interview.html:765-1158`, `static/interview.html:1162-1165`
- `static/analytics.html` also loads Chart.js from CDN:
  - `<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>`

Impact: under the real FastAPI app, these pages receive the CSP header and browsers should block inline scripts/styles and the CDN script. Existing UI tests do not catch it because `tests/test_ui_auth_banner.py` serves `static/` through `SimpleHTTPRequestHandler`, bypassing the FastAPI security headers.

Recommendation:

1. Move inline JS/CSS into same-origin static files, or serve a page-specific CSP.
2. Vendor Chart.js locally or allow the exact CDN only for that page.
3. Add one Playwright test against `create_app()`/uvicorn, not `SimpleHTTPRequestHandler`, to catch CSP regressions.

### P1 - Footer links expose static tools whose backend endpoints do not exist

The main UI links these pages:

- `static/index.html:161-165`
  - `/english.html`
  - `/interview.html`
  - `/analytics.html`
  - `/webpage.html`
  - `/rag.html`

But the linked tools call old/nonexistent API paths:

- `static/english.html:530` -> `/api/english`
- `static/interview.html:766` -> `/api/interview`
- `static/webpage.html:931`, `1489`, `1535`, `1541`, `1562`, `1618`, `1654` -> `/api/webpage/...`
- `static/analytics.html:561`, `596`, `616`, `641` -> `/api/analytics/...`

Actual app routes contain only `/api/v1/...`; route inventory has no `/api/english`, `/api/interview`, `/api/webpage`, or `/api/analytics/*`.

Impact: the product surface advertises tools that cannot work in the current backend. This creates false positives in manual QA because the pages render, but their primary actions fail at runtime.

Recommendation:

- Remove dead links, mark these pages as archived, or implement/port the missing routes.
- Prefer a route inventory test that checks every same-origin API path referenced from `static/`.

### P1 - Analytics UI contract does not match the backend analytics route

Evidence:

- Backend exposes one route:
  - `src/gracekelly/api/routes/analytics.py:11`
  - `src/gracekelly/api/routes/analytics.py:31-45` -> `GET /api/v1/analytics`
- Backend response fields:
  - `total_models`
  - `total_executions`
  - `models`
  - `top_models`
  - per model: `model_id`, `total_executions`, `successful`, `failed`, `success_rate`, `avg_duration_ms`
- Main sidebar reads old fields:
  - `static/js/app.js:388-399` uses `total_requests` and `successful_requests`
- Dedicated analytics page calls old routes and old concepts:
  - `static/analytics.html:561` `/api/analytics/overview`
  - `static/analytics.html:596` `/api/analytics/trends?days=7`
  - `static/analytics.html:616` `/api/analytics/models`
  - `static/analytics.html:641` `/api/analytics/accounts`
  - `static/analytics.html:705` still says data comes from SQLite, while `docs/architecture.md` explicitly excludes SQLite.

Impact: sidebar stats should show blanks/zeroes even when backend analytics has data; `/analytics.html` is effectively stale.

Recommendation:

- Update the sidebar to the `/api/v1/analytics` schema.
- Either delete `/analytics.html` or rewrite it around the existing endpoint.
- Add a static/API contract test for field names used by `static/js/app.js`.

### P2 - The documented default pytest command is not robust in this checkout

Evidence:

- `AGENTS.md:36` says to run `python -m pytest --tb=short -q`.
- `README.md:157` says `python -m pytest`.
- `pyproject.toml:70` excludes only `tmp`, `.pytest_cache`, `.hypothesis`, `docs`.
- The checkout contains stale temp dirs under `.tmp`, `.workflow/tmp-tests`, and `pytest-temp`.

Observed:

- `.venv\Scripts\python -m pytest -p no:schemathesis --tb=short -q` fails during collection with 37 `PermissionError` entries from those temp dirs.
- `.venv\Scripts\python -m pytest -p no:schemathesis --tb=short -q tests` passes.

Impact: a clean CI checkout may pass collection, but local developers and agents in the real workspace get red tests unless they know to target `tests/` explicitly.

Recommendation:

- Add `.tmp`, `.workflow/tmp-tests`, `pytest-temp`, and probably `.workflow` to `norecursedirs`, or standardize all docs/CI on `pytest tests`.
- Keep `-p no:schemathesis` if the global environment can inject the incompatible plugin.

### P2 - Model catalog has no graceful first-run fallback for dry-run/no-browser mode

Evidence:

- `Settings` defaults to dry-run and browser disabled:
  - `src/gracekelly/config.py:74`
  - `src/gracekelly/config.py:90-92`
- `/api/v1/models` requires a stored browser catalog snapshot:
  - `src/gracekelly/api/routes/models.py:177-186`
- `create_app(Settings(storage_backend="memory", browser_enabled=False))` returns `503` for `/api/v1/models`.

Impact: a default local/dry-run start can serve the SPA, but the model menu cannot populate until a browser catalog snapshot exists. This is surprising because dry-run mode should be the easiest first-run path.

Recommendation:

- In dry-run/no-browser mode, return API models plus a clearly marked static/dry-run browser catalog, or render a UI fallback that does not depend on `/api/v1/models`.

### P3 - Security/dependency scanners are CI-only and not locally available

Evidence:

- `.github/workflows/ci.yml:55-63` installs and runs `pip-audit` and `bandit`.
- Local `.venv` does not have either module installed.

Impact: local audit cannot reproduce the full CI security gate without mutating the environment. This is acceptable for CI, but weak for local preflight.

Recommendation:

- Add a documented optional command, for example `python -m pip install -e ".[dev,postgres,browser]" && python -m pip install pip-audit bandit[toml]`, or add them to the `dev` extra if local parity is expected.

## What is healthy

- Source lint is clean: `ruff check src/ tests/`.
- Source typecheck is clean: `mypy src/gracekelly/`.
- The actual test suite under `tests/` is green: `2661 passed, 6 skipped`.
- Backend route surface is explicit and mostly well-covered.
- Main orchestrator boundaries are clear: routes -> service -> router -> adapters -> storage.
- Prompt text rendering in the main chat path escapes HTML before markdown formatting (`static/js/chat.js:98-115`), so the main chat bubbles do not appear to be raw XSS sinks.
- Security headers exist and are tested, though their current global application conflicts with static pages.

## Recommended next sequence

1. Fix CI red gates first: `mypy src/ tests/` and coverage threshold mismatch.
2. Decide the auth model for the built-in SPA before adding more API-key behavior.
3. Make CSP and static pages compatible, then add a FastAPI-served Playwright smoke.
4. Remove or restore stale static tools linked from the footer.
5. Normalize test commands in `AGENTS.md`, README, CI, and `pyproject.toml`.

## Residual risk

- I did not run live Perplexity browser smoke, Postgres live integration, `pip-audit`, or `bandit` locally.
- The passing full test command targeted `tests/`; root-level pytest collection is currently broken in this checkout for the reasons above.
