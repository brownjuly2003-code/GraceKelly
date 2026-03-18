# Operator Runbook

Last updated: 2026-03-18

This runbook covers the current operating surface for GraceKelly:
- service liveness and readiness
- metrics scraping
- browser-adapter recovery
- storage validation and task-scoped snapshot restore

It is intentionally limited to the current in-process deployment model.

## Primary endpoints

- `GET /health`
  - fast summary for service, environment, storage backend, active model executions, saturated models
- `GET /api/v1/readiness`
  - component-by-component status for storage, execution router, and adapters
- `GET /metrics`
  - Prometheus-style gauges for readiness, component states, execution saturation, storage counts when available, and browser circuit-breaker state
- `GET /api/v1/tasks`
  - recent operator task summaries with `status`, `execution_mode`, `dry_run`, and `failure_code` filters
- `GET /api/v1/tasks/{task_id}`
  - full execution context: plan scalars, steps, events, terminal execution details

## Normal startup checks

1. Confirm the process is live:
   - `curl http://127.0.0.1:8011/health`
2. Confirm readiness semantics:
   - `curl http://127.0.0.1:8011/api/v1/readiness`
3. Confirm scrape surface:
   - `curl http://127.0.0.1:8011/metrics`

Expected development baseline:
- `storage_backend=memory`
- readiness may be `ok` even if browser is optional and degraded under the active execution profile
- `gracekelly_execution_active_model_executions 0` when idle

## Readiness interpretation

`storage` component:
- `ok`: repository reachable and schema report acceptable
- `degraded`: connectivity or schema drift issue
- Action:
  - for PostgreSQL, run the validation CLI
  - for memory, restart the process if the in-memory store itself is corrupted

`execution-router` component:
- use `active_model_executions`, `active_by_model`, `model_limits`, and `saturated_models`
- `saturated_models` means requests are being rejected with `rate_limited` for those models

`browser.perplexity` component:
- `session` shows configuration and last session error
- `automation` shows live-driver or scripted-driver detail
- `circuit_breaker` shows whether repeated infrastructure failures have opened the browser adapter

## Metrics interpretation

Key metric groups:
- `gracekelly_readiness_state`
- `gracekelly_component_state`
- `gracekelly_execution_active_model_executions`
- `gracekelly_execution_model_active`
- `gracekelly_execution_model_limit`
- `gracekelly_execution_model_saturated`
- `gracekelly_storage_task_count`, `gracekelly_storage_step_count`, `gracekelly_storage_event_count`
- `gracekelly_browser_circuit_breaker_state`
- `gracekelly_browser_circuit_breaker_consecutive_failures`
- `gracekelly_browser_circuit_breaker_open_count`
- `gracekelly_browser_circuit_breaker_fail_fast_rejections`

Storage-count gauges are present on both the in-memory backend and PostgreSQL when the repository healthcheck can read the durable tables successfully.

## Browser triage

Common task-level failure codes:

`auth_failed`:
- browser profile is not logged in or Perplexity showed a late sign-in overlay
- Recovery:
  - create or refresh a dedicated profile:
    - `gracekelly-create-perplexity-profile`
  - point runtime to that directory:
    - `set GRACEKELLY_BROWSER_PROFILE_DIR=D:\GraceKelly\tmp\browser-recon\perplexity-profile`
  - rerun the live smoke

`provider_unavailable`:
- browser driver missing, profile directory busy, browser disabled, or circuit breaker currently open
- Recovery:
  - confirm `browser_enabled=true`
  - close any Chrome windows using the same profile directory
  - inspect `/api/v1/readiness` for `browser.perplexity.details.circuit_breaker`
  - if the circuit breaker is open, wait for cooldown or restart the service

`model_mismatch`:
- requested browser model was not confirmed in the current authenticated UI
- Recovery:
  - inspect `GET /api/v1/models`
  - if model availability drift is suspected, capture fresh recon artifacts

`timeout` or `unknown_error`:
- live UI or automation state unstable
- Recovery:
  - inspect `browser.perplexity` health details and breaker counters
  - capture fresh DOM recon
  - rerun the live smoke with debug enabled

## Browser recovery commands

Create or refresh a dedicated authenticated profile:

```bash
gracekelly-create-perplexity-profile
```

Capture fresh authenticated recon:

```bash
gracekelly-capture-perplexity-recon --prompt "Reply with only OK" --timeout-seconds 60
```

Run the manual-gated live smoke:

```bash
set GRACEKELLY_BROWSER_LIVE_TEST=true
set GRACEKELLY_BROWSER_PROFILE_DIR=D:\GraceKelly\tmp\browser-recon\perplexity-profile
set GRACEKELLY_BROWSER_LIVE_DEBUG=true
pytest -q tests/test_playwright_live.py -rA
```

## Circuit breaker recovery

