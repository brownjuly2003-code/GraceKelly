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
pip install -e .[dev,postgres]
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
- API-backed execution currently starts with a minimal Mistral adapter boundary.
- Browser-backed execution can now be exercised end-to-end through a `scripted` automation backend; live site automation is still not implemented yet.
- PostgreSQL schema bootstrap now lives in a packaged SQL migration: `src/gracekelly/storage/migrations/0001_initial.sql`.

## Scripted browser mode

```bash
set GRACEKELLY_BROWSER_ENABLED=true
set GRACEKELLY_BROWSER_AUTOMATION_BACKEND=scripted
set GRACEKELLY_BROWSER_PROFILE_DIR=D:\Profiles\GraceKelly
uvicorn gracekelly.main:app --app-dir src --host 127.0.0.1 --port 8011
```

This mode is for exercising the browser execution path and operator views without a live browser driver.

## PostgreSQL validation

```bash
set GRACEKELLY_POSTGRES_DSN=postgresql://postgres:postgres@localhost:5432/gracekelly
python -m gracekelly.tools.validate_postgres
```

Use `--no-bootstrap` to validate an existing schema without applying the packaged migration first.

## Optional live PostgreSQL test

```bash
set GRACEKELLY_POSTGRES_TEST_DSN=postgresql://postgres:postgres@localhost:5432/gracekelly_test
python -m unittest D:\GraceKelly\tests\test_postgres_live.py
```

This test stays skipped unless `GRACEKELLY_POSTGRES_TEST_DSN` and `psycopg` are both available.
