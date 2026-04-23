# Post-Phase-2 Audit

Date: 2026-04-23
Scope: read-only audit of `src/`, `tests/`, docs, tooling, and workflow history at HEAD `7e50fb7`

## Executive Summary

Health score: 7.6/10. The codebase is operationally healthy: baseline gates are green (`pytest -q`: `2647 passed, 6 skipped`; `ruff`: clean; `mypy --strict`: clean; total coverage: `97%`), import layering remains disciplined, and the security scan found no known CVEs or high-signal dangerous API usage. The main debt is not broad instability but three targeted blind spots accumulated during the late-phase push: runtime configuration is split between explicit app factories and hidden module globals, the browser hot path is partially invisible to the baseline coverage signal, and the roadmap/API docs have drifted behind the actual post-Phase-2 state. This project is not in "significant accumulated debt", but it is also not yet "ready for long-term maintenance" without one short hardening pass around config propagation, browser-path test visibility, and docs sync.

Top-3 prioritized findings:
- `P1: ExecutionRouter ignores create_app(Settings(...)) budget/fallback overrides because it reads module-global config state instead of injected app settings.`
- `P1: Baseline coverage excludes playwright_driver.py, and targeted coverage shows _find_option_in_menu_scope at only 71.4% line coverage.`
- `P1: docs/phased-roadmap.md still says Phase 2/4 are partial, references obsolete GRACEKELLY_RATE_LIMIT_PER_MINUTE, and claims CORS support with no code match.`

Verdict: needs targeted hardening.

## Baseline metrics snapshot

| Metric | Value |
| --- | --- |
| Source files | 106 |
| Source LOC | 15,330 |
| Test files | 157 |
| Test LOC | 35,500 |
| Coverage total | 97% |
| `mypy --strict` | pass, 0 errors, 1 config note (`pyproject.toml` unused override section) |
| `ruff check src tests` | 0 violations |
| `pytest -q` | `2647 passed, 6 skipped, 11 subtests passed in 658.77s` |
| `pytest -q --durations=20` | `2647 passed, 6 skipped, 11 subtests passed in 777.23s` |

Top-5 least-covered modules from the baseline coverage report:

| Module | Coverage | Notes |
| --- | --- | --- |
| `src/gracekelly/core/__init__.py` | 45% | lazy re-export glue, low risk but under-tested |
| `src/gracekelly/tools/backup_profile.py` | 76% | operational tool, not in main runtime path |
| `src/gracekelly/tools/capture_perplexity_recon.py` | 85% | just above the <85 threshold |
| `src/gracekelly/core/session_context.py` | 86% | hot enough to watch because prompt shaping happens here |
| `src/gracekelly/storage/postgres.py` | 89% | acceptable, but still the least-covered durable backend module |

Top-5 longest tests from `pytest --durations=20`:

| Test | Duration |
| --- | --- |
| `tests/test_http_api.py::HttpApiSmokeTests::test_metrics_exposes_open_browser_circuit_breaker` | 13.80s |
| `tests/test_http_api.py::HttpApiSmokeTests::test_readiness_exposes_browser_circuit_breaker_details` | 13.06s |
| `tests/test_ui_auth_banner.py::test_sync_auth_banner_shows_server_message_and_trace_id` | 13.01s |
| `tests/test_http_api.py::HttpApiSmokeTests::test_readiness_logs_when_overall_status_is_degraded` | 12.98s |
| `tests/test_playwright_driver.py::PlaywrightDriverTests::test_auth_status_emits_diagnostic_log_when_logged_out` | 10.00s |

## Architecture findings

