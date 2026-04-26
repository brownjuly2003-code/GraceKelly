# Operator Runbook

Last updated: 2026-04-25

This runbook covers the current operating surface for GraceKelly:
- API authentication
- web UI startup
- browser execution via Perplexity as the primary path
- service liveness and readiness
- metrics scraping
- browser-adapter recovery
- storage validation and task-scoped snapshot restore

It is intentionally limited to the current in-process deployment model.

## Quickstart

1. **Step 1 — Boot**
   Start the backend with the browser runtime enabled:
   ```bash
   set GRACEKELLY_BROWSER_ENABLED=true
   set GRACEKELLY_BROWSER_AUTOMATION_BACKEND=playwright
   set GRACEKELLY_EXECUTION_PROFILE=hybrid
   set GRACEKELLY_BROWSER_PROFILE_DIR=D:\GraceKelly\tmp\browser-recon\perplexity-profile
   python -m uvicorn gracekelly.main:create_app --factory --host 127.0.0.1 --port 8011
   ```
   Keep that process running, then open `http://127.0.0.1:8011/`.

2. **Step 2 — Authenticate browser**
   Bootstrap a dedicated Chrome profile once:
   ```bash
   gracekelly-create-perplexity-profile
   ```
   Finish the Perplexity login manually in that profile, close every Chrome window using it, and reuse the same `GRACEKELLY_BROWSER_PROFILE_DIR` for the backend.

3. **Step 3 — First smoke**
   ```bash
   python scripts/live_smart_smoke.py --pattern smart
   ```
   Expected result: HTTP `200`, a meaningful answer, and roughly `1-3` browser submits for the SMART flow.
   With `GRACEKELLY_EXECUTION_PROFILE=dry-run`, all eight sync routes auto-gate to dry-run execution without requiring `dry_run: true` in the request body.

