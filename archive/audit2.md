# GraceKelly Gate 4 — Independent Boundary Review

**Date:** 2026-03-17
**Reviewer:** Claude Opus 4.6 (1M context), acting as independent reviewer
**Audit brief:** `gate4-audit-brief.md`
**Working tree:** clean
**Tests:** 68 passed, 3 skipped (0.76s)
**Scope:** adapter boundary for live browser execution

---

## Methodology

Every file listed in the audit brief's suggested entry points was read in full. In addition, all files under `core/`, `adapters/`, `storage/`, `api/routes/`, and `main.py` were reviewed. Import graphs were verified via automated grep. Thread-safety mechanisms were traced through `asyncio.to_thread`, `RLock`, and `Lock`. The full implementation plan (including confirmed decisions, issue log, and action items) was reviewed for consistency with the code.

---

## Answers to audit questions

### Q1. Can a live browser driver be added behind the current adapter boundary without introducing browser-aware branches into `core/`?

**Verdict: Yes.**

Evidence:

1. **Import graph is clean.** `grep` for `from.*adapters` and `from.*browser` across `src/gracekelly/core/` and `src/gracekelly/api/` returns zero matches. The only file that imports from `adapters/browser/` is `main.py` — the composition root. This is correct.

2. **`core/router.py` dispatches by `step.backend.value`**, not by adapter type. The router checks `"api"` vs else; it does not name Perplexity, Playwright, or any browser technology. A live driver changes nothing in this dispatch.

3. **`core/orchestrator.py` has no awareness of adapter internals.** It receives an `ExecutionBatchResult` and builds storage records and events. The browser adapter could return results from Playwright, Selenium, or a headless Chrome CDP connection — the orchestrator would not notice.

4. **`core/planning.py` routes models by `ModelSpec.adapter_kind`** (`"browser"` or `"api"`), which is registry data, not adapter coupling. Adding a new browser-capable model requires only a new `ModelSpec` entry.

5. **`core/models.py`** has `adapter_kind` as a plain string. No imports from browser packages.

**No browser-aware branches need to enter `core/` for a live driver.**

---

### Q2. Is `ExecutionRequest` expressive enough for real browser execution, or is one more abstraction needed?

**Verdict: Sufficient. No additional abstraction needed before the first live driver.**

`ExecutionRequest` (`contracts.py:98-110`) provides:

| Field | Browser relevance |
|---|---|
| `task_id` | Correlation for logging/debugging |
| `prompt` | The text to submit in the browser UI |
| `plan` | Full execution context (quorum, merge, dry_run) |
| `step` | Model spec with `provider_model_id`, `timeout_seconds`, `backend`, `provider` |
| `reasoning` | Whether to enable reasoning mode in the UI |
| `metadata` | Pass-through for trace data |
| `cancellation` | Cooperative cancellation token |

What a live browser driver additionally needs:
- **Browser profile directory** → already in `BrowserSessionManager` (injected dependency)
- **Base URL** → already in `BrowserSessionConfig`
- **Page interaction policies** → already in `PopupPolicy`, `AuthRecoveryPolicy`, `ModelVerificationPolicy`, `SubmitPolicy` (injected dependencies)
- **Timeout** → in `step.model.timeout_seconds`

All browser-specific context lives in the adapter's injected dependencies, not in the request. This is the right design: `ExecutionRequest` carries the *what* (prompt, model, timeout), while the adapter owns the *how* (browser launch, DOM interaction, selectors).

**One observation:** If a future increment needs to pass per-request browser hints (e.g., "use a specific cookie jar for this request"), `metadata` is the escape hatch. For the first live spike, this is not needed.

---

### Q3. Should browser session state, auth recovery, popup handling, and DOM/model verification remain entirely inside `adapters/browser/`, or is any of that pressure already leaking into shared layers?

**Verdict: No leaking detected. Everything is correctly contained.**

Detailed trace:

| Concern | Location | Leaking? |
|---|---|---|
| Session state | `adapters/browser/session.py` (`BrowserSessionManager`, `BrowserSessionState`) | No — only accessed by `PerplexityBrowserAdapter` |
| Auth recovery | `adapters/browser/policy.py` (`AuthRecoveryPolicy`), `automation.py` (`auth_status`, `recover_auth`) | No — called only from `PerplexityBrowserAdapter._ensure_auth()` |
| Popup dismissal | `adapters/browser/policy.py` (`PopupPolicy`), `automation.py` (`dismiss_popups`) | No — called only from `PerplexityBrowserAdapter.execute()` |
| Model verification | `adapters/browser/policy.py` (`ModelVerificationPolicy`), `automation.py` (`select_model`), `perplexity.py` (`_model_matches_expected`) | No — `_model_matches_expected` calls `models_equivalent()` from `core/models.py`, but this is a read-only query, not a coupling |
| DOM interaction | `adapters/browser/automation.py` (`BrowserAutomationPort` ABC) | No — the ABC is defined inside `adapters/browser/`, not in `core/` |

