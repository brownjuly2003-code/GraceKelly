# API Behavioural Divergence
Date: 2026-04-23
Status: behavioural matrix complete
Source of endpoint list: `01-inventory.md` section `## 1. HTTP endpoints`

## Intro

This document covers HTTP behaviour only: routing defaults, error surface, streaming, sync vs async execution, retry semantics, idempotency, auth / middleware, and observability hooks.

Pairing rule used here:
- Exact pair when both projects expose the same operational role at HTTP level (`/health`, analytics overview, main orchestration entrypoint, task list/detail, retry/resume-like flows).
- When one project multiplexes several behaviours behind one route and the other project splits them into multiple routes, this document stays at HTTP-surface level and treats the split routes as one-sided families. Semantic pattern equivalence is deferred to `04-06`.
- One-sided endpoints are grouped by route family only when the family shares one handler style; every covered path is listed explicitly in the section header.

Severity legend:
- `high`: breaking or silent behavioural change likely to affect clients or operators.
- `medium`: visible operational mismatch with a viable workaround.
- `low`: surface mismatch with limited client impact.
- `none`: no material divergence found.

## GET /health

### Orchestrator2 behaviour
- `Routing defaults`: no parameters; the handler always instantiates `AccountPool`, counts accounts with sessions, and maps `available > 0` to `status="ok"`, else `status="degraded"`. Evidence: `api/routes/health.py:10`, `api/routes/health.py:21`.
- `Error surface`: any exception is swallowed and returned as a `200` JSON body with `status="error"` and an `error` string instead of a `5xx`. Evidence: `api/routes/health.py:20`, `api/routes/health.py:33`.
- `Streaming`: none. Evidence: `api/routes/health.py:10`.
- `Sync vs async`: `async def`, but the account-pool work is synchronous and runs on the event loop thread. Evidence: `api/routes/health.py:11`, `api/routes/health.py:21`.
- `Retry semantics`: none in the route. Evidence: `api/routes/health.py:20`.
- `Idempotency`: read-only and effectively idempotent, except live account/session counts can change between calls. Evidence: `api/routes/health.py:21`.
- `Auth / middleware`: no auth middleware is registered; global CORS is `allow_origins=["*"]` with `allow_credentials=False`. Evidence: `api/main.py:116`.
- `Observability hooks`: startup enables DB init and monitoring, but the handler itself emits no logs or metrics. Evidence: `api/main.py:56`, `api/main.py:80`.

### GraceKelly behaviour
- `Routing defaults`: no parameters; the route builds a readiness-derived health summary, but by default only returns `{"status": ...}` because `health_expose_details` defaults to `false`. Evidence: `src/gracekelly/api/routes/health.py:317`, `src/gracekelly/config.py:208`.
- `Error surface`: degraded states still return `200`; there is no broad local catch, so unexpected failures fall through to the app-level exception handlers instead of being masked inside a success body. Evidence: `src/gracekelly/api/routes/health.py:321`, `src/gracekelly/main.py:306`.
- `Streaming`: none. Evidence: `src/gracekelly/api/routes/health.py:316`.
- `Sync vs async`: `async def`, but readiness/summary building is explicitly offloaded with `asyncio.to_thread`. Evidence: `src/gracekelly/api/routes/health.py:324`.
- `Retry semantics`: none in the route. Evidence: `src/gracekelly/api/routes/health.py:317`.
- `Idempotency`: read-only and effectively idempotent, except live readiness and saturation metrics can drift. Evidence: `src/gracekelly/api/routes/health.py:333`.
- `Auth / middleware`: `/health` is explicitly public, but still receives security headers, request metrics, and `X-Request-ID`. Evidence: `src/gracekelly/middleware.py:15`, `src/gracekelly/middleware.py:60`, `src/gracekelly/middleware.py:83`, `src/gracekelly/middleware.py:97`.
- `Observability hooks`: degraded or saturated snapshots are logged; Sentry and OTEL can be attached globally. Evidence: `src/gracekelly/api/routes/health.py:334`, `src/gracekelly/main.py:329`, `src/gracekelly/main.py:414`.

### Behavioural divergence

| Axis | Orchestrator2 | GraceKelly | Notes |
|---|---|---|---|
| Routing defaults | Direct account-pool summary | Readiness-derived summary with detail gate | GK hides internals unless config enables them |
| Error surface | `200` with `status="error"` body | `200` for degraded state, app-level handlers for real failures | O2 masks exceptions more aggressively |
| Streaming | None | None | Same |
| Sync / async | Async wrapper over sync work | Async wrapper with explicit thread offload | GK is safer for blocking health calculations |
| Retry | None | None | Same |
| Idempotency | Read-only | Read-only | Same class |
| Auth / middleware | Open + wildcard CORS | Public route, but with headers/metrics/request-id | Middleware stack differs materially |
| Observability | Startup monitoring only | Warning logs + optional Sentry/OTEL | GK is more operator-facing here |

### Severity hint

`medium` - both routes are health checks, but Orchestrator2 converts internal failures into `200` payloads while GraceKelly treats degraded state and genuine failure as different surfaces.

## GET /api/v1/analytics <-> GET /api/analytics/overview

### Orchestrator2 behaviour
- `Routing defaults`: no parameters; the route opens SQLite and returns totals, 24h counters, per-model counts, and per-hour buckets. Evidence: `api/routes/analytics.py:29`, `api/routes/analytics.py:35`.
- `Error surface`: DB-open failure or any later exception falls back to a mock `200` payload with zeros instead of a `5xx`. Evidence: `api/routes/analytics.py:36`, `api/routes/analytics.py:99`, `api/routes/analytics.py:251`.
- `Streaming`: none. Evidence: `api/routes/analytics.py:29`.
- `Sync vs async`: `async def`, but all `sqlite3` access is synchronous on the event loop. Evidence: `api/routes/analytics.py:22`, `api/routes/analytics.py:40`.
- `Retry semantics`: none. Evidence: `api/routes/analytics.py:35`.
- `Idempotency`: read-only and idempotent except for live DB contents. Evidence: `api/routes/analytics.py:45`.
- `Auth / middleware`: open endpoint under global wildcard CORS; no auth layer. Evidence: `api/main.py:116`.
- `Observability hooks`: errors are printed with `[Analytics] ...` and otherwise not surfaced to metrics/logging infrastructure. Evidence: `api/routes/analytics.py:102`.

### GraceKelly behaviour
- `Routing defaults`: no parameters; the route aggregates up to 100 recent tasks from the repository and falls back to `execution_history` when repository records are absent. Evidence: `src/gracekelly/api/routes/analytics.py:45`, `src/gracekelly/api/routes/analytics.py:50`, `src/gracekelly/api/routes/analytics.py:67`.
- `Error surface`: storage read failures become HTTP `503 "Storage unavailable."`; no mock success payload is returned. Evidence: `src/gracekelly/api/routes/analytics.py:63`.
- `Streaming`: none. Evidence: `src/gracekelly/api/routes/analytics.py:31`.
- `Sync vs async`: `def` handler; FastAPI runs the sync function off the event loop while repository access stays synchronous. Evidence: `src/gracekelly/api/routes/analytics.py:45`.
- `Retry semantics`: none. Evidence: `src/gracekelly/api/routes/analytics.py:45`.
- `Idempotency`: read-only and idempotent except for live repository/history contents. Evidence: `src/gracekelly/api/routes/analytics.py:77`.
- `Auth / middleware`: protected when API key auth is configured; also inherits request-id, metrics, and optional Redis `429` handling. Evidence: `src/gracekelly/middleware.py:24`, `src/gracekelly/middleware.py:97`, `src/gracekelly/middleware.py:108`.
- `Observability hooks`: storage failures are logged via `logger.error`; global request metrics still record the endpoint. Evidence: `src/gracekelly/api/routes/analytics.py:64`, `src/gracekelly/request_metrics.py:24`.

### Behavioural divergence