For deeper operations see the sections below:
- [Ecosystem smoke](#ecosystem-smoke)
- [Windows always-on autostart](#windows-always-on-autostart)
- [Live smoke harness](#live-smoke-harness)
- [Browser triage](#browser-triage)
- [Harness limitations](#harness-limitations)
- [Known integrators](#known-integrators)

## Ecosystem smoke

`scripts/ecosystem_smoke.py` is the single-command health check across the V2 backend
and all three known clients (`RAG_Support_Assistant`, `agent_toolkit`, `juhub`).

```bash
.venv\Scripts\python scripts\ecosystem_smoke.py
```

Step order: pre-flight `:8011/healthz/ready` → V2 direct (`/smart` + `/orchestrate`)
→ RAG smoke (if `:8000` reachable) → agent_toolkit `pytest tests/integration/`
(if `D:\agent_toolkit` exists) → juhub `--dry-run` debate (if
`D:\Perplexity_Orchestrator2\juhub` exists). Missing components are reported as
SKIP, not FAIL. Exit code 0 if every step is PASS or SKIP, 1 on the first FAIL.

Useful flags:

- `--skip-rag`, `--skip-agent-toolkit`, `--skip-juhub` — narrow the run.
- `--gracekelly-url`, `--rag-url` — override base URLs.
- `--verbose` — show each subprocess stdout.

This script does not start uvicorn itself; boot V2 first.

## Windows always-on autostart

`scripts\win-autostart\` ships a Windows Task Scheduler XML and `.bat` helpers to
keep V2 running on user logon. This is optional — purely a convenience for
single-user local deploy where juhub cron at 08:30 and RAG async traffic both rely
on V2 being already up.

Install once, as Administrator:

```cmd
cd D:\GraceKelly\scripts\win-autostart
install_autostart.bat
```

Verify:

```cmd
schtasks /Query /TN "GraceKelly Autostart" /V /FO LIST
```

Switch execution profile without editing files:

```cmd
set_profile.bat hybrid    :: or dry-run / api-only
```

The wrapper `gracekelly_uvicorn.bat` reads `%LOCALAPPDATA%\GraceKelly\profile.env`
on each start; restart the task to pick up changes. Logs land in
`%LOCALAPPDATA%\GraceKelly\uvicorn.log`. Uninstall: `uninstall_autostart.bat`
(also as Administrator). See `scripts\win-autostart\README.md` for full reference
and troubleshooting.

## UI

The built-in web UI is served from the main app at http://127.0.0.1:8011/.
Run the backend, then open that address in the browser.

## API security

### Authentication

Set `GRACEKELLY_API_KEY` to require API key on all protected endpoints. Clients must include one of:
- `Authorization: Bearer <key>` header
- `X-API-Key: <key>` header

Public endpoints (no key required): `/health`, `/docs`, `/openapi.json`, `/redoc`.

When `GRACEKELLY_API_KEY` is not set, all endpoints are open (development default).

## Browser execution (primary)

GraceKelly executes models through your Perplexity Pro subscription via browser automation.
Direct provider APIs remain optional fallbacks when you need separate provider access.

### Setup

1. Create a Chrome profile logged into Perplexity Pro
2. Set in `.env`:
   ```bash
   GRACEKELLY_BROWSER_ENABLED=true
   GRACEKELLY_BROWSER_AUTOMATION_BACKEND=playwright
   GRACEKELLY_BROWSER_PROFILE_DIR=/path/to/chrome/profile
   ```
3. Available models depend on your Perplexity subscription tier

### Circuit breaker

If the browser adapter fails 3 times consecutively, the circuit breaker opens
for 60 seconds. Check `/metrics` for `gracekelly_browser_circuit_breaker_state`.
`MODEL_MISMATCH` does **not** count toward the breaker (Sonar auto-route is
recovered by retry, not by tripping). Only `PROVIDER_UNAVAILABLE`, `TIMEOUT`,
and `UNKNOWN_ERROR` are counted.

Configure via:
- `GRACEKELLY_BROWSER_CIRCUIT_BREAKER_FAILURE_THRESHOLD` (default 3)
- `GRACEKELLY_BROWSER_CIRCUIT_BREAKER_COOLDOWN_SECONDS` (default 60)

### Stability behaviors (2026-04-26)

The browser adapter has three layered protections to keep sessions healthy
across long runs:

- **Cold-start navigation** — initial `page.goto(perplexity.ai)` and home
  re-navigations use a 30s timeout (was 5s). Cold Chromium launches no longer
  fail the first request.
- **Sonar auto-route retry** — when Perplexity overrides the requested model
  to Sonar, the adapter retries `select_model` up to 2 extra times with a
  1.5s delay before returning `MODEL_MISMATCH`. Class constants
  `_MODEL_SELECT_RETRIES` / `_MODEL_SELECT_RETRY_DELAY_S` in
  `adapters/browser/perplexity.py`.
- **Force session reset on exception** — after `TIMEOUT` or unknown
  exceptions, the adapter best-effort-closes Playwright/Chromium so the next
  request relaunches a fresh session. Without this, a degraded session
  cascades through the breaker.
- **Thinking-toggle memoization** — if Perplexity's UI does not surface a
  separate "Thinking" toggle for the active model, the adapter records the
  miss once per session and skips the menu probe on subsequent calls
  (otherwise ~2s wasted per call).
- **Submit click force=True** — the prompt-submit button uses `force=True`
  to bypass actionability waits when an overlay briefly covers it.

Live smoke verification: 12/12 sequential `/api/v1/smart` calls landed clean
(0 failures, 0 warnings, 0 breaker trips) on HEAD `ceeb27d`.

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
- Diagnostics:
  - the adapter logs a structured `browser_auth_unknown` warning with
    url/title/body_length/prompt_input state whenever auth still resolves
    to logged_out after the settle retry. Grep the uvicorn log for
    `browser_auth_unknown` to see the actual page state that defeated the
    auth check.

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
- If an external integrator receives `failure_code: "unknown_error"` with a Playwright traceback while the backend is running with `GRACEKELLY_EXECUTION_PROFILE=dry-run`, treat it as the known dry-run profile-gate regression covered by [docs/audits/2026-04-25-dry-run-gate-audit.md](audits/2026-04-25-dry-run-gate-audit.md).
- Recovery:
  - inspect `browser.perplexity` health details and breaker counters
  - capture fresh DOM recon
  - rerun the live smoke with debug enabled
- Per-call budget is controlled by `GRACEKELLY_BROWSER_CALL_TIMEOUT_SECONDS`
  (default 120s). Raise it for very long prompts or when SMART fan-out
  sub-calls are still within the budget but tight.

Fan-out / decomposition (SMART `used_roles=True` or DEBATE):
- each sub-exec is routed through the same browser session. The adapter
  calls `reset_page_state()` (navigates the UI back to the home
  ask-input) before every submit so consecutive sub-execs do not extract
  stale `body_after_prompt` from the previous thread. If you see
  multiple sub-execs completing with identical output lengths or
  anomalously short durations (&lt;2s) in the log, confirm the "Navigating
  Perplexity UI back to" log line is present between them — if missing,
  the reset pathway itself has regressed.

## Browser recovery commands

Create or refresh a dedicated authenticated profile:

```bash
gracekelly-create-perplexity-profile
```

Capture fresh authenticated recon:

```bash
gracekelly-capture-perplexity-recon --prompt "Reply with only OK" --timeout-seconds 60
```

Run the manual-gated live smoke after the backend is already running with the browser env settings from the Quick Start:

```bash
python scripts/live_smart_smoke.py --pattern smart
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
The export command summary now also echoes `generated_at`, `compressed_output`, `output_exists`, `output_size_bytes`, `manifest_status`, `snapshot_status_consistency_status`, `selection_status`, `missing_task_ids_status`, field-level manifest verification statuses, `requested_task_ids`, `exported_task_ids`, `missing_task_ids`, `task_count`, `step_count`, `event_count`, `repository_health`, and `repository_schema`, so the operator can capture both selection results and storage state without opening the snapshot file immediately.
If export fails after the snapshot manifest was already assembled, the error payload preserves that manifest context too.
If the export path ends with `.gz`, the snapshot is written as gzip-compressed JSON.

Inspect a snapshot artifact offline before restore:

```bash
gracekelly-inspect-snapshot --input D:\GraceKelly\tmp\postgres-export\selected.json
```

That command verifies `snapshot_sha256` when present and reports manifest details such as `manifest_status`, `snapshot_status_consistency_status`, `selection_status`, `missing_task_ids_status`, field-level manifest verification statuses, `selection`, `task_count`, `step_count`, `event_count`, `exported_task_ids`, `missing_task_ids`, `input_size_bytes`, and `import_ready` without requiring database connectivity. If the file cannot be parsed, the error payload still includes `compressed_input` and `input_size_bytes`.

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
It also echoes `compressed_input`, `input_size_bytes`, `source_format_status`, `source_migration_status`, `source_checksum_status`, `source_snapshot_sha256`, `source_import_ready`, `source_status_consistency_status`, `source_manifest_status`, `source_selection_status`, `source_selection`, `source_task_count`, `source_step_count`, `source_event_count`, `source_exported_task_ids`, `source_missing_task_ids`, and `source_missing_task_ids_status`, so the restore report preserves the source artifact manifest context.
Failed import preflights also include `compressed_input`, `input_size_bytes`, and the source compatibility verdict fields derivable from the parsed artifact, so the operator can still identify and classify the rejected snapshot from the error payload.
Compressed `.json.gz` snapshot input is supported directly.

## Live smoke harness

`scripts/live_smart_smoke.py` is a manual-gated operator harness for end-to-end browser-backed smoke checks. It is not scheduled and is not part of CI; run it only when you explicitly want to spend live browser quota.

### Preconditions

1. Chrome profile is already authenticated to Perplexity Pro, for example `D:/GraceKelly/chrome-profile/`.
2. Uvicorn is running on `http://127.0.0.1:8011/` with at least:
   ```powershell
   $env:GRACEKELLY_BROWSER_ENABLED="true"
   $env:GRACEKELLY_EXECUTION_PROFILE="hybrid"
   ```
3. No other `chrome.exe` process is using that profile:
   ```powershell
   Get-CimInstance Win32_Process -Filter "name = 'chrome.exe'" |
     Where-Object { $_.CommandLine -like '*D:\\GraceKelly\\chrome-profile*' } |
     Select-Object ProcessId, CommandLine
   ```
   The command should return no rows before you launch the smoke.

### Supported patterns

| Pattern | API path | UI label | Default prompt summary | Expected quota | Min answer length |
| --- | --- | --- | --- | --- | --- |
| `smart` | `/api/v1/smart` | `Умный выбор` | EV market comparison across Europe, USA, China | 1-3 submits | 500 chars |
| `debate` | `/api/v1/debate` | `Дебаты` | EV market comparison with challenge/defense loop | 3-5 submits | 500 chars |
| `consensus` | `/api/v1/consensus` | not surfaced; direct POST fallback | 3 leading EV manufacturers in China | 3-5 submits | 300 chars |
| `compare` | `/api/v1/compare` | not surfaced; direct POST fallback | Claude Sonnet 4.6 vs GPT-5.4 reasoning comparison | 5 submits | 400 chars |
| `upload` | `/api/v1/orchestrate/upload` | n/a; composer attachment flow | summarize attached file | 1 submit | 150 chars |

Quota expectations are approximate and assume a healthy authenticated browser session. `smart` may fan out into 1-3 submits, `debate` usually needs 3-5, `consensus` usually needs 3-5, `compare` fans out across five models, and `upload` is expected to be a single submit.

### Usage examples

```powershell
python scripts/live_smart_smoke.py --pattern smart
python scripts/live_smart_smoke.py --pattern debate
python scripts/live_smart_smoke.py --pattern consensus
python scripts/live_smart_smoke.py --pattern compare
python scripts/live_smart_smoke.py --pattern upload --attachment <path>
```

### Artifacts and interpretation

Reports are written to `.workflow/outbox/<tag>-<PATTERN>-report.md` and raw payloads to `.workflow/outbox/<tag>-<PATTERN>-response.json`.

`Status: success` means the harness completed prompt-to-response end-to-end and the evaluator accepted the pattern-specific response without `AUTH_FAILED`, `shell-chrome`, forbidden markers, or length/topic failures.

`Status: failure` means the report contains explicit rejection reasons such as non-200 status, missing answer field, too-short output, forbidden markers, or missing topic keywords. Inspect the paired `response.json` to see the captured HTTP status and the raw response body fields that the evaluator examined.

### Coverage notes

Fallback behaviour is validated via unit-tests in `tests/test_router_fallback.py`, not through the live harness; browser-adapter failure is not reproduced artificially in smoke runs.

This harness does not cover `smart/v2`, `batch`, or `pipeline`. Those paths stay validated through unit tests and route-level smoke coverage such as `tests/test_routes_*`.

## Harness limitations

### Cyrillic prompts via PowerShell pipe

When the harness or any other CLI tool passes a cyrillic prompt through a PowerShell pipe
(`echo 'привет' | python ...`), PowerShell's default encoding can downgrade the text to `?`
placeholders before the child process sees it. That is a PowerShell / harness issue, not a
GraceKelly backend bug.

Workarounds:
- pass the prompt directly with `--prompt`, for example `python scripts/live_smart_smoke.py --prompt "привет"`
- set `$OutputEncoding = [System.Text.Encoding]::UTF8` before piping in the current session
- use `--ascii-fallback` for deterministic ASCII smoke prompts

Reference incident: Phase 17 / batch-82 live SMART failure recorded in `docs/phased-roadmap.md`.

### Persistent session reuse

Authentication is persisted through the dedicated Chrome profile directory (default
`chrome-profile/`, configurable via `GRACEKELLY_BROWSER_PROFILE_DIR`). There is no separate session
token file to rotate or copy.

If another Chrome process is still using that profile, startup can fail with the live-profile guard
or `BrowserProfileBusyError`. Use a dedicated profile created by `gracekelly-create-perplexity-profile`
and follow `docs/onboarding.md` for the bootstrap / recovery flow.

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

## Health endpoint security

The `GET /health` endpoint returns a minimal summary by default (status, environment, backend name, saturation counts). Internal component details are hidden.

To expose full details (storage schema, browser circuit-breaker state, adapter keys present/absent):

```bash
set GRACEKELLY_HEALTH_EXPOSE_DETAILS=true
```

Security implications:
- The detailed view reveals which adapters have API keys configured and whether the browser session is authenticated.
- Keep `GRACEKELLY_HEALTH_EXPOSE_DETAILS=false` (default) in any internet-facing deployment.
- The detailed view is safe on an internal monitoring network or when the health endpoint is behind API key authentication.
- `GET /api/v1/health/detailed` always returns full adapter and embeddings status; protect it with `GRACEKELLY_API_KEY` if health endpoints are public.

## Request timeout (orchestrate)

`POST /api/v1/orchestrate` runs synchronously in a thread pool. To cap execution time and return HTTP 504 to the caller instead of holding the connection indefinitely:

```bash
set GRACEKELLY_ORCHESTRATE_TIMEOUT_SECONDS=60
```

Setting `0` (default) disables the timeout.

How it works:
- The orchestration coroutine is wrapped in `asyncio.wait_for` with the configured timeout.
- On breach, the endpoint returns `504 Gateway Timeout` with `detail: "Orchestration request timed out."`
- The background thread continues running until the underlying adapter call completes or fails on its own - the timeout only affects the HTTP response, not the execution itself.

Tuning guidance:
- Start with the slowest expected model timeout + 10 s of overhead (e.g. Anthropic 120 s -> set 130 s).
- For dry-run mode, 5 s is sufficient.
- For consensus V2 with multiple rounds, account for `max_rounds x variations_per_round x model_timeout_seconds`.
- Pair this setting with load-balancer / reverse-proxy timeouts: both must be larger than the orchestrate timeout.

## Known integrators

V2 is the only active orchestrator. All three known clients run on `http://127.0.0.1:8011`:

- **`RAG_Support_Assistant`** (`D:\RAG_Support_Assistant`, port 8000)
  - Smoke: `python D:\RAG_Support_Assistant\scripts\gracekelly_smoke.py`
  - Failover provider: ollama (when V2 returns 5xx).
- **`agent_toolkit`** (`D:\agent_toolkit`)
  - LangGraph wrapper (`OrchestratorChatModel`) → V2 endpoints by `GKPattern`.
  - Test: `cd D:\agent_toolkit && uv run pytest tests/integration/`
- **`juhub`** (`D:\Perplexity_Orchestrator2\juhub`, scheduled 08:30 daily)
  - `backend/scheduler.py` does pre-flight `:8011/healthz/ready`; if V2 is down, the run is skipped with an error log (no auto-start).
  - Manual dry-run: `cd D:\Perplexity_Orchestrator2 && set GK_DRY_RUN=1 && python -m juhub.backend.scheduler --now`

Legacy V1 orchestrator at `D:\Perplexity_Orchestrator2` (`:8001`, `/api/gk/*`) is deprecated 2026-04-25 and not used by any client. See `D:\Perplexity_Orchestrator2\DEPRECATED.md`.