The one cross-boundary call is `PerplexityBrowserAdapter._model_matches_expected` → `core.models.models_equivalent()`. This is a legitimate dependency direction (adapter reads from core registry). It does not leak browser concerns upward.

**`core/models.py` does strip `" thinking"` and `" with reasoning"` suffixes during normalization** (`models.py:29-30`). This is a model-naming concern, not a browser concern — it would apply equally to API models that append reasoning suffixes. Not a leak.

**Composition root (`main.py`)** imports from `adapters/browser/` to wire dependencies. This is expected for a composition root. The wiring is flat (no conditional browser logic inside route handlers or middleware).

---

### Q4. Are the current task, step, and event contracts sufficient for operator forensics once a live browser is involved?

**Verdict: Sufficient for the first live increment. No schema widening needed.**

Forensic data flow for a browser execution:

1. **`gk_task_steps`** stores: `model_id`, `model_display_name`, `backend` ("browser"), `provider` ("perplexity"), `status`, `failure_code`, `failure_message`, `output_text`, `duration_ms`. This covers *what happened* and *how long it took*.

2. **`step.completed` / `step.failed` event payloads** carry `details` dict from `ExecutionResult.details`. The current `PerplexityBrowserAdapter` already populates this with:
   - `provider`, `requested_model_label`, `actual_model_label` (from model selection)
   - `driver` (from automation backend)
   - `submitted_prompt`, `timeout_seconds` (from submit)
   - `configured`, `active` (from session state on failure)

   A live Playwright driver would add: page URL, selector timing, screenshot path, DOM state hash — all as `details` entries, without widening the step table.

3. **`task.completed` / `task.failed` / `task.cancelled` event payloads** carry aggregate `details` from `ExecutionBatchResult.details`: quorum, merge strategy, adapter names, failure codes, winning step, cancelled steps. This is already browser-agnostic.

4. **`FailureCode` enum** covers browser scenarios: `AUTH_FAILED`, `MODEL_MISMATCH`, `PROVIDER_UNAVAILABLE`, `TIMEOUT`, `UNKNOWN_ERROR`. No new failure codes needed for the first spike.

**One gap to watch:** If browser execution produces large diagnostic data (screenshots, full DOM dumps), `details` dicts in event payloads could become very large. This is not a Gate 4 blocker — event payloads are JSONB and can absorb it — but if screenshots appear, they should be stored externally (filesystem/S3) with only a path reference in the event payload.

---

### Q5. Is the current synchronous execution model acceptable for the first live browser slice, or must off-thread/async execution be addressed first?

**Verdict: Already addressed. The current model is acceptable for the first spike.**

Evidence:

1. **All routes use `asyncio.to_thread`.**
   - `orchestrate.py:66`: `await asyncio.to_thread(service.submit_snapshot, payload)`
   - `orchestrate.py:92`: `await asyncio.to_thread(_load_task_list_items, ...)`
   - `orchestrate.py:109`: `await asyncio.to_thread(_load_task_view, ...)`
   - `health.py:63,79`: `await asyncio.to_thread(...)` for both health and readiness

   This means synchronous browser execution (which could take 30-60 seconds) will NOT block the FastAPI event loop. Other requests (health checks, task listing) remain responsive.

2. **`InMemoryTaskRepository` is thread-safe** via `RLock` on all operations.

3. **`ModelConcurrencyGate` is thread-safe** via `Lock`.

**Remaining thread-safety concerns for live browser:**

- **`BrowserSessionState`** (`session.py:14-21`) is a mutable dataclass without locks. `mark_active()` and `mark_error()` mutate `self._state.active` and `self._state.last_error`. With `asyncio.to_thread`, two concurrent browser executions could race on session state. For the first spike (single concurrent request), this is acceptable. Before concurrent browser use, `BrowserSessionManager` needs a lock.

- **`CancellationToken`** (`contracts.py:67-76`) uses a plain `bool`. CPython's GIL makes `bool` assignment atomic, so this works in practice. For correctness, `threading.Event` would be cleaner, but is not a Gate 4 blocker.

