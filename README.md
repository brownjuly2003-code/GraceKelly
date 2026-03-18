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
- `GET /metrics`
- `GET /api/v1/models`
- `POST /api/v1/orchestrate`
- `GET /api/v1/tasks`
- `GET /api/v1/tasks/{task_id}`

`GET /api/v1/tasks` supports `limit`, `status`, `execution_mode`, `dry_run`, and `failure_code` query params and returns summary metadata including `adapter_name`, winning `model`, `requested_models`, and short-circuit fields such as `cancelled_step_count` / `cancel_reason`.
`GET /api/v1/tasks/{task_id}` also lifts both execution policy and terminal execution context to top-level fields such as `quorum`, `merge_strategy`, `adapter_hint`, `cancel_on_quorum`, `winning_step_index`, `cancelled_steps`, `cancel_reason`, and `execution_details`, while still returning the raw event stream.
`GET /api/v1/models` now includes `adapter_kind`, `provider`, and browser-specific availability hints (`available`, `availability_status`, `availability_checked_at`, `availability_source`) so the catalog can distinguish static registry entries from the last authenticated Perplexity menu actually observed by the Playwright runtime.
`GET /api/v1/readiness` exposes browser-adapter circuit-breaker state under the `browser.perplexity` component whenever repeated infrastructure-grade browser failures temporarily open the adapter.
`GET /metrics` exposes Prometheus-style gauges for service readiness, component states, execution saturation, in-memory storage counts when available, and browser circuit-breaker state.

## Tests

```bash
pytest -q
```

Current suite: 359 tests (4 optional skips for live PostgreSQL/Playwright).

The project config adds `src` to the pytest import path, so local test runs do not require an editable install just to resolve `gracekelly.*` imports.

## Example request

```bash
curl -X POST http://127.0.0.1:8011/api/v1/orchestrate \
  -H "content-type: application/json" \
  -d "{\"prompt\":\"Health check prompt\",\"models\":[\"Kimi K2\",\"Mistral\"],\"dry_run\":true,\"quorum\":1}"
```

## API security

### Authentication

```bash
set GRACEKELLY_API_KEY=your-secret-key
uvicorn gracekelly.main:app --app-dir src --host 127.0.0.1 --port 8011
```

When `GRACEKELLY_API_KEY` is set, all endpoints except `/health`, `/docs`, `/openapi.json`, and `/redoc` require one of:
- `Authorization: Bearer <key>` header
- `X-API-Key: <key>` header

When not set, all endpoints are open (development default).

### Rate limiting

```bash
set GRACEKELLY_RATE_LIMIT_PER_MINUTE=60
```

When set, each client IP is limited to this many requests per minute on protected endpoints. Returns HTTP 429 when exceeded. Disabled by default.

### Authenticated request example

```bash
curl -X POST http://127.0.0.1:8011/api/v1/orchestrate \
  -H "content-type: application/json" \
  -H "Authorization: Bearer your-secret-key" \
  -d "{\"prompt\":\"Health check\",\"models\":[\"Mistral\"],\"dry_run\":true}"
```

## PostgreSQL connection pooling

```bash
set GRACEKELLY_POSTGRES_POOL_ENABLED=true
set GRACEKELLY_POSTGRES_POOL_MIN_SIZE=1
set GRACEKELLY_POSTGRES_POOL_MAX_SIZE=5
```

When enabled, connections are served from a `psycopg_pool.ConnectionPool` instead of opening per-request. Requires `pip install -e .[postgres]` (includes `psycopg_pool`). Falls back to direct connections if `psycopg_pool` is not installed.

## Runtime notes

- `dry_run=true` exercises the orchestration path without calling providers.
- API-backed execution now includes both a minimal Mistral adapter boundary and an OpenAI-compatible boundary.
- Browser-backed execution now includes both the `scripted` backend and a first headed Playwright backend.
- Browser execution is wrapped in a small in-process circuit breaker that trips on repeated `provider_unavailable`, `timeout`, or `unknown_error` failures and reports its state through health/readiness.
- Browser shutdown now resets session state to idle, and browser adapter health explicitly degrades if session state and live driver state drift apart.
- Route and degraded-storage diagnostics now emit structured `key=value` logs, so task submission, task lookup, readiness degradation, and PostgreSQL health/schema failures are easier to trace in plain logs.
- If callers send `metadata.trace_id`, that value is propagated into route and orchestrator lifecycle logs for lightweight correlation.
- PostgreSQL schema bootstrap now lives in a packaged SQL migration: `src/gracekelly/storage/migrations/0001_initial.sql`.
- Live Perplexity reconnaissance from 2026-03-17 is captured in `docs/perplexity-dom-recon.md`.
- `memory` stays the zero-config development default; for durable browser runs, set `GRACEKELLY_STORAGE_BACKEND=postgres` explicitly.
- Current operational recovery steps are documented in `docs/operator-runbook.md`.

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
set GRACEKELLY_BROWSER_CIRCUIT_BREAKER_ENABLED=true
set GRACEKELLY_BROWSER_CIRCUIT_BREAKER_FAILURE_THRESHOLD=3
set GRACEKELLY_BROWSER_CIRCUIT_BREAKER_COOLDOWN_SECONDS=60
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