| Axis | Orchestrator2 | GraceKelly | Notes |
|---|---|---|---|
| Routing defaults | SQLite overview + mock fallback | Repository/history aggregation | Different backing stores and fallback strategy |
| Error surface | Silent `200` mock payloads | Explicit `503` on storage failure | This changes monitoring semantics materially |
| Streaming | None | None | Same |
| Sync / async | Async + sync sqlite on loop | Sync route off loop | Different blocking profile |
| Retry | None | None | Same |
| Idempotency | Read-only | Read-only | Same class |
| Auth / middleware | Open + CORS | Protected + request middleware stack | Different access contract |
| Observability | Print-only error path | Logged error path + request metrics | GK is easier to monitor |

### Severity hint

`medium` - clients and dashboards see very different outage semantics: Orchestrator2 hides DB failures behind mock `200` payloads, GraceKelly returns a hard `503`.

## POST /api/v1/orchestrate <-> POST /orchestrate

### Orchestrator2 behaviour
- `Routing defaults`: `level` defaults to `STANDARD`, `model` defaults to `None`, and `mirror_telegram` defaults to `false`; the route creates a new in-memory task and returns immediately with `status="pending"`. Evidence: `api/routes/orchestrate.py:49`, `api/routes/orchestrate.py:425`, `api/routes/orchestrate.py:432`.
- `Error surface`: the initial HTTP response is almost always `200`; execution failures appear later in task state (`status="failed"`, `error=...`) rather than as synchronous `4xx/5xx` responses. Evidence: `api/routes/orchestrate.py:217`, `api/routes/orchestrate.py:251`, `api/routes/orchestrate.py:464`.
- `Streaming`: no HTTP streaming on this route; progress is pushed through the websocket broadcaster. Evidence: `api/routes/orchestrate.py:219`, `api/routes/websocket.py:19`.
- `Sync vs async`: `async def` that schedules `BackgroundTasks`; the real orchestration runs asynchronously after the request returns. Evidence: `api/routes/orchestrate.py:425`, `api/routes/orchestrate.py:455`.
- `Retry semantics`: per-model browser calls use `execute_with_retry(... max_retries=2)`; orchestration levels can also fan out across multiple models and consensus loops. Evidence: `api/routes/orchestrate.py:154`, `api/routes/orchestrate.py:263`, `api/routes/orchestrate.py:268`.
- `Idempotency`: non-idempotent; every POST allocates a new `task_id` and enqueues new background work. Evidence: `api/routes/orchestrate.py:432`.
- `Auth / middleware`: open endpoint under wildcard CORS; no auth or rate limiting. Evidence: `api/main.py:116`.
- `Observability hooks`: progress is broadcast over websocket, successful/failed model calls are logged to DB, model stats are updated, and Telegram mirroring is optional. Evidence: `api/routes/orchestrate.py:168`, `api/routes/orchestrate.py:219`, `api/routes/orchestrate.py:310`.

### GraceKelly behaviour
- `Routing defaults`: the request must include `model` or `models`; defaults are `adapter_hint=auto`, `quorum=1`, `merge_strategy=first_success`, `cancel_on_quorum=true`, `reasoning=false`, `dry_run=false`, and `decompose=true`; the route returns the final task snapshot synchronously. Evidence: `src/gracekelly/schemas.py:14`, `src/gracekelly/api/routes/orchestrate.py:233`.
- `Error surface`: validation errors are `422`, unsupported capability is `501`, storage/auth issues are `503`, timeout is `504`, and unexpected failures are `500` with structured `{code,message,trace_id}` detail. Evidence: `src/gracekelly/api/routes/orchestrate.py:244`, `src/gracekelly/api/routes/orchestrate.py:295`, `src/gracekelly/api/routes/orchestrate.py:303`, `src/gracekelly/api/routes/orchestrate.py:347`, `src/gracekelly/api/routes/orchestrate.py:369`, `src/gracekelly/api/routes/orchestrate.py:382`.
- `Streaming`: this route is non-streaming; streaming is split into a dedicated SSE endpoint. Evidence: `src/gracekelly/api/routes/orchestrate.py:233`, `src/gracekelly/api/routes/stream.py:127`.
- `Sync vs async`: `async def`, but the blocking `submit_snapshot` call is pushed to an executor and wrapped in `asyncio.wait_for` when a timeout is configured. Evidence: `src/gracekelly/api/routes/orchestrate.py:273`, `src/gracekelly/api/routes/orchestrate.py:277`.
- `Retry semantics`: no route-level HTTP retry loop; the route only waits for one submission attempt and cancels the future on timeout. Evidence: `src/gracekelly/api/routes/orchestrate.py:276`.
- `Idempotency`: non-idempotent; each request persists a new task snapshot and can emit a new trace id/header. Evidence: `src/gracekelly/api/routes/orchestrate.py:255`, `src/gracekelly/api/routes/orchestrate.py:330`.
- `Auth / middleware`: protected by API key when configured, plus request-id propagation, request metrics, security headers, and optional Redis-backed rate limiting. Evidence: `src/gracekelly/middleware.py:24`, `src/gracekelly/middleware.py:60`, `src/gracekelly/middleware.py:83`, `src/gracekelly/middleware.py:97`, `src/gracekelly/middleware.py:108`.
- `Observability hooks`: structured request/accepted/failure logs, optional Sentry, and optional OTEL instrumentation. Evidence: `src/gracekelly/api/routes/orchestrate.py:258`, `src/gracekelly/api/routes/orchestrate.py:318`, `src/gracekelly/api/routes/orchestrate.py:374`, `src/gracekelly/main.py:329`, `src/gracekelly/main.py:414`.

### Behavioural divergence

| Axis | Orchestrator2 | GraceKelly | Notes |
|---|---|---|---|
| Routing defaults | `STANDARD` async background task | Synchronous final snapshot, requires model selection | Different client contract from the first byte |
| Error surface | Initial `200`; failures move to later task status | Immediate `422/501/503/504/500` surface | Breaking difference for API consumers |
| Streaming | Websocket side-channel only | Separate SSE endpoint, not this route | Different transport split |
| Sync / async | Fire-and-poll background model | Waits for executor completion in-request | Latency and timeout semantics differ sharply |
| Retry | Worker retries + orchestration loops | No route retry; single submission wait | Different failure recovery profile |
| Idempotency | New task every call | New task every call | Same non-idempotent class |
| Auth / middleware | Open + CORS | Protected + metrics/request-id/rate-limit | Operationally very different |
| Observability | DB stats + websocket + Telegram | Structured logs + Sentry/OTEL + task repo | Both observable, but in different places |

### Severity hint

`high` - these are the main orchestration entrypoints, but one is fire-and-poll background work and the other is synchronous final-result RPC with explicit HTTP failure codes.

## GET /api/v1/tasks <-> GET /tasks

### Orchestrator2 behaviour
- `Routing defaults`: no parameters; the route returns a debug list of every in-memory orchestration task with only `task_id`, `status`, and `created_at`. Evidence: `api/routes/orchestrate.py:484`.
- `Error surface`: no explicit error handling; the handler returns `200` with `count` and `tasks`. Evidence: `api/routes/orchestrate.py:485`.
- `Streaming`: none. Evidence: `api/routes/orchestrate.py:484`.
- `Sync vs async`: `async def`, but it only reads the in-memory `tasks` dict synchronously. Evidence: `api/routes/orchestrate.py:485`.
- `Retry semantics`: none. Evidence: `api/routes/orchestrate.py:485`.
- `Idempotency`: read-only and idempotent except for live task churn. Evidence: `api/routes/orchestrate.py:487`.
- `Auth / middleware`: open endpoint under wildcard CORS. Evidence: `api/main.py:116`.
- `Observability hooks`: none in the handler. Evidence: `api/routes/orchestrate.py:485`.