1. `P1` Runtime config propagation is inconsistent across the core and already reproduces as a real settings bug.
   - `create_app()` accepts explicit `Settings` and stores them on `app.state.settings` at [src/gracekelly/main.py:314] and [src/gracekelly/main.py:400-408], but `ExecutionRouter` still reads budget and fallback settings from module-global `_default_settings` imported from [src/gracekelly/core/router.py:7].
   - The router constructs its default budget tracker from `_default_settings.max_browser_submits_per_task` / `_default_settings.max_browser_submits_per_hour` at [src/gracekelly/core/router.py:45-47] and gates fallback through `_default_settings.enable_model_fallback` at [src/gracekelly/core/router.py:331-346].
   - Concrete repro from this audit: `create_app(Settings(... max_browser_submits_per_task=2, max_browser_submits_per_hour=5, enable_model_fallback=True))` produced `app.state.settings.enable_model_fallback == True` but `app.state.execution_router.healthcheck()["budget"] == {'per_task_limit': None, 'per_hour_limit': None, ...}`.
   - This is more than style drift: config behavior depends on hidden import-time state, while tests compensate by patching `gracekelly.core.router._default_settings` directly in [tests/test_request_budget.py:349-378] and [tests/test_router_fallback.py:135-499].

2. `P2` DI patterns are mixed enough to create hidden-state coupling.
   - Factory-style injection exists in `create_app()` and `build_browser_adapter()` at [src/gracekelly/main.py:133-210].
   - The orchestrator uses explicit injection with a silent default object fallback at [src/gracekelly/core/orchestrator.py:57].
   - The router uses a module-global singleton (`config.settings`) at [src/gracekelly/core/router.py:7].
   - The model catalog uses mutable module-global state at [src/gracekelly/core/models.py:198-207].
   - These styles are individually reasonable, but mixing them for the same configuration/catalog responsibilities is the reason the settings bug above exists.

3. Layering is still intact.
   - AST import scan found no `api -> adapters` direct imports.
   - AST import scan found no `adapters -> api` direct imports.
   - AST import scan also found no `core -> adapters` imports.
   - No circular-import symptoms surfaced in `ruff` or `mypy`.

4. `P2` Size and cyclomatic proxies show a few clear outliers.
   - Files over 600 LOC:
     - [src/gracekelly/adapters/browser/playwright_driver.py:1] -> 1,118 LOC
     - [src/gracekelly/api/routes/orchestrate.py:1] -> 847 LOC
     - [src/gracekelly/storage/postgres.py:1] -> 806 LOC
   - Functions over 100 LOC:
     - [src/gracekelly/api/routes/health.py:110] `_build_metrics_payload` -> 204 LOC
     - [src/gracekelly/api/routes/orchestrate.py:399] `orchestrate_with_files` -> 192 LOC
     - [src/gracekelly/api/routes/smart_v2.py:82] `run_smart_v2` -> 159 LOC
     - [src/gracekelly/api/routes/stream.py:128] `orchestrate_stream` -> 157 LOC
     - [src/gracekelly/adapters/api/base.py:197] `BaseApiAdapter.execute_async` -> 154 LOC
     - [src/gracekelly/adapters/browser/playwright_driver.py:234] `PlaywrightBrowserAutomation.select_model` -> 153 LOC
     - [src/gracekelly/core/consensus_v2.py:109] `ConsensusExecutorV2.execute` -> 148 LOC
     - [src/gracekelly/adapters/browser/perplexity.py:68] `PerplexityBrowserAdapter.execute` -> 147 LOC
     - [src/gracekelly/main.py:314] `create_app` -> 147 LOC
   - Not every large function is wrong, but the concentration is high enough to justify a future decomposition pass.

5. Circular imports: no findings.
   - `ruff` clean, `mypy --strict` clean, and the import-boundary scan showed no suspicious reverse links.

## Security findings

1. No known dependency vulnerabilities were reported.
   - `pip-audit 2.10.0 --path .venv/Lib/site-packages` returned `No known vulnerabilities found`.
   - The tool skipped the local project package (`gracekelly 0.1.0`) because it is not on PyPI; this is expected.

2. No high-signal dangerous API usage was found in `src/`.
   - Grep for `os.system|subprocess.call|eval(|pickle.loads|yaml.load(` returned no matches.

