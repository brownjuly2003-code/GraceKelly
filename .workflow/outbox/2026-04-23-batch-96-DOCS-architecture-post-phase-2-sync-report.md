# DOCS-architecture-post-phase-2-sync

Status: success

What changed:
- Added post-Phase-2 capability bullets to `docs/architecture.md` for browser budgeting, session-aware prompt shaping, observability hooks, auxiliary HTTP surfaces, and audit snapshots.
- Added missing module references to the module-boundary section for:
  - `api.routes.analytics`
  - `api.routes.health_detailed`
  - `core.budget`
  - `core.session_context`
  - `request_metrics`
  - `telemetry`
- Kept the existing layered structure intact and only appended targeted bullets in the matching sections.

Added module references:
- `api.routes.analytics`: aggregate model performance stats from recent task and step history.
- `api.routes.health_detailed`: detailed adapter and embeddings health endpoint.
- `core.budget`: per-task and per-hour browser submit budgeting.
- `core.session_context`: bounded session-history reconstruction for follow-up prompts.
- `request_metrics`: in-process HTTP and adapter metrics backing `/metrics`.
- `telemetry`: optional OpenTelemetry setup for FastAPI.
- `docs/audits/`: referenced once in current scope as the location for post-phase audit snapshots.

Verification:
- Re-read `docs/architecture.md` after edits and confirmed there are no new references to missing modules in the added bullets.
- Existing references such as `adapters.browser.scripted` and the current storage/adapter modules were preserved.
- Repo test verification was attempted with `D:\GraceKelly\.venv\Scripts\python.exe -m pytest -q` and timed out twice (124s, then 604s), so no green-test claim is made for this batch.

Scope:
- `docs/architecture.md`