Browser circuit breaker semantics:
- counts only `provider_unavailable`, `timeout`, and `unknown_error`
- opens after the configured threshold
- fail-fast blocks new browser executions until cooldown expires
- the next allowed probe closes the breaker on success or reopens it on another counted failure

Runtime knobs:

```bash
set GRACEKELLY_BROWSER_CIRCUIT_BREAKER_ENABLED=true
set GRACEKELLY_BROWSER_CIRCUIT_BREAKER_FAILURE_THRESHOLD=3
set GRACEKELLY_BROWSER_CIRCUIT_BREAKER_COOLDOWN_SECONDS=60
```

Operational guidance:
- prefer waiting for cooldown if the root cause is transient UI or provider instability
- restart the service if the browser runtime itself is wedged and cooldown alone is not enough
- investigate repeated `open_count` growth before increasing thresholds

## Storage validation

Validate PostgreSQL connectivity and schema:

```bash
set GRACEKELLY_POSTGRES_DSN=postgresql://postgres:postgres@localhost:5432/gracekelly
set GRACEKELLY_POSTGRES_CONNECT_TIMEOUT_SECONDS=5
python -m gracekelly.tools.validate_postgres
```

Use `--no-bootstrap` if the target database should not be modified during validation.

Export a JSON snapshot of recent durable-state records:

```bash
set GRACEKELLY_POSTGRES_DSN=postgresql://postgres:postgres@localhost:5432/gracekelly
gracekelly-export-postgres --limit 100
```

Export specific tasks only:

```bash
gracekelly-export-postgres --task-id task-1 --task-id task-2
```

Export artifacts now carry `snapshot_format_version`, `gracekelly_version`, and `snapshot_sha256` so restores can reject incompatible or corrupted JSON before task rows are touched.
The export command summary now also echoes `requested_task_ids`, `exported_task_ids`, `missing_task_ids`, `repository_health`, and `repository_schema`, so the operator can capture both selection results and storage state without opening the snapshot file immediately.
If the export path ends with `.gz`, the snapshot is written as gzip-compressed JSON.

Inspect a snapshot artifact offline before restore:

```bash
gracekelly-inspect-snapshot --input D:\GraceKelly\tmp\postgres-export\selected.json
```

That command verifies `snapshot_sha256` when present and reports manifest details such as `selection`, `task_count`, `exported_task_ids`, `missing_task_ids`, and `import_ready` without requiring database connectivity.

Restore a snapshot back into PostgreSQL:

```bash
set GRACEKELLY_POSTGRES_DSN=postgresql://postgres:postgres@localhost:5432/gracekelly
gracekelly-import-postgres --input D:\GraceKelly\tmp\postgres-export\selected.json
```

Restore semantics:
- imported `task_id` values are replaced in place
- related step and event rows are replaced together with the task
- unrelated tasks remain in the database
- `snapshot_format_version` is verified when present
- `snapshot_sha256` is verified when present

Restore only selected task bundles from a larger snapshot:

```bash
gracekelly-import-postgres --input D:\GraceKelly\tmp\postgres-export\selected.json --task-id task-1 --task-id task-2
```

If one or more requested `task_id` values are absent, the command still restores the bundles that exist and returns `status=partial` plus `missing_task_ids` in the JSON summary.

Use `--allow-degraded-schema` only for deliberate manual recovery when the guardrail would otherwise block a needed restore.

Validate restore inputs without writing:

```bash
gracekelly-import-postgres --input D:\GraceKelly\tmp\postgres-export\selected.json --dry-run
```

That success payload includes `repository_health` and `repository_schema`, so operators can confirm the target backend state in the same preflight call.
It also echoes `source_selection`, `source_task_count`, `source_exported_task_ids`, and `source_missing_task_ids`, so the restore report preserves the source artifact manifest context.
Compressed `.json.gz` snapshot input is supported directly.

## Task inspection workflow

1. Find the recent failures:
   - `GET /api/v1/tasks?status=failed&dry_run=false`
2. Narrow by backend shape:
   - `GET /api/v1/tasks?execution_mode=browser`
3. Narrow by failure class:
   - `GET /api/v1/tasks?failure_code=provider_unavailable`
4. Inspect one task deeply:
   - `GET /api/v1/tasks/{task_id}`

Use `execution_details`, terminal event payloads, and step event `details` together. That is where current adapter diagnostics, browser driver metadata, and circuit-breaker-origin failures surface without widening storage tables.

## Log correlation

If callers supply `metadata.trace_id` on `POST /api/v1/orchestrate`, GraceKelly now echoes that value in:
- route-level `orchestrate.request` / `orchestrate.accepted`
- orchestrator-level `task.submit.started` / `task.submit.completed`
- `task.event_persistence_failed` warnings

That gives a minimal correlation key across HTTP entry, task creation, and best-effort event logging without requiring an external tracing system.