### GraceKelly behaviour
- `Routing defaults`: defaults are `limit=20`, optional filters for `status`, `execution_mode`, `dry_run`, `failure_code`, `before`, and `prompt_contains`; the route returns rich task summaries with steps/events-derived metadata. Evidence: `src/gracekelly/api/routes/orchestrate.py:593`, `src/gracekelly/api/routes/orchestrate.py:607`.
- `Error surface`: storage failures become HTTP `503`; invalid query values are validated by FastAPI before handler logic. Evidence: `src/gracekelly/api/routes/orchestrate.py:603`, `src/gracekelly/api/routes/orchestrate.py:647`.
- `Streaming`: none. Evidence: `src/gracekelly/api/routes/orchestrate.py:593`.
- `Sync vs async`: `async def`, but task loading is offloaded through `asyncio.to_thread`. Evidence: `src/gracekelly/api/routes/orchestrate.py:624`.
- `Retry semantics`: none in the route. Evidence: `src/gracekelly/api/routes/orchestrate.py:607`.
- `Idempotency`: read-only and idempotent except for live repository contents. Evidence: `src/gracekelly/api/routes/orchestrate.py:621`.
- `Auth / middleware`: protected when API key auth is enabled; request-id, metrics, and optional rate limiting apply. Evidence: `src/gracekelly/middleware.py:24`, `src/gracekelly/middleware.py:97`, `src/gracekelly/middleware.py:108`.
- `Observability hooks`: the route logs a structured `tasks.list` event with result count and applied filters. Evidence: `src/gracekelly/api/routes/orchestrate.py:635`.

### Behavioural divergence

| Axis | Orchestrator2 | GraceKelly | Notes |
|---|---|---|---|
| Routing defaults | No params, debug dump | Rich filters + keyset cursor | GK is a real list API, O2 is a debug view |
| Error surface | Bare `200` list | Explicit `503` on storage failure | Different operational expectations |
| Streaming | None | None | Same |
| Sync / async | Async + sync dict | Async + thread offload | Different scalability profile |
| Retry | None | None | Same |
| Idempotency | Read-only | Read-only | Same class |
| Auth / middleware | Open | Protected + middleware stack | Different access contract |
| Observability | None | Structured list log | GK exposes operator context |

### Severity hint

`high` - both paths are task-list endpoints, but Orchestrator2 is a debug dump over volatile in-memory state while GraceKelly exposes a filtered repository-backed API.

## GET /api/v1/tasks/{task_id} <-> GET /status/{task_id}

### Orchestrator2 behaviour
- `Routing defaults`: path-only input; the route looks up one in-memory task and returns progress counters, current step, result, and error. Evidence: `api/routes/orchestrate.py:464`.
- `Error surface`: missing task is HTTP `404`; otherwise the body is always `200` even if the task itself failed. Evidence: `api/routes/orchestrate.py:467`.
- `Streaming`: none on HTTP; websocket is separate. Evidence: `api/routes/orchestrate.py:464`, `api/routes/websocket.py:41`.
- `Sync vs async`: `async def` over synchronous in-memory dict access. Evidence: `api/routes/orchestrate.py:465`.
- `Retry semantics`: none in the status route. Evidence: `api/routes/orchestrate.py:465`.
- `Idempotency`: read-only and idempotent except for live task progress/result drift. Evidence: `api/routes/orchestrate.py:470`.
- `Auth / middleware`: open endpoint under wildcard CORS. Evidence: `api/main.py:116`.
- `Observability hooks`: none in the handler itself. Evidence: `api/routes/orchestrate.py:465`.

### GraceKelly behaviour
- `Routing defaults`: path plus optional `events_limit` and `events_offset`; task ids must match a UUID pattern before the handler runs. Evidence: `src/gracekelly/api/routes/orchestrate.py:666`, `src/gracekelly/api/routes/orchestrate.py:682`.
- `Error surface`: missing task is `404`; storage failure is `503`; the returned `TaskView` includes full step/event history and terminal summaries. Evidence: `src/gracekelly/api/routes/orchestrate.py:675`, `src/gracekelly/api/routes/orchestrate.py:703`, `src/gracekelly/schemas.py:223`.
- `Streaming`: none. Evidence: `src/gracekelly/api/routes/orchestrate.py:666`.
- `Sync vs async`: `async def`, but repository reads are offloaded to threads. Evidence: `src/gracekelly/api/routes/orchestrate.py:688`.
- `Retry semantics`: none in the detail route. Evidence: `src/gracekelly/api/routes/orchestrate.py:680`.
- `Idempotency`: read-only and idempotent except for live repository/event pagination drift. Evidence: `src/gracekelly/api/routes/orchestrate.py:686`.
- `Auth / middleware`: protected when API key auth is enabled; request-id, metrics, and optional rate limiting apply. Evidence: `src/gracekelly/middleware.py:24`, `src/gracekelly/middleware.py:97`, `src/gracekelly/middleware.py:108`.
- `Observability hooks`: structured `task.get` logs include status, step count, event count, and execution mode. Evidence: `src/gracekelly/api/routes/orchestrate.py:692`.

### Behavioural divergence

| Axis | Orchestrator2 | GraceKelly | Notes |
|---|---|---|---|
| Routing defaults | Path-only progress view | UUID path + paginated events | GK returns much richer state |
| Error surface | `404` or `200` current task snapshot | `404/503` plus full task view | Storage failures are explicit only in GK |
| Streaming | None | None | Same |
| Sync / async | Async + sync dict | Async + thread offload | Different blocking profile |
| Retry | None | None | Same |
| Idempotency | Read-only | Read-only | Same class |
| Auth / middleware | Open | Protected + middleware stack | Different access contract |
| Observability | None | Structured detail log | GK provides better operator traceability |

### Severity hint

`high` - both are task-detail endpoints, but Orchestrator2 exposes a volatile progress snapshot while GraceKelly exposes durable task/step/event history with explicit storage failures.

## POST /api/v1/tasks/{task_id}/retry <-> POST /api/tasks/{task_id}/resume

### Orchestrator2 behaviour
- `Routing defaults`: path-only input; the route loads a complex task, picks the first logged-in account, and schedules background execution from the current progress point. Evidence: `api/routes/tasks.py:225`, `api/routes/tasks.py:236`, `api/routes/tasks.py:247`.
- `Error surface`: missing task is `404`; no logged-in accounts is `503`; success returns `200` with `status="resuming"` and a progress snapshot, not a final result. Evidence: `api/routes/tasks.py:232`, `api/routes/tasks.py:241`, `api/routes/tasks.py:250`.
- `Streaming`: none. Evidence: `api/routes/tasks.py:225`.
- `Sync vs async`: `async def`, but it only schedules a background task; actual execution happens later. Evidence: `api/routes/tasks.py:247`.
- `Retry semantics`: no per-request retry loop; it resumes background work once. Evidence: `api/routes/tasks.py:247`.
- `Idempotency`: non-idempotent; each call schedules another background execution attempt. Evidence: `api/routes/tasks.py:247`.
- `Auth / middleware`: open endpoint under wildcard CORS. Evidence: `api/main.py:116`.
- `Observability hooks`: none beyond the returned progress message. Evidence: `api/routes/tasks.py:250`.

### GraceKelly behaviour
- `Routing defaults`: path-only input; the route reloads the original orchestration task, reconstructs an `OrchestrateRequest` from steps/events, and executes the retry synchronously to completion. Evidence: `src/gracekelly/api/routes/orchestrate.py:742`, `src/gracekelly/api/routes/orchestrate.py:781`, `src/gracekelly/api/routes/orchestrate.py:816`.
- `Error surface`: missing task is `404`; storage failure is `503`; retrying a non-failed/non-cancelled task is `409`; reconstructed-request validation issues are `422`. Evidence: `src/gracekelly/api/routes/orchestrate.py:753`, `src/gracekelly/api/routes/orchestrate.py:770`, `src/gracekelly/api/routes/orchestrate.py:775`, `src/gracekelly/api/routes/orchestrate.py:798`.
- `Streaming`: none. Evidence: `src/gracekelly/api/routes/orchestrate.py:742`.
- `Sync vs async`: `async def`, but the submission is run in an executor and awaited before responding. Evidence: `src/gracekelly/api/routes/orchestrate.py:790`.
- `Retry semantics`: this is the explicit retry endpoint; it creates exactly one new retry task linked by `retry_of_task_id`, with no HTTP-level loop. Evidence: `src/gracekelly/api/routes/orchestrate.py:794`.
- `Idempotency`: non-idempotent; every retry call creates a brand-new retry task id. Evidence: `src/gracekelly/api/routes/orchestrate.py:805`.
- `Auth / middleware`: protected when API key auth is enabled; request-id, metrics, and optional rate limiting apply. Evidence: `src/gracekelly/middleware.py:24`, `src/gracekelly/middleware.py:97`, `src/gracekelly/middleware.py:108`.
- `Observability hooks`: structured `task.retry.requested` and `task.retry.accepted` logs. Evidence: `src/gracekelly/api/routes/orchestrate.py:782`, `src/gracekelly/api/routes/orchestrate.py:801`.

