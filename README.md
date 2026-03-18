# GraceKelly

GraceKelly is a clean-slate orchestrator for browser-routed LLM execution.

This project is intentionally independent from any legacy repository:
- no direct imports from legacy code
- no shared runtime
- no shared SQLite files
- no mixed UI, archive, and orchestration concerns in one process

The current phase builds the core contract first:
- FastAPI service shell
- canonical model registry
- task submission contract
- in-memory task storage
- task events
- readiness reporting
- adapter routing for browser and API backends
- phased roadmap for the execution engine

## Project layout

- `src/gracekelly/main.py`: FastAPI app factory and wiring
- `src/gracekelly/api/routes/`: public API routes
- `src/gracekelly/core/`: orchestration domain logic
- `src/gracekelly/storage/`: storage abstractions and backends
- `docs/`: architecture notes and delivery phases

## Getting started

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev,postgres,browser]
uvicorn gracekelly.main:app --app-dir src --host 127.0.0.1 --port 8011
```

## First endpoints

- `GET /health`
- `GET /api/v1/readiness`
- `GET /api/v1/models`
- `POST /api/v1/orchestrate`
- `GET /api/v1/tasks`
- `GET /api/v1/tasks/{task_id}`

`GET /api/v1/tasks` supports `limit`, `status`, `execution_mode`, `dry_run`, and `failure_code` query params and returns summary metadata including `adapter_name`, winning `model`, `requested_models`, and short-circuit fields such as `cancelled_step_count` / `cancel_reason`.
`GET /api/v1/tasks/{task_id}` also lifts both execution policy and terminal execution context to top-level fields such as `quorum`, `merge_strategy`, `adapter_hint`, `cancel_on_quorum`, `winning_step_index`, `cancelled_steps`, `cancel_reason`, and `execution_details`, while still returning the raw event stream.
`GET /api/v1/models` now includes `adapter_kind`, `provider`, and browser-specific availability hints (`available`, `availability_status`, `availability_checked_at`, `availability_source`) so the catalog can distinguish static registry entries from the last authenticated Perplexity menu actually observed by the Playwright runtime.

## Tests

```bash
pytest -q
```

The project config adds `src` to the pytest import path, so local test runs do not require an editable install just to resolve `gracekelly.*` imports.

## Example request

```bash
curl -X POST http://127.0.0.1:8011/api/v1/orchestrate \
  -H "content-type: application/json" \
  -d "{\"prompt\":\"Health check prompt\",\"models\":[\"Kimi K2\",\"Mistral\"],\"dry_run\":true,\"quorum\":1}"