3. Secrets handling looks clean.
   - Grep for `password|api_key|secret` outside `config.py` only surfaced key-plumbing, adapter auth headers, and health/doc strings.
   - No hard-coded secret values were found in `src/`.

4. Path traversal checks look adequate for the current local-deploy model.
   - Upload handling only inspects the uploaded filename suffix via [src/gracekelly/api/routes/orchestrate.py:193-206]; it does not open a filesystem path derived from the user filename.
   - Browser profile dirs are explicitly validated against `..` and `~` at [src/gracekelly/adapters/browser/session.py:9-18].
   - Screenshot output paths are built from config-controlled `screenshots_dir` plus a sanitized step slug at [src/gracekelly/adapters/browser/playwright_driver.py:560-575].

5. Auth/rate-limiting defaults are development-safe, not internet-safe.
   - API auth is opt-in; when `GRACEKELLY_API_KEY` is unset, middleware logs that all endpoints are open at [src/gracekelly/middleware.py:23-25].
   - Rate limiting is also opt-in because `setup_rate_limiting()` no-ops without Redis at [src/gracekelly/middleware.py:108-114].
   - This is acceptable for the explicitly single-user local deployment model, but public deployment still requires explicit hardening.

Security verdict: no active security findings requiring immediate code changes.

## Dependency health

1. Runtime dependency drift is low.
   - Direct runtime dependencies from `pyproject.toml` are `fastapi`, `uvicorn[standard]`, `httpx`, `python-multipart`, and `python-dotenv`.
   - Outdated direct runtime deps:
     - `fastapi 0.135.3 -> 0.136.0`
     - `uvicorn 0.44.0 -> 0.46.0`
   - No direct runtime package shows a major-version drift.

2. Dev tooling drift is moderate but non-urgent.
   - `pytest-cov 5.0.0 -> 7.1.0` is the only visible major-version drift in the venv package list, and it is dev-only.
   - `mypy 1.20.0 -> 1.20.2`, `ruff 0.15.10 -> 0.15.11`, `hypothesis 6.151.12 -> 6.152.1` are minor.

3. No obvious unused main dependency was found.
   - `python-dotenv` is used in [src/gracekelly/config.py:7-12].
   - `python-multipart` is not imported by name, but it is required by FastAPI `UploadFile` / `File(...)` handling in [src/gracekelly/api/routes/orchestrate.py:13] and [src/gracekelly/api/routes/orchestrate.py:407].
   - Optional packages are imported lazily where needed:
     - `pypdf` only in [src/gracekelly/api/routes/orchestrate.py:208-215]
     - `playwright` in the browser adapter and browser tools
     - `redis`, `sentry-sdk`, `opentelemetry*`, `psycopg`, `psycopg_pool` behind feature gates

4. Heavy-dependency assessment:
   - `playwright` is the heaviest dependency and is used deeply enough to justify itself (`src/gracekelly/adapters/browser/playwright_driver.py`, `src/gracekelly/tools/create_perplexity_profile.py`, `src/gracekelly/tools/capture_perplexity_recon.py`).
   - `pypdf` is comparatively heavy for a single route helper, but it remains optional and isolated to the upload path, which is acceptable.
   - No dependency-health finding rises above `P3` today.

## Test robustness

1. `P1` The baseline coverage signal hides a live browser hot path.
   - `pyproject.toml` omits `src/gracekelly/adapters/browser/playwright_driver.py` from coverage at [pyproject.toml:85-88].
   - A targeted coverage run over `tests/test_playwright_driver.py` shows the file at only `65%`.
   - More importantly, the specific helper introduced to harden the batch-87/88 model-menu fix, `_find_option_in_menu_scope()` at [src/gracekelly/adapters/browser/playwright_driver.py:708-714], is only `5/7` statement lines covered (`71.4%`) in the direct driver suite; the exception/continue path (`712-713`) is unhit.
   - This means the headline `97%` baseline does not reflect one of the most failure-prone modules in the repo.