### Behavioural divergence

| Axis | Orchestrator2 | GraceKelly | Notes |
|---|---|---|---|
| Routing defaults | Resume complex task in background | Reconstruct and synchronously rerun orchestration task | Only loosely equivalent operational role |
| Error surface | `404/503` or `200 resuming` | `404/409/422/503` or final snapshot | Very different client workflow |
| Streaming | None | None | Same |
| Sync / async | Background resume | Awaited synchronous retry | Different latency semantics |
| Retry | Schedules one resume | Schedules one new retry task | Same high-level idea, different object model |
| Idempotency | Non-idempotent | Non-idempotent | Same class |
| Auth / middleware | Open | Protected + middleware stack | Different access contract |
| Observability | Minimal | Structured retry logs | GK is more explicit |

### Severity hint

`high` - both endpoints restart work, but they operate on different task models and return different lifecycle states (`resuming` background vs completed retry snapshot).

## GET /api/v1/health/detailed <-> GET /health/db

### Orchestrator2 behaviour
- `Routing defaults`: no parameters; the route asks the monitor for a DB health report and migration recommendation. Evidence: `api/routes/health.py:42`, `api/routes/health.py:50`.
- `Error surface`: any exception is swallowed and returned as a `200` body with `status="error"` and `needs_migration=false`. Evidence: `api/routes/health.py:50`, `api/routes/health.py:53`.
- `Streaming`: none. Evidence: `api/routes/health.py:42`.
- `Sync vs async`: `async def`, but monitor access is synchronous. Evidence: `api/routes/health.py:43`, `api/routes/health.py:51`.
- `Retry semantics`: none. Evidence: `api/routes/health.py:50`.
- `Idempotency`: read-only and effectively idempotent except for live DB/monitor state. Evidence: `api/routes/health.py:51`.
- `Auth / middleware`: open endpoint under wildcard CORS. Evidence: `api/main.py:116`.
- `Observability hooks`: global monitoring is started at app startup; the route itself emits no logs. Evidence: `api/main.py:80`.

### GraceKelly behaviour
- `Routing defaults`: no parameters; the route enumerates API adapter key presence, embeddings client status, and uptime, then returns `healthy` only when every adapter and embeddings client report `ok`. Evidence: `src/gracekelly/api/routes/health_detailed.py:32`, `src/gracekelly/api/routes/health_detailed.py:43`.
- `Error surface`: no local catch; failures would surface through the app-level exception handlers rather than being folded into a success body. Evidence: `src/gracekelly/api/routes/health_detailed.py:43`, `src/gracekelly/main.py:306`.
- `Streaming`: none. Evidence: `src/gracekelly/api/routes/health_detailed.py:32`.
- `Sync vs async`: `def` handler; FastAPI runs it off the event loop while adapter/embeddings checks stay synchronous. Evidence: `src/gracekelly/api/routes/health_detailed.py:43`.
- `Retry semantics`: none. Evidence: `src/gracekelly/api/routes/health_detailed.py:43`.
- `Idempotency`: read-only and effectively idempotent except for live adapter availability and uptime. Evidence: `src/gracekelly/api/routes/health_detailed.py:55`, `src/gracekelly/api/routes/health_detailed.py:67`.
- `Auth / middleware`: protected unless API key auth is disabled; inherits security headers, request-id, metrics, and optional rate limiting. Evidence: `src/gracekelly/middleware.py:24`, `src/gracekelly/middleware.py:60`, `src/gracekelly/middleware.py:97`, `src/gracekelly/middleware.py:108`.
- `Observability hooks`: no local logs, but global request metrics still see the endpoint. Evidence: `src/gracekelly/request_metrics.py:24`.

### Behavioural divergence

| Axis | Orchestrator2 | GraceKelly | Notes |
|---|---|---|---|
| Routing defaults | DB monitor view | Adapter + embeddings + uptime view | Scope differs even though both are "detailed health" |
| Error surface | `200` error body | App-level exception path | O2 hides failures more aggressively |
| Streaming | None | None | Same |
| Sync / async | Async + sync monitor call | Sync route off loop | Different blocking profile |
| Retry | None | None | Same |
| Idempotency | Read-only | Read-only | Same class |
| Auth / middleware | Open | Protected + middleware stack | Different access contract |
| Observability | Startup monitor only | Request metrics only | Different operator signal source |

### Severity hint

`medium` - both are operational health endpoints, but they describe different subsystems and expose failures through different HTTP surfaces.

## GraceKelly-only operational health surfaces

Covered endpoints: `GET /healthz/live`, `GET /healthz/ready`, `GET /api/v1/readiness`, `GET /metrics`

### GraceKelly behaviour
- `Routing defaults`: `/healthz/live` always returns `{"status":"ok"}`; `/healthz/ready` checks repository/router/browser prerequisites; `/api/v1/readiness` returns the full readiness report; `/metrics` returns Prometheus text. Evidence: `src/gracekelly/api/routes/health.py:374`, `src/gracekelly/api/routes/health.py:379`, `src/gracekelly/api/routes/health.py:392`, `src/gracekelly/api/routes/health.py:415`.
- `Error surface`: readiness probe emits HTTP `503` when mandatory components are missing, while `/api/v1/readiness` keeps a `200` payload and logs non-ok states; `/metrics` has no local catch. Evidence: `src/gracekelly/api/routes/health.py:382`, `src/gracekelly/api/routes/health.py:403`.
- `Streaming`: none. Evidence: `src/gracekelly/api/routes/health.py:374`.
- `Sync vs async`: all routes are `async`; readiness and metrics offload expensive report building with `asyncio.to_thread`. Evidence: `src/gracekelly/api/routes/health.py:395`, `src/gracekelly/api/routes/health.py:418`.
- `Retry semantics`: none in the routes. Evidence: `src/gracekelly/api/routes/health.py:379`.
- `Idempotency`: read-only and idempotent except for live readiness/metric counters. Evidence: `src/gracekelly/api/routes/health.py:392`, `src/gracekelly/request_metrics.py:24`.
- `Auth / middleware`: `/healthz/live` and `/healthz/ready` are public; `/api/v1/readiness` and `/metrics` are protected when API key auth / Redis rate limiting are enabled. Evidence: `src/gracekelly/middleware.py:15`, `src/gracekelly/middleware.py:24`, `src/gracekelly/middleware.py:127`.
- `Observability hooks`: `/api/v1/readiness` emits warning logs on degraded state; `/metrics` exports request totals, adapter errors, latency histograms, and circuit-breaker gauges. Evidence: `src/gracekelly/api/routes/health.py:404`, `src/gracekelly/api/routes/health.py:269`, `src/gracekelly/request_metrics.py:29`.

### Note

N/A in the other project. Perplexity_Orchestrator2 has `/health` and `/health/db`, but no separate liveness probe, readiness probe, readiness JSON, or Prometheus endpoint in `01-inventory.md`.

### Severity hint

`medium` - these routes materially change deployment and monitoring integration even though they do not map to a direct O2 counterpart.

## GraceKelly-only model catalog surfaces

Covered endpoints: `GET /api/v1/models`, `POST /api/v1/models/refresh`