## PostgreSQL export

```bash
set GRACEKELLY_POSTGRES_DSN=postgresql://postgres:postgres@localhost:5432/gracekelly
gracekelly-export-postgres --limit 100
```

This writes a JSON snapshot under `tmp/postgres-export/` by default, including:
- export timestamp and schema version
- `snapshot_format_version` and `gracekelly_version`
- `snapshot_sha256` integrity digest
- `task_count`, `step_count`, and `event_count` manifest totals
- repository health and schema report
- `exported_task_ids` for quick manifest inspection
- serialized task records with nested steps and events

The command summary also includes `generated_at`, `compressed_output`, `output_exists`, `output_size_bytes`, `manifest_status`, `snapshot_status_consistency_status`, `selection_status`, `missing_task_ids_status`, field-level manifest verification statuses, `requested_task_ids`, `exported_task_ids`, `missing_task_ids`, `task_count`, `step_count`, `event_count`, `repository_health`, and `repository_schema`, so the export result itself is usable as a lightweight storage preflight.
If export fails after the snapshot was already assembled, the error payload now also preserves the snapshot manifest context.

If the output path ends with `.gz`, GraceKelly writes a gzip-compressed snapshot:

```bash
gracekelly-export-postgres --output D:\GraceKelly\tmp\postgres-export\selected.json.gz
```

Export specific tasks when needed:

```bash
gracekelly-export-postgres --task-id task-1 --task-id task-2 --output D:\GraceKelly\tmp\postgres-export\selected.json
```

Inspect a snapshot artifact offline before restore:

```bash
gracekelly-inspect-snapshot --input D:\GraceKelly\tmp\postgres-export\selected.json
```

This verifies `snapshot_sha256` when present and returns the manifest summary, including `manifest_status`, `snapshot_status_consistency_status`, `selection_status`, `missing_task_ids_status`, per-field manifest verification statuses, `selection`, `task_count`, `step_count`, `event_count`, `exported_task_ids`, `missing_task_ids`, `input_size_bytes`, and an `import_ready` verdict based on checksum, `snapshot_format_version`, `migration`, and manifest consistency, without requiring a PostgreSQL DSN.
If the snapshot cannot be parsed, the error payload still includes `compressed_input` and `input_size_bytes`.

## PostgreSQL import

```bash
set GRACEKELLY_POSTGRES_DSN=postgresql://postgres:postgres@localhost:5432/gracekelly
gracekelly-import-postgres --input D:\GraceKelly\tmp\postgres-export\selected.json
```

This restores the snapshot task-by-task into PostgreSQL:
- each imported `task_id` is replaced in place
- related steps and events are replaced with the snapshot bundle for that task
- unrelated tasks already in the database are left untouched
- `snapshot_format_version` is checked when present
- `snapshot_sha256` is verified when present, so corrupted snapshots are rejected before restore

Restore only a subset of task bundles from a larger snapshot:

```bash
gracekelly-import-postgres --input D:\GraceKelly\tmp\postgres-export\selected.json --task-id task-1 --task-id task-2
```

If some requested task IDs are missing from the artifact, the command returns `status=partial` and lists them under `missing_task_ids` after restoring the bundles that were present.

Validate a snapshot and the target repository without writing any task data:

```bash
gracekelly-import-postgres --input D:\GraceKelly\tmp\postgres-export\selected.json --dry-run
```

The success payload now includes `repository_health` and `repository_schema`, so a dry run can double as a pre-restore validation report.
It also echoes `compressed_input`, `input_size_bytes`, `source_format_status`, `source_migration_status`, `source_checksum_status`, `source_snapshot_sha256`, `source_import_ready`, `source_status_consistency_status`, `source_manifest_status`, `source_selection_status`, `source_selection`, `source_task_count`, `source_step_count`, `source_event_count`, `source_exported_task_ids`, `source_missing_task_ids`, and `source_missing_task_ids_status` from the artifact manifest, so restore output stays self-contained.
Even failed import preflights now include `compressed_input`, `input_size_bytes`, and the source compatibility verdict fields available from the parsed artifact, so a broken snapshot is still identifiable without a second inspection step.

Gzip-compressed snapshot input is also supported:

```bash
gracekelly-import-postgres --input D:\GraceKelly\tmp\postgres-export\selected.json.gz --dry-run
```

If connectivity or schema state is intentionally degraded but you still need a manual restore, override the guard explicitly:

```bash
gracekelly-import-postgres --input D:\GraceKelly\tmp\postgres-export\selected.json --allow-degraded-schema
```

## Optional live PostgreSQL test

```bash
set GRACEKELLY_POSTGRES_TEST_DSN=postgresql://postgres:postgres@localhost:5432/gracekelly_test
python -m unittest D:\GraceKelly\tests\test_postgres_live.py
```

This test stays skipped unless `GRACEKELLY_POSTGRES_TEST_DSN` and `psycopg` are both available.