**Assessment:** `asyncio.to_thread` is sufficient for a first spike where only one browser execution runs at a time (enforced by `concurrency_limit=1` on all browser models in the registry). The thread-safety gap in `BrowserSessionManager` must be addressed before lifting concurrency limits.

---

### Q6. Does the current composition root in `src/gracekelly/main.py` remain acceptable for a first live driver, or is refactoring required before adding real browser runtime dependencies?

**Verdict: Acceptable. One minor addition needed, no refactoring.**

The current `build_browser_automation()` function dispatches on `browser_automation_backend`:
- `"null"` → `NullBrowserAutomation()`
- `"scripted"` → `ScriptedBrowserAutomation(...)`
- else → `ValueError`

Adding a live driver requires one new branch:
```python
if backend == "playwright":
    from gracekelly.adapters.browser.playwright import PlaywrightBrowserAutomation
    return PlaywrightBrowserAutomation(...)
```

This is minimal and follows the existing pattern. The lazy import (inside the `if` branch) is already established by `build_task_repository` for PostgreSQL. No structural refactoring needed.

**One concern:** Playwright browser launch is expensive (~1-3 seconds) and should ideally happen once at startup rather than per-request. The current `build_browser_automation()` is called once in `create_app()` and the result is stored in `app.state.browser_adapter`, so this is already correct — the automation instance is a singleton for the app lifetime.