### GraceKelly behaviour
- `Routing defaults`: both endpoints read a stored `ModelCatalogSnapshot`; `/refresh` only appends `refreshed_at` and does not trigger a live upstream refresh itself. Evidence: `src/gracekelly/api/routes/models.py:118`, `src/gracekelly/api/routes/models.py:177`, `src/gracekelly/api/routes/models.py:202`.
- `Error surface`: missing snapshot becomes HTTP `503` with structured `model_catalog_unavailable` detail. Evidence: `src/gracekelly/api/routes/models.py:179`, `src/gracekelly/api/routes/models.py:205`.
- `Streaming`: none. Evidence: `src/gracekelly/api/routes/models.py:167`.
- `Sync vs async`: both handlers are `async`; snapshot access itself is synchronous. Evidence: `src/gracekelly/api/routes/models.py:177`, `src/gracekelly/api/routes/models.py:202`.
- `Retry semantics`: none at HTTP level; catalog refresh happens during app startup/lifespan logic. Evidence: `src/gracekelly/main.py:229`, `src/gracekelly/main.py:240`.
- `Idempotency`: `/models` is read-only; `/models/refresh` is effectively read-only apart from adding a response timestamp. Evidence: `src/gracekelly/api/routes/models.py:216`.
- `Auth / middleware`: protected when API key auth is enabled; request-id, metrics, security headers, and optional Redis rate limiting apply. Evidence: `src/gracekelly/middleware.py:24`, `src/gracekelly/middleware.py:60`, `src/gracekelly/middleware.py:97`, `src/gracekelly/middleware.py:108`.
- `Observability hooks`: the payload includes browser menu observation timestamps, verification timestamps, and availability status derived from stored/live observations. Evidence: `src/gracekelly/api/routes/models.py:14`, `src/gracekelly/api/routes/models.py:65`, `src/gracekelly/api/routes/models.py:130`.

### Note

N/A in the other project. Perplexity_Orchestrator2 inventories model ids and stats, but it does not expose a public model-catalog API with availability metadata.

### Severity hint

`medium` - this is an operator-facing catalog surface that does not exist in O2 and changes how clients discover model availability.

## GraceKelly-only orchestration extras

Covered endpoints: `POST /api/v1/orchestrate/upload`, `GET /api/v1/tasks/{task_id}/export`, `POST /api/v1/orchestrate/stream`

### GraceKelly behaviour
- `Routing defaults`: upload accepts multipart `prompt` plus optional `model/models/session_id/dry_run/files`; export renders one stored task to Markdown; stream requires at least one requested model and turns single-model execution into SSE. Evidence: `src/gracekelly/api/routes/orchestrate.py:399`, `src/gracekelly/api/routes/orchestrate.py:718`, `src/gracekelly/api/routes/stream.py:127`.
- `Error surface`: upload emits `422` for malformed `models`, unsupported files, and missing PDF support, `504` on timeout, `503` on storage/auth issues, and structured `500` on unknown failures; export emits `404/503`; stream keeps HTTP `200` and emits `error` SSE events for "no model", unknown model, storage issues, or adapter exceptions. Evidence: `src/gracekelly/api/routes/orchestrate.py:187`, `src/gracekelly/api/routes/orchestrate.py:210`, `src/gracekelly/api/routes/orchestrate.py:463`, `src/gracekelly/api/routes/orchestrate.py:536`, `src/gracekelly/api/routes/orchestrate.py:580`, `src/gracekelly/api/routes/stream.py:131`, `src/gracekelly/api/routes/stream.py:141`, `src/gracekelly/api/routes/stream.py:178`.
- `Streaming`: only `/api/v1/orchestrate/stream` streams; browser-backed models emit `accepted` then `complete`, and non-stream-capable adapters are downgraded to a one-shot `complete` event. Evidence: `src/gracekelly/api/routes/stream.py:149`, `src/gracekelly/api/routes/stream.py:185`, `src/gracekelly/api/routes/stream.py:226`, `src/gracekelly/api/routes/stream.py:266`.
- `Sync vs async`: upload and export offload blocking repository/orchestration work; stream offloads the producer and task persistence. Evidence: `src/gracekelly/api/routes/orchestrate.py:452`, `src/gracekelly/api/routes/orchestrate.py:734`, `src/gracekelly/api/routes/stream.py:105`, `src/gracekelly/api/routes/stream.py:214`, `src/gracekelly/api/routes/stream.py:272`.
- `Retry semantics`: none in the HTTP wrappers; stream/upload rely on underlying adapter/service behaviour rather than route retries. Evidence: `src/gracekelly/api/routes/orchestrate.py:451`, `src/gracekelly/api/routes/stream.py:185`.
- `Idempotency`: upload and stream are non-idempotent because they create new task ids and persist new results; export is read-only. Evidence: `src/gracekelly/api/routes/orchestrate.py:530`, `src/gracekelly/api/routes/stream.py:189`, `src/gracekelly/api/routes/stream.py:241`, `src/gracekelly/api/routes/orchestrate.py:739`.
- `Auth / middleware`: protected when API key auth is enabled; request-id, metrics, security headers, and optional Redis rate limiting apply. Evidence: `src/gracekelly/middleware.py:24`, `src/gracekelly/middleware.py:60`, `src/gracekelly/middleware.py:83`, `src/gracekelly/middleware.py:97`, `src/gracekelly/middleware.py:108`.
- `Observability hooks`: upload logs structured request/acceptance/failure events; stream persists completed outputs back into the task repository for later inspection. Evidence: `src/gracekelly/api/routes/orchestrate.py:433`, `src/gracekelly/api/routes/orchestrate.py:519`, `src/gracekelly/api/routes/stream.py:38`.

### Note

N/A in the other project. Orchestrator2 exposes websocket progress and a separate GK compatibility route, but no direct equivalents for multipart upload orchestration, markdown task export, or HTTP SSE streaming in `01-inventory.md`.

### Severity hint

`high` - these routes add whole transport and workflow modes (multipart, markdown export, SSE) that are absent from the reference implementation.

## GraceKelly-only stateless pattern endpoints

Covered endpoints: `POST /api/v1/batch`, `POST /api/v1/compare`, `POST /api/v1/consensus`, `POST /api/v1/debate`, `POST /api/v1/pipeline`, `POST /api/v1/smart`, `POST /api/v1/smart/v2`

### GraceKelly behaviour
- `Routing defaults`: the family is split by specialisation: `/smart` and `/smart/v2` default to `model="claude-sonnet-4-6"` with auto-resolved routing, `/pipeline` defaults to `quick/standard` style routing, `/consensus` defaults to `similarity_threshold=0.85`, `consensus_target=0.95`, `max_rounds=5`, `/compare` defaults to one model plus `analyze=true`, `/debate` can skip the initial model call when `initial_position` is supplied, and `/batch` caps prompts at 20. Evidence: `src/gracekelly/api/routes/smart.py:36`, `src/gracekelly/api/routes/smart_v2.py:36`, `src/gracekelly/api/routes/pipeline.py:32`, `src/gracekelly/api/routes/consensus.py:27`, `src/gracekelly/api/routes/compare.py:26`, `src/gracekelly/api/routes/debate.py:28`, `src/gracekelly/api/routes/batch.py:29`.
- `Error surface`: route-level validation errors are mostly `400/422/503`, but downstream model failures are frequently normalized into successful `200` payload fields such as `answer="[failure_code] ..."`, per-model `status="failed"/"error"`, or empty answers instead of propagating `5xx`. Evidence: `src/gracekelly/api/routes/smart.py:145`, `src/gracekelly/api/routes/smart_v2.py:163`, `src/gracekelly/api/routes/pipeline.py:129`, `src/gracekelly/api/routes/debate.py:109`, `src/gracekelly/api/routes/compare.py:118`, `src/gracekelly/api/routes/consensus.py:154`, `src/gracekelly/api/routes/batch.py:115`.
- `Streaming`: none in this family. Evidence: `src/gracekelly/api/routes/smart.py:59`, `src/gracekelly/api/routes/compare.py:49`, `src/gracekelly/api/routes/consensus.py:51`.
- `Sync vs async`: mixed execution style; most handlers are `async` and branch on `inspect.isawaitable`, while `/api/v1/consensus` is a synchronous `def` route that runs consensus work inline. Evidence: `src/gracekelly/api/routes/smart.py:73`, `src/gracekelly/api/routes/smart_v2.py:82`, `src/gracekelly/api/routes/pipeline.py:65`, `src/gracekelly/api/routes/debate.py:60`, `src/gracekelly/api/routes/batch.py:64`, `src/gracekelly/api/routes/compare.py:63`, `src/gracekelly/api/routes/consensus.py:67`.
- `Retry semantics`: there is no explicit route-level retry loop; any retry behaviour is delegated to adapters/executors hidden beneath `resolve_execution_adapter` or consensus executors. Evidence: `src/gracekelly/api/routes/_helpers.py:10`, `src/gracekelly/api/routes/consensus.py:143`.
- `Idempotency`: logically non-idempotent because outputs come from live LLM execution and no stable task ids are reused; these routes are stateless but not deterministic. Evidence: `src/gracekelly/api/routes/smart.py:131`, `src/gracekelly/api/routes/debate.py:95`, `src/gracekelly/api/routes/compare.py:105`.
- `Auth / middleware`: protected when API key auth is enabled; request-id, metrics, security headers, and optional Redis rate limiting apply to the whole family. Evidence: `src/gracekelly/middleware.py:24`, `src/gracekelly/middleware.py:60`, `src/gracekelly/middleware.py:83`, `src/gracekelly/middleware.py:97`, `src/gracekelly/middleware.py:108`.
- `Observability hooks`: logging is light and uneven (`logger.error` in batch/compare/consensus), while the global request-metrics middleware still records request counts and latencies. Evidence: `src/gracekelly/api/routes/batch.py:130`, `src/gracekelly/api/routes/compare.py:125`, `src/gracekelly/api/routes/consensus.py:161`, `src/gracekelly/request_metrics.py:24`.