2. Coverage gaps under 85% are limited and mostly low-risk.
   - [src/gracekelly/core/__init__.py:1] -> 45%
   - [src/gracekelly/tools/backup_profile.py:1] -> 76%
   - No 0%-covered modules were present in the baseline report.

3. Known flake history is narrow and well-instrumented.
   - `.workflow/outbox/2026-04-21-batch-74-FLAKY-postgres-test-triage-report.md` recorded `tests/test_import_postgres_tool.py::ImportPostgresToolTests::test_main_rejects_checksum_mismatch` as a full-suite-only flake.
   - `.workflow/outbox/2026-04-21-batch-75-FLAKY-postgres-fix-report.md` later reported no repro on the current line.
   - `.workflow/outbox/2026-04-22-batch-80-FLAKE-triage-http-api-report.md` recorded and fixed a timing-dependent flake in `tests/test_http_api.py::HttpApiSmokeTests::test_list_tasks_exposes_winning_model_and_short_circuit_summary`.
   - No evidence of a broad flake wave after those two items.

4. Duration outliers are concentrated in integration-like route tests, not a random scatter.
   - The longest tests are mostly `HttpApiSmokeTests` plus one UI auth banner test and one Playwright-driver diagnostic test.
   - Given the current single-process app factory and browser health machinery, 10-14s is not shocking, but these tests are still slow enough to tax iteration speed and should be kept under review.

5. Mutation-test coverage is still ad hoc.
   - There is no systemic mutation job in the repo.
   - Recommendation: run `mutmut` or `cosmic-ray` selectively on `gracekelly.core.router`, `gracekelly.api.routes.orchestrate`, and the Playwright driver helpers after the next hardening pass.

6. Test parity for the three explicitly requested hotspots:
   - `core/budget.py`: yes, baseline coverage is `100%`.
   - `core/router.py._try_fallback`: effectively yes. From the full-suite coverage report the only missed line in `router.py` was [src/gracekelly/core/router.py:346], so `_try_fallback()` is above 95% line coverage; this is an inference from the full coverage output.
   - `adapters/browser/playwright_driver.py._find_option_in_menu_scope`: no. Targeted direct-suite coverage measured `71.4%` line coverage.

## Code quality

1. `P2` Tooling config has a stale mypy override block.
   - `mypy --strict` reports `pyproject.toml: note: unused section(s): module = ['test_app_startup', 'test_orchestrate_timeout', 'test_postgres_live']`.
   - The stale override is at [pyproject.toml:106-112].
   - This is not breaking correctness, but it is evidence of config drift after the repo standardized on `mypy src --strict`.

2. No bare `except:` blocks were found.
   - Grep for `except:` / `except: pass` in `src/` returned no matches.

3. `P2` Fallback observability is weaker than adjacent failure paths.
   - Recent route and browser code emits structured or semi-structured logs in most failure branches, for example [src/gracekelly/api/routes/orchestrate.py:258-375] and [src/gracekelly/adapters/browser/playwright_driver.py:257-422].
   - The fallback path itself in [src/gracekelly/core/router.py:325-365] does not log when fallback is attempted, skipped, or succeeds/fails.
   - Operators can reconstruct fallback from result details after the fact, but live debugging still lacks a single log event for this transition.