**However:** There is no `lifespan` context manager on the FastAPI app. If Playwright needs explicit cleanup (closing browser context, releasing resources), a lifespan handler should be added:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # cleanup browser resources
```
This is a nice-to-have for the first spike (process exit handles cleanup), but should be added before sustained use.

**`app = create_app()` at module level** (`main.py:115`) remains a minor wart — it eagerly creates the app at import time. This doesn't affect the live driver specifically, but it means importing `gracekelly.main` always triggers full wiring. For a first spike, this is acceptable.

---

### Q7. What is the smallest safe live-browser milestone that keeps rollback easy if the provider UI changes?

**Recommended milestone:**

1. **New file:** `src/gracekelly/adapters/browser/playwright_driver.py` implementing `BrowserAutomationPort`
2. **Minimal implementation:** Only `ensure_session`, `auth_status`, `select_model`, `submit_prompt`
3. **Deferred:** `recover_auth` returns same as `auth_status` (no active recovery). `dismiss_popups` is a no-op (log and continue).
4. **New backend value:** `GRACEKELLY_BROWSER_AUTOMATION_BACKEND=playwright`
5. **One model, one prompt:** Test against a single browser model (e.g., Kimi K2.5 on Perplexity)
6. **Scripted fallback preserved:** `scripted` backend remains the default and continues working unchanged

**Rollback:** Set `GRACEKELLY_BROWSER_AUTOMATION_BACKEND=scripted` in env. Instant rollback, zero code changes.

**Selector resilience:** Extract all CSS/XPath selectors into a single `selectors.py` or dataclass so DOM breakage requires updating one file, not scattered string literals.

**Acceptance criteria for this milestone:**
- [ ] Playwright driver launches a browser with an existing Perplexity profile
- [ ] Prompt submission produces non-empty `output_text` for at least one model
- [ ] Auth check returns `logged_in=True` for a pre-authenticated profile
- [ ] Model selection returns the correct `actual_label` for the requested model
- [ ] `FailureCode.AUTH_FAILED` is returned when the profile is not authenticated
- [ ] `FailureCode.MODEL_MISMATCH` is returned when the UI shows a different model
- [ ] All 68 existing tests still pass (no regression)
- [ ] Scripted backend remains fully functional as fallback

---

### Q8. What browser-specific data must remain out of normalized storage for now?

**Must stay OUT of `gk_task_steps` and `gk_task_events` schema:**

| Data type | Reason | Where it should go |
|---|---|---|
| Screenshots (PNG/WebP) | Binary, large (100KB-2MB each) | Filesystem, referenced by path in `details` |
| Full DOM snapshots | Large text (100KB+), volatile structure | Filesystem or structured logging |
| Browser console logs | Potentially unbounded, debug-only | Structured logging (structlog/JSON) |
| Network waterfall / HAR | Large, debug-only | Filesystem |
| Playwright trace files | Binary, large | Filesystem |
| CSS selector state | Volatile, implementation detail | Adapter-internal or structured logging |
| Cookie/session dumps | Sensitive | Never persisted outside browser profile |

**Acceptable in `ExecutionResult.details` → event payloads (JSONB):**

| Data type | Size | Reason |
|---|---|---|
| Requested vs actual model label | ~100 bytes | Essential for model-mismatch forensics |
| Page URL at submission time | ~200 bytes | Essential for debugging provider changes |
| Selector timing (ms per step) | ~200 bytes | Performance forensics |
| Auth check result | ~50 bytes | Auth failure forensics |
| Popup dismissal count | ~20 bytes | Operational awareness |
| Driver type ("playwright", "scripted") | ~20 bytes | Adapter identification |

**Rule of thumb:** Structured metadata under 1KB goes into event `details`. Anything larger or binary goes to filesystem with a path reference.

---

## Constraint verification

| Constraint | Status | Evidence |
|---|---|---|
| `core/` stays provider- and browser-agnostic | **Holds** | Zero imports from `adapters/` in `core/`. Dispatch by string `backend.value`, not by type. |
| Browser-specific failure handling stays in `adapters/browser/` | **Holds** | `PerplexityBrowserAdapter.execute()` maps all browser failures to `FailureCode` enum values. No browser error types escape the adapter. |
| `gk_task_steps` must not be widened for browser debug data | **Holds** | Debug data flows through `ExecutionResult.details` → event payloads. Step table has no browser-specific columns. |
| Memory and PostgreSQL behavior stay aligned at contract level | **Holds** | Both implement `TaskRepository` ABC. Both use the same `TaskRecord`/`TaskStepRecord`/`TaskEventRecord` types. `InMemoryTaskRepository` now mirrors PostgreSQL's `sequence_no` uniqueness constraint. |
| Scripted backend remains as stable fallback/test path | **Holds** | `ScriptedBrowserAutomation` has no dependencies on live browser code. It is wired via `build_browser_automation()` based on env var. Adding a new backend does not touch the scripted path. |
| This phase must not smuggle in worker extraction, retries, or queue infrastructure | **Holds** | No worker, retry, or queue code exists. Execution is synchronous within `asyncio.to_thread`. The recommended milestone adds only a new `BrowserAutomationPort` implementation. |

---

## Issues found during review

### Issue 1 (LOW): `BrowserSessionState` is not thread-safe

**File:** `adapters/browser/session.py:14-21`

`BrowserSessionState` is a mutable dataclass accessed from `PerplexityBrowserAdapter.execute()`, which now runs in `asyncio.to_thread`. `mark_active()` and `mark_error()` mutate state without synchronization.

**Current risk:** Low. All browser models have `concurrency_limit=1`, so only one browser execution runs at a time. Two concurrent browser requests for different models could still race.

**Recommendation:** Add a `Lock` to `BrowserSessionManager` before lifting concurrency limits or supporting multiple browser providers. Not a Gate 4 blocker.

### Issue 2 (LOW): No `lifespan` handler for browser resource cleanup

**File:** `main.py`

If a Playwright browser context is created at app startup, there is no explicit cleanup on shutdown. Process exit handles this for a first spike, but sustained use should add a FastAPI `lifespan` context manager.

**Recommendation:** Add a minimal lifespan when the Playwright driver lands. Not a Gate 4 blocker.

### Issue 3 (INFO): `app = create_app()` at module level

**File:** `main.py:115`

Module-level app creation means all adapter construction (including future Playwright browser launch) happens at import time. This is established behavior and does not block the first spike, but could slow down test imports if Playwright launch is expensive.

**Recommendation:** Consider `--factory` mode (`uvicorn gracekelly.main:create_app --factory`) for production. Not a Gate 4 blocker.

### Issue 4 (INFO): Logging coverage is minimal

Only `orchestrator.py` has a logger. Browser adapter execution (auth checks, model selection, prompt submission, failures) has no logging. For forensics during the first live spike, adapter-level logging would be very valuable.

**Recommendation:** Add a logger to `PerplexityBrowserAdapter` and to the future Playwright driver. Log at INFO for successful steps, WARNING for failures. Not a Gate 4 blocker, but strongly recommended before the first live execution.

---

## Verdict

**Approve the current boundary. Proceed with a minimal live browser driver.**

The adapter boundary is clean. `core/` is genuinely browser-agnostic. `ExecutionRequest` is expressive enough. Task/step/event contracts support browser forensics without schema widening. The synchronous execution model has been properly offloaded to threads. The composition root needs only one new branch, not a refactoring.

**Conditions (recommended, not blocking):**

1. Extract all DOM selectors into a single file or dataclass in the first Playwright driver commit, so provider UI changes require updating one location.
2. Add a logger to the browser adapter layer before the first live execution.
3. Keep `concurrency_limit=1` for all browser models until `BrowserSessionManager` gets a lock.
4. Store screenshots and large diagnostic data on filesystem, not in event payloads.