### Note

N/A in the other project at pure HTTP-surface level. Later pattern docs (`04-06`) compare the underlying semantics, but the native Orchestrator2 public API does not expose this same set of synchronous stateless pattern routes, and its main `/orchestrate` route surfaces failures through task state rather than stuffed top-level `answer` fields. Evidence: `api/routes/orchestrate.py:217`, `api/routes/orchestrate.py:251`, `api/routes/orchestrate.py:464`.

### Severity hint

`high` - the family introduces multiple public routes whose HTTP success bodies can silently encode upstream execution failure, especially `/api/v1/smart`, which is a materially different failure contract from the reference orchestrator.

## Perplexity_Orchestrator2 accounts surfaces

Covered endpoints: `GET /accounts`, `GET /accounts/{account_id}`, `GET /accounts/needing-login`

### Orchestrator2 behaviour
- `Routing defaults`: the family uses a singleton `AccountPool`; list endpoints enumerate all accounts or only accounts without sessions, and the detail endpoint returns one account. Evidence: `api/routes/accounts.py:11`, `api/routes/accounts.py:15`, `api/routes/accounts.py:40`, `api/routes/accounts.py:89`.
- `Error surface`: unknown account ids do not raise `404`; the detail route returns `200 {"error": ...}` instead. Evidence: `api/routes/accounts.py:77`.
- `Streaming`: none. Evidence: `api/routes/accounts.py:40`.
- `Sync vs async`: `async def`, but all pool/session work is synchronous. Evidence: `api/routes/accounts.py:41`, `api/routes/accounts.py:48`.
- `Retry semantics`: none. Evidence: `api/routes/accounts.py:41`.
- `Idempotency`: read-only and idempotent except for live account/session state. Evidence: `api/routes/accounts.py:48`.
- `Auth / middleware`: open endpoint family under wildcard CORS; no auth/rate limiting. Evidence: `api/main.py:116`.
- `Observability hooks`: none in the handlers. Evidence: `api/routes/accounts.py:40`.

### Note

N/A in the other project. GraceKelly does not expose public account-pool management endpoints in `01-inventory.md`.

### Severity hint

`medium` - this is an O2-only operator surface, and its use of `200 {"error": ...}` on detail misses differs from GraceKelly's general preference for explicit HTTP error codes on storage-backed APIs.

## Perplexity_Orchestrator2 analytics detail surfaces

Covered endpoints: `GET /api/analytics/models`, `GET /api/analytics/accounts`, `GET /api/analytics/trends`

### Orchestrator2 behaviour
- `Routing defaults`: `/models` returns model performance, `/accounts` returns account health summary, and `/trends` defaults to `days=7`; all three open SQLite directly and use mock empty payloads when the DB cannot be opened. Evidence: `api/routes/analytics.py:106`, `api/routes/analytics.py:153`, `api/routes/analytics.py:207`, `api/routes/analytics.py:109`, `api/routes/analytics.py:157`, `api/routes/analytics.py:210`.
- `Error surface`: query/runtime errors are caught and replaced with `200` mock or empty payloads rather than `5xx` responses. Evidence: `api/routes/analytics.py:146`, `api/routes/analytics.py:200`, `api/routes/analytics.py:242`, `api/routes/analytics.py:265`, `api/routes/analytics.py:272`, `api/routes/analytics.py:280`.
- `Streaming`: none. Evidence: `api/routes/analytics.py:106`.
- `Sync vs async`: `async def`, but all sqlite work is synchronous on the event loop. Evidence: `api/routes/analytics.py:114`, `api/routes/analytics.py:161`, `api/routes/analytics.py:215`.
- `Retry semantics`: none. Evidence: `api/routes/analytics.py:109`.
- `Idempotency`: read-only and idempotent except for live DB contents. Evidence: `api/routes/analytics.py:115`.
- `Auth / middleware`: open under wildcard CORS; no auth/rate limiting. Evidence: `api/main.py:116`.
- `Observability hooks`: only `print("[Analytics] ...")` on exceptions. Evidence: `api/routes/analytics.py:149`, `api/routes/analytics.py:203`, `api/routes/analytics.py:245`.

### Note

N/A in the other project. GraceKelly exposes only one aggregate analytics endpoint and does not split model/account/trend views into separate public routes.

### Severity hint

`medium` - the whole family hides DB faults behind `200` payloads and materially diverges from GraceKelly's storage-failure handling style.

## Perplexity_Orchestrator2 conversation surfaces

Covered endpoints: `POST /api/conversation/create`, `GET /api/conversation/{conv_id}`, `GET /api/conversation/{conv_id}/messages`, `POST /api/conversation/{conv_id}/answer`

### Orchestrator2 behaviour
- `Routing defaults`: conversation creation accepts optional `task`; messages default to `limit=50` and `offset=0`; answer submission requires an existing pending question. Evidence: `api/routes/conversation.py:27`, `api/routes/conversation.py:55`, `api/routes/conversation.py:70`.
- `Error surface`: missing conversations are `404`; answering without a pending question is `400`; successful answers return a plain `{"status":"ok","answer":...}` body. Evidence: `api/routes/conversation.py:41`, `api/routes/conversation.py:59`, `api/routes/conversation.py:77`.
- `Streaming`: no HTTP streaming in these routes, but the same resource has a websocket side-channel for real-time updates. Evidence: `api/routes/conversation.py:84`.
- `Sync vs async`: `async def`, but all `conversation_manager` access is synchronous in-process state. Evidence: `api/routes/conversation.py:28`, `api/routes/conversation.py:38`.
- `Retry semantics`: none. Evidence: `api/routes/conversation.py:27`.
- `Idempotency`: `create` and `answer` are mutating/non-idempotent; `get` and `messages` are read-only. Evidence: `api/routes/conversation.py:27`, `api/routes/conversation.py:70`.
- `Auth / middleware`: open under wildcard CORS; no auth/rate limiting. Evidence: `api/main.py:116`.
- `Observability hooks`: none in the HTTP handlers. Evidence: `api/routes/conversation.py:27`.

### Note

N/A in the other project. GraceKelly has `session_id` chaining inside orchestration requests, but no standalone conversation-management HTTP surface in `01-inventory.md`.

### Severity hint

`low` - this is a genuinely O2-only feature surface rather than a conflicting implementation of an existing GraceKelly route.

## Perplexity_Orchestrator2 debate and English helper surfaces

Covered endpoints: `GET /api/debate/latest`, `GET /api/debate/health`, `POST /api/english/respond`, `POST /api/english/analyze`