```

## Runtime notes

- `dry_run=true` exercises the orchestration path without calling providers.
- API-backed execution now includes both a minimal Mistral adapter boundary and an OpenAI-compatible boundary.
- Browser-backed execution now includes both the `scripted` backend and a first headed Playwright backend.
- PostgreSQL schema bootstrap now lives in a packaged SQL migration: `src/gracekelly/storage/migrations/0001_initial.sql`.
- Live Perplexity reconnaissance from 2026-03-17 is captured in `docs/perplexity-dom-recon.md`.
- `memory` stays the zero-config development default; for durable browser runs, set `GRACEKELLY_STORAGE_BACKEND=postgres` explicitly.

## OpenAI-compatible API mode

```bash
set GRACEKELLY_OPENAI_API_KEY=sk-example
set GRACEKELLY_OPENAI_BASE_URL=https://api.openai.com/v1
set GRACEKELLY_OPENAI_TIMEOUT_SECONDS=60
uvicorn gracekelly.main:app --app-dir src --host 127.0.0.1 --port 8011
```

Use the catalog model name `GPT-5.4 API` to route a request through the OpenAI-compatible adapter path.

## Scripted browser mode

```bash
set GRACEKELLY_BROWSER_ENABLED=true
set GRACEKELLY_BROWSER_AUTOMATION_BACKEND=scripted
set GRACEKELLY_BROWSER_PROFILE_DIR=D:\Profiles\GraceKelly
uvicorn gracekelly.main:app --app-dir src --host 127.0.0.1 --port 8011
```

This mode is for exercising the browser execution path and operator views without a live browser driver.

## Playwright browser mode

```bash
set GRACEKELLY_BROWSER_ENABLED=true
set GRACEKELLY_BROWSER_AUTOMATION_BACKEND=playwright
set GRACEKELLY_BROWSER_PROFILE_DIR=D:\Profiles\GraceKellyPlaywright
set GRACEKELLY_BROWSER_PLAYWRIGHT_CHANNEL=chrome
set GRACEKELLY_BROWSER_PLAYWRIGHT_HEADLESS=false
uvicorn gracekelly.main:app --app-dir src --host 127.0.0.1 --port 8011
```

Use a dedicated user-data directory for this mode. On 2026-03-17, headless mode hit Cloudflare `403`, and copying a live Chrome `Default` profile did not reliably preserve authenticated state.

## Create dedicated Perplexity profile

```bash
gracekelly-create-perplexity-profile
```

This opens a persistent Playwright Chrome profile at `tmp/browser-recon/perplexity-profile` by default. Log in to Perplexity manually in the opened browser window, wait for the prompt input to appear, then return to the terminal and press Enter.

You can override the profile directory if needed:

```bash
gracekelly-create-perplexity-profile --profile-dir D:\GraceKelly\tmp\browser-recon\perplexity-profile
```

Then point runtime and smoke checks at the same directory:

```bash
set GRACEKELLY_BROWSER_PROFILE_DIR=D:\GraceKelly\tmp\browser-recon\perplexity-profile
```

## Capture authenticated DOM recon

```bash
gracekelly-capture-perplexity-recon
```

By default this writes a dated artifact bundle under `tmp/browser-recon/YYYY-MM-DD/`:
- authenticated home screenshot
- toolbar button inventory
- composer HTML fragment
- `More` screenshot and button inventory if overflow is present
- model-picker screenshot and menu snapshot if the picker becomes visible
- a manifest JSON tying the capture together

You can also capture a real answered state:

```bash
gracekelly-capture-perplexity-recon --prompt "Reply with only OK" --timeout-seconds 60
```

That adds:
- post-response screenshot
- captured `main` HTML after the answer
- raw response-candidate JSON for selector/debug work

If the current UI needs manual help after the automatic pass, run:

```bash
gracekelly-capture-perplexity-recon --interactive-pause
```

This opens the same dedicated profile, performs the automatic capture first, then pauses so the live UI can be clicked manually before a final screenshot is saved.

## Optional live Playwright smoke

```bash
set GRACEKELLY_BROWSER_LIVE_TEST=true
set GRACEKELLY_BROWSER_PROFILE_DIR=D:\Profiles\GraceKellyPlaywright
pytest -q tests/test_playwright_live.py -rA
```

This smoke stays skipped unless `GRACEKELLY_BROWSER_LIVE_TEST=true`. If the supplied profile is not authenticated for Perplexity, the test reports a skip instead of a hard failure.
Close any Chrome windows using the same `GRACEKELLY_BROWSER_PROFILE_DIR` before running the smoke. If the profile is still open elsewhere, GraceKelly now surfaces that as a provider-availability failure instead of a generic browser crash.
Set `GRACEKELLY_BROWSER_LIVE_DEBUG=true` to write the last live execution details to `tmp/browser-recon/live-smoke-result.json` for manual DOM drift inspection.

## PostgreSQL validation

```bash
set GRACEKELLY_POSTGRES_DSN=postgresql://postgres:postgres@localhost:5432/gracekelly
set GRACEKELLY_POSTGRES_CONNECT_TIMEOUT_SECONDS=5
python -m gracekelly.tools.validate_postgres
```

Use `--no-bootstrap` to validate an existing schema without applying the packaged migration first.

## Optional live PostgreSQL test

```bash
set GRACEKELLY_POSTGRES_TEST_DSN=postgresql://postgres:postgres@localhost:5432/gracekelly_test
python -m unittest D:\GraceKelly\tests\test_postgres_live.py
```

This test stays skipped unless `GRACEKELLY_POSTGRES_TEST_DSN` and `psycopg` are both available.