4. `P2` Public docstring coverage in `core/` is extremely low.
   - The audit found only one public docstring anywhere in `src/`: [src/gracekelly/telemetry.py:12] `setup_telemetry`.
   - Missing public docstrings in `core/` include at least:
     - [src/gracekelly/core/account_loader.py:9] `AccountCredential`
     - [src/gracekelly/core/account_loader.py:15] `load_accounts`
     - [src/gracekelly/core/account_loader.py:37] `load_accounts_from_env`
     - [src/gracekelly/core/account_pool.py:13] `Account`
     - [src/gracekelly/core/account_pool.py:26] `AccountPoolConfig`
     - [src/gracekelly/core/account_pool.py:30] `AccountPool`
     - [src/gracekelly/core/account_pool_manager.py:10] `PooledExecutionResult`
     - [src/gracekelly/core/account_pool_manager.py:16] `AccountPoolManager`
     - [src/gracekelly/core/adaptive_params.py:9] `AdaptiveConsensusParams`
     - [src/gracekelly/core/adaptive_params.py:29] `get_adaptive_params`
   - Total missing public core docstrings found by the AST pass: 162.

5. `P3` Likely dead-code candidates exist, but they are low-risk.
   - [src/gracekelly/core/models.py:207] `get_browser_catalog()` has no call sites in `src/` or `tests/`.
   - [src/gracekelly/core/readiness.py:16] `ComponentStatus` likewise has no call sites.
   - These do not justify a dedicated batch unless nearby files are already being touched.

6. Type-hint posture is mostly acceptable, but `Any` is concentrated at adapter/framework boundaries.
   - The main clusters are `app_state`, `api/routes/health.py`, `storage/postgres.py`, and especially `adapters/browser/playwright_driver.py`.
   - For the browser adapter this is somewhat legitimate because Playwright sync objects are dynamically typed, but it does reduce refactor confidence in the hottest module.

## Docs sync

1. `P1` `docs/phased-roadmap.md` is materially out of sync with the post-Phase-2 state.
   - Phase 2 still says `Status: partial, first authenticated live-driver smoke proven` at [docs/phased-roadmap.md:37-39], while the batch context for this audit states Phase 2 is closed.
   - Phase 4 still says `Status: partial` at [docs/phased-roadmap.md:91-93], even though the batch context states Phase 4 is closed except for deferred/non-audit items.
   - The roadmap still documents `GRACEKELLY_RATE_LIMIT_PER_MINUTE` at [docs/phased-roadmap.md:112], but the code uses `GRACEKELLY_RATE_LIMIT_RPM` at [src/gracekelly/config.py:202].
   - The roadmap claims `CORS support (configurable origins, credentials, CORS middleware)` at [docs/phased-roadmap.md:203], but repo-wide grep found no `CORSMiddleware`, `allow_origins`, or equivalent implementation in `src/`.

2. `P2` README API inventory is incomplete relative to the live route surface.
   - The API table at [README.md:81-96] lists the primary endpoints but omits at least:
     - `GET /api/v1/analytics` at [src/gracekelly/api/routes/analytics.py:31]
     - `POST /api/v1/orchestrate/upload` at [src/gracekelly/api/routes/orchestrate.py:393]
     - `POST /api/v1/tasks/{task_id}/retry` at [src/gracekelly/api/routes/orchestrate.py:742]
     - `POST /api/v1/models/refresh` at [src/gracekelly/api/routes/models.py:193]
   - If README is intended as product-level orientation, this is acceptable. If it is intended as endpoint inventory, it is stale.

3. `P2` `docs/architecture.md` documents only part of the current module surface.
   - It still accurately mentions `adapters.browser.scripted` at [docs/architecture.md:19] and [docs/architecture.md:53].
   - It does not mention several meaningful post-Phase-2 modules or surfaces, including `core.budget`, `api.routes.analytics`, `api.routes.health_detailed`, `core.session_context`, `request_metrics`, and `telemetry`.
   - No references to deleted/non-existent modules were found; the drift is under-documentation, not stale references.

4. `docs/operator-runbook.md` is largely synced.
   - Auth behavior for `GRACEKELLY_API_KEY` matches code at [docs/operator-runbook.md:25-31] and [src/gracekelly/middleware.py:23-41].
   - The live-smoke quota expectations still match the Phase 17 evidence in the roadmap.
   - The upload endpoint is documented in the harness table at [docs/operator-runbook.md:318].
   - No action needed here beyond keeping it aligned after the roadmap cleanup.