### Orchestrator2 behaviour
- `Routing defaults`: debate endpoints read a JSON file from disk; English conversation defaults to `topic="casual"` and substitutes a canned greeting prompt when `message` is empty; English analysis rejects an empty response list. Evidence: `api/routes/debate.py:15`, `api/routes/debate.py:18`, `api/routes/english.py:26`, `api/routes/english.py:115`, `api/routes/english.py:145`.
- `Error surface`: `/api/debate/latest` raises `404/500`; `/api/debate/health` always returns `200` status payloads; English routes raise `400` for empty analysis input and `500` passthrough errors from direct Mistral HTTP calls. Evidence: `api/routes/debate.py:30`, `api/routes/debate.py:41`, `api/routes/debate.py:61`, `api/routes/english.py:137`, `api/routes/english.py:145`.
- `Streaming`: none. Evidence: `api/routes/debate.py:18`, `api/routes/english.py:115`.
- `Sync vs async`: debate routes are `async` wrappers over synchronous file I/O; English routes are true async and use `httpx.AsyncClient` directly against Mistral. Evidence: `api/routes/debate.py:36`, `api/routes/english.py:169`, `api/routes/english.py:199`.
- `Retry semantics`: none in the routes. Evidence: `api/routes/english.py:115`.
- `Idempotency`: debate GETs are read-only; English POSTs are non-idempotent live-model calls. Evidence: `api/routes/debate.py:18`, `api/routes/english.py:115`.
- `Auth / middleware`: open under wildcard CORS; no auth/rate limiting. Evidence: `api/main.py:116`.
- `Observability hooks`: English handlers log errors; debate handlers do not. Evidence: `api/routes/english.py:138`, `api/routes/english.py:160`.

### Note

N/A in the other project. GraceKelly exposes a debate execution route, but not this file-backed daily-debate feed or direct Mistral English tutor API family.

### Severity hint

`medium` - these routes are O2-only and bring their own error conventions (`404/500`, `200` health payloads, direct upstream `500` passthrough).

## Perplexity_Orchestrator2 GraceKelly compatibility surfaces

Covered endpoints: `POST /api/gk/orchestrate`, `GET /api/gk/patterns`

### Orchestrator2 behaviour
- `Routing defaults`: `pattern` defaults to `DUAL`, `thread_id/model/model_pair/files` are optional, `reasoning` defaults to `true`, and the route wraps execution with `GK_MAX_RETRIES=3` and `GK_TIMEOUT_SECONDS=1200`; `/patterns` returns a static list of available patterns. Evidence: `api/routes/gk_models.py:33`, `api/routes/gk_models.py:36`, `api/routes/gk_models.py:40`, `api/routes/gk_models.py:76`, `api/routes/gk_orchestrate.py:238`.
- `Error surface`: orchestration failures do not become HTTP `5xx`; the route returns `200` with `status="failed"`, empty `model_responses`, and a localized `consensus.text` error prefix; file-save failures are printed and ignored. Evidence: `api/routes/gk_orchestrate.py:100`, `api/routes/gk_orchestrate.py:207`, `api/routes/gk_orchestrate.py:228`.
- `Streaming`: none. Evidence: `api/routes/gk_orchestrate.py:72`.
- `Sync vs async`: `async def`, but browser/model work runs inline; helper patterns perform per-model retries and optional decomposition. Evidence: `api/routes/gk_orchestrate.py:86`, `api/routes/gk_patterns.py:60`, `api/routes/gk_patterns.py:86`, `api/routes/gk_decomposition.py:121`, `api/routes/gk_decomposition.py:252`.
- `Retry semantics`: worker calls retry with `max_retries=2`, and the outer `_execute_with_retries` wrapper retries the whole orchestration up to 3 times under one shared timeout. Evidence: `api/routes/gk_patterns.py:60`, `api/routes/gk_decomposition.py:252`.
- `Idempotency`: non-idempotent; each request allocates a fresh `task_id`, writes DB request logs, and may append to a thread. Evidence: `api/routes/gk_orchestrate.py:75`, `api/routes/gk_orchestrate.py:151`, `api/routes/gk_orchestrate.py:184`.
- `Auth / middleware`: open under wildcard CORS; no auth/rate limiting. Evidence: `api/main.py:116`.
- `Observability hooks`: mostly `print(...)` statements plus DB `log_request` and optional thread query persistence. Evidence: `api/routes/gk_orchestrate.py:78`, `api/routes/gk_orchestrate.py:149`, `api/routes/gk_orchestrate.py:171`.

### Note

N/A in the other project as a separate family. GraceKelly exposes native split routes instead of one compatibility endpoint plus a static pattern list.

### Severity hint

`medium` - this compatibility surface materially differs from native O2 `/orchestrate`, especially by stuffing orchestration failures into a `200` response body.

## Perplexity_Orchestrator2 stats summary surfaces

Covered endpoints: `GET /stats/models`, `GET /stats/requests`, `GET /stats/summary`

### Orchestrator2 behaviour
- `Routing defaults`: `/stats/requests` defaults to `limit=50`; the family mostly passes through to DB helper functions. Evidence: `api/routes/stats.py:10`, `api/routes/stats.py:29`, `api/routes/stats.py:43`.
- `Error surface`: there is no explicit exception handling, so helper/database errors would bubble as framework `500`s. Evidence: `api/routes/stats.py:5`, `api/routes/stats.py:26`, `api/routes/stats.py:40`, `api/routes/stats.py:54`.
- `Streaming`: none. Evidence: `api/routes/stats.py:10`.
- `Sync vs async`: `async def`, but all DB helper calls are synchronous. Evidence: `api/routes/stats.py:11`, `api/routes/stats.py:30`, `api/routes/stats.py:44`.
- `Retry semantics`: none. Evidence: `api/routes/stats.py:11`.
- `Idempotency`: read-only and idempotent except for live DB contents. Evidence: `api/routes/stats.py:26`.
- `Auth / middleware`: open under wildcard CORS; no auth/rate limiting. Evidence: `api/main.py:116`.
- `Observability hooks`: none in the handlers. Evidence: `api/routes/stats.py:10`.

### Note

N/A in the other project. GraceKelly folds similar information into `/api/v1/analytics`, `/api/v1/models`, `/metrics`, and readiness surfaces rather than a `/stats/*` family.

### Severity hint

`low` - this is an O2-specific reporting surface, not a divergent implementation of an existing GraceKelly route.

## Perplexity_Orchestrator2 interview trainer surfaces

Covered endpoints: `GET /api/interview/levels`, `POST /api/interview/start`, `GET /api/interview/status/{session_id}`, `GET /api/interview/question/{session_id}/{index}`, `POST /api/interview/evaluate`, `GET /api/interview/summary/{session_id}`

### Orchestrator2 behaviour
- `Routing defaults`: interview generation uses `BATCH_SIZE=10`, `DEFAULT_MODEL="Claude Sonnet 4.6"`, and clamps `count` into `1..50`; `/levels` is static; `/start` creates an in-memory session and schedules `_run_session` in the background. Evidence: `api/routes/interview.py:37`, `api/routes/interview.py:38`, `api/routes/interview.py:80`, `api/routes/interview.py:132`, `api/routes/interview.py:145`, `api/routes/interview.py:159`.
- `Error surface`: many misses are returned as `200 {"error": ...}` instead of `404`; empty topic returns `200 {"valid": false, ...}`; background generation retries one empty batch once and can end in `status="error"` or `status="invalid"` in session state. Evidence: `api/routes/interview.py:142`, `api/routes/interview.py:166`, `api/routes/interview.py:181`, `api/routes/interview.py:198`, `api/routes/interview.py:264`, `api/routes/interview.py:290`.
- `Streaming`: none. Evidence: `api/routes/interview.py:132`.
- `Sync vs async`: `async def`, but all state lives in an in-memory `sessions` dict; model calls go through `BrowserWorker.execute_with_retry(... max_retries=2)`. Evidence: `api/routes/interview.py:75`, `api/routes/interview.py:94`, `api/routes/interview.py:99`.
- `Retry semantics`: per-prompt worker retries use `max_retries=2`, and batch generation retries one empty batch one additional time. Evidence: `api/routes/interview.py:99`, `api/routes/interview.py:291`.
- `Idempotency`: `/start` and `/evaluate` are non-idempotent; `/status`, `/question`, `/summary`, and `/levels` are read-only. Evidence: `api/routes/interview.py:137`, `api/routes/interview.py:195`.
- `Auth / middleware`: open under wildcard CORS; no auth/rate limiting. Evidence: `api/main.py:116`.
- `Observability hooks`: logger errors exist for validation, generation, and evaluation failures; otherwise progress stays in session state only. Evidence: `api/routes/interview.py:259`, `api/routes/interview.py:317`, `api/routes/interview.py:410`, `api/routes/interview.py:462`.

### Note

N/A in the other project. GraceKelly has no public interview-trainer HTTP family in `01-inventory.md`.

### Severity hint

`medium` - the family is O2-only and relies heavily on `200 {"error": ...}` session-state contracts rather than explicit HTTP error codes.

## Perplexity_Orchestrator2 complex task API

Covered endpoints: `POST /api/tasks/complex`, `POST /api/tasks/{task_id}/execute`, `GET /api/tasks/{task_id}/result`, `GET /api/tasks/`, `DELETE /api/tasks/{task_id}`

### Orchestrator2 behaviour
- `Routing defaults`: complex-task creation defaults `auto_execute=false`; it spins up a browser session inline to decompose the task; execute starts background work; list returns all stored tasks. Evidence: `api/routes/tasks.py:18`, `api/routes/tasks.py:49`, `api/routes/tasks.py:85`, `api/routes/tasks.py:191`, `api/routes/tasks.py:311`.
- `Error surface`: creation returns `503` when no logged-in accounts exist and `500` with raw exception detail otherwise; execute/result/delete return `404` for missing tasks; delete mutates the filesystem directly. Evidence: `api/routes/tasks.py:76`, `api/routes/tasks.py:144`, `api/routes/tasks.py:200`, `api/routes/tasks.py:290`, `api/routes/tasks.py:327`, `api/routes/tasks.py:330`.
- `Streaming`: none. Evidence: `api/routes/tasks.py:49`.
- `Sync vs async`: `async def`, but creation does substantial browser startup and file/task-manager work inline; background execution is scheduled later. Evidence: `api/routes/tasks.py:85`, `api/routes/tasks.py:117`, `api/routes/tasks.py:148`.
- `Retry semantics`: no explicit HTTP retry loop in this family. Evidence: `api/routes/tasks.py:49`.
- `Idempotency`: create/execute/delete are non-idempotent; result/list are read-only. Evidence: `api/routes/tasks.py:49`, `api/routes/tasks.py:191`, `api/routes/tasks.py:320`.
- `Auth / middleware`: open under wildcard CORS; no auth/rate limiting. Evidence: `api/main.py:116`.
- `Observability hooks`: no structured logs; progress lives in task-manager state and response bodies. Evidence: `api/routes/tasks.py:217`, `api/routes/tasks.py:294`.

### Note

N/A in the other project as a direct family. GraceKelly has orchestration task lifecycle endpoints, but not this separate "complex task graph" HTTP surface.

### Severity hint

`medium` - the family is O2-only and combines inline browser orchestration, background execution, and raw exception-detail responses.

## Perplexity_Orchestrator2 thread surfaces

Covered endpoints: `GET /api/threads`, `POST /api/threads`, `GET /api/threads/{thread_id}`, `PATCH /api/threads/{thread_id}`, `DELETE /api/threads/{thread_id}`, `POST /api/threads/{thread_id}/queries`

### Orchestrator2 behaviour
- `Routing defaults`: thread creation defaults to a localized "new thread" title; adding the first query auto-renames the thread from the query text prefix. Evidence: `api/routes/threads.py:16`, `api/routes/threads.py:104`, `api/routes/threads.py:230`.
- `Error surface`: missing threads become `404` for get/update/delete/add-query; list/create are plain `200`. Evidence: `api/routes/threads.py:144`, `api/routes/threads.py:169`, `api/routes/threads.py:193`, `api/routes/threads.py:215`.
- `Streaming`: none. Evidence: `api/routes/threads.py:91`.
- `Sync vs async`: `async def`, but all database access is synchronous through `get_db()`. Evidence: `api/routes/threads.py:99`, `api/routes/threads.py:115`, `api/routes/threads.py:141`.
- `Retry semantics`: none. Evidence: `api/routes/threads.py:91`.
- `Idempotency`: list/get are read-only; create/patch/delete/add-query are mutating and non-idempotent in practice. Evidence: `api/routes/threads.py:104`, `api/routes/threads.py:154`, `api/routes/threads.py:179`, `api/routes/threads.py:200`.
- `Auth / middleware`: open under wildcard CORS; no auth/rate limiting. Evidence: `api/main.py:116`.
- `Observability hooks`: none in the handlers. Evidence: `api/routes/threads.py:91`.

### Note

N/A in the other project. GraceKelly supports `session_id` on orchestration requests, but it does not expose a standalone threads CRUD API in `01-inventory.md`.

### Severity hint

`low` - this is a feature gap rather than a conflicting behavioural implementation of an existing GraceKelly route.

## Perplexity_Orchestrator2 webpage builder surfaces

Covered endpoints: `GET /api/webpage/presets`, `POST /api/webpage/generate`, `GET /api/webpage/preview/{session_id}`, `GET /api/webpage/download/{session_id}`, `POST /api/webpage/ai-suggest`, `POST /api/webpage/ai-content`, `POST /api/webpage/ai-chart`

### Orchestrator2 behaviour
- `Routing defaults`: pure generator endpoints read/write `data/webpages`; AI endpoints default audience/page type/language fields and use BrowserWorker-backed Claude suggestions. Evidence: `api/routes/webpage.py:35`, `api/routes/webpage.py:45`, `api/routes/webpage.py:49`, `api/routes/webpage.py:57`, `api/routes/webpage.py:66`, `api/routes/webpage.py:114`, `api/routes/webpage.py:166`, `api/routes/webpage.py:204`, `api/routes/webpage.py:240`.
- `Error surface`: generation and AI endpoints return `200 {"success": false, "error": ...}` on failures; preview returns `404` HTML; download returns `200 {"error":"File not found"}`. Evidence: `api/routes/webpage.py:138`, `api/routes/webpage.py:147`, `api/routes/webpage.py:157`, `api/routes/webpage.py:197`, `api/routes/webpage.py:233`, `api/routes/webpage.py:269`.
- `Streaming`: none. Evidence: `api/routes/webpage.py:108`.
- `Sync vs async`: `async def`, but generate/preview/download do synchronous filesystem I/O; AI endpoints call BrowserWorker `execute_with_retry(... max_retries=2)`. Evidence: `api/routes/webpage.py:123`, `api/routes/webpage.py:149`, `api/routes/webpage.py:159`, `api/routes/webpage.py:75`, `api/routes/webpage.py:79`.
- `Retry semantics`: AI calls retry at the worker layer with `max_retries=2`; file-only routes have no retry logic. Evidence: `api/routes/webpage.py:79`.
- `Idempotency`: `generate` is non-idempotent because it allocates a new `session_id` and file; preview/download are read-only; AI routes are non-idempotent live-model calls. Evidence: `api/routes/webpage.py:119`, `api/routes/webpage.py:143`, `api/routes/webpage.py:153`.
- `Auth / middleware`: open under wildcard CORS; no auth/rate limiting. Evidence: `api/main.py:116`.
- `Observability hooks`: only logger errors on generation/AI failures. Evidence: `api/routes/webpage.py:139`, `api/routes/webpage.py:200`, `api/routes/webpage.py:236`, `api/routes/webpage.py:272`.

### Note

N/A in the other project. GraceKelly does not expose a webpage-builder HTTP family in `01-inventory.md`.

### Severity hint

`medium` - the family is O2-only and uses mixed `404`, `200 error body`, and `200 success=false` conventions that differ from GraceKelly's task-oriented APIs.