5. Docstrings vs signature spot-check:
   - Effectively blocked by docstring scarcity. Only one public docstring exists in `src/`, and its signature/docstring pair in [src/gracekelly/telemetry.py:12-36] is consistent.

## Recommendations

1. `P1`, size `S`, scope `src/gracekelly/core/router.py`, `src/gracekelly/main.py`, tests: inject settings into `ExecutionRouter` explicitly and remove `_default_settings` reads for budget/fallback, because `create_app(Settings(...))` currently does not control those behaviors.
2. `P1`, size `S`, scope `pyproject.toml`, `tests/test_playwright_driver.py`, possibly CI config: stop hiding `playwright_driver.py` from the default coverage signal or add a dedicated coverage job for it, and add the missing exception-path test for `_find_option_in_menu_scope`.
3. `P1`, size `XS`, scope `docs/phased-roadmap.md`: update Phase 2/4 statuses, rename the rate-limit env var to `GRACEKELLY_RATE_LIMIT_RPM`, and either remove or implement the documented CORS support claim.
4. `P2`, size `S`, scope `README.md`, `docs/architecture.md`: decide whether README is a full API inventory or a product-level summary, then align endpoint/module docs to that chosen level.
5. `P2`, size `XS`, scope `pyproject.toml`, `src/gracekelly/core/router.py`: delete the stale mypy override block and add one structured fallback log event covering attempt/result/reason.
6. `P2`, size `M`, scope `src/gracekelly/adapters/browser/playwright_driver.py`, `src/gracekelly/api/routes/orchestrate.py`, `src/gracekelly/storage/postgres.py`: plan a future decomposition batch for the largest files/functions once the P1 items are closed.
7. `P3`, size `XS`, scope `src/gracekelly/core/models.py`, `src/gracekelly/core/readiness.py`, selected `core/*`: prune clearly unused public symbols only when adjacent code is already being touched; separately, add docstrings only to hot-path/public modules where operator or contributor confusion is real.

Explicitly not to fix now:

1. `P3` `core.__init__.py` low coverage. ROI is poor because it is lazy export glue and not a runtime risk.
2. `P3` `tools/backup_profile.py` at 76% coverage. It is an operational helper outside the main request path.
3. `P3` broad dependency bumping. Direct runtime drift is minor and there is no security pressure today.
4. `P3` CORS implementation itself, unless product goals now require cross-origin clients. The urgent issue is the roadmap claim, not the absence of the feature in a same-origin local app.

Manual-only live validation, if any follow-up needs it:

1. After browser coverage/fallback hardening, any real Perplexity validation should remain manual and quota-gated.
2. No scheduled live validation is recommended from this audit.

## Methodology footnote

Tools used:
- `git status --short`
- `.venv/Scripts/pytest.exe -q`
- `.venv/Scripts/pytest.exe -q --durations=20`
- `.venv/Scripts/python.exe -m ruff check src tests`
- `.venv/Scripts/python.exe -m mypy src --strict`
- `.venv/Scripts/python.exe -m coverage report --show-missing --sort=cover`
- targeted coverage probes via `coverage 7.13.5` API against `tests/test_playwright_driver.py`
- `uv pip list --python .venv/Scripts/python.exe --outdated`
- `pip-audit 2.10.0 --path .venv/Lib/site-packages`
- `rg` grep scans and short AST scripts under project Python 3.13.7

Version snapshot:
- Python `3.13.7`
- `pytest 9.0.3`
- `ruff 0.15.10`
- `mypy 1.20.0`
- `coverage.py 7.13.5`
- `pip-audit 2.10.0`
- `uv 0.8.23`

Not covered in this audit:
- load/performance profiling
- multi-user or distributed deployment behavior
- scheduled/live browser submits
- full dependency graph reduction analysis
- formal cyclomatic-complexity tooling (size was approximated via LOC/AST length)
