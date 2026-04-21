# CLOSE-69-scope-reconcile

Date: 2026-04-21

Decisions
- `src/gracekelly/core/orchestrator.py` -> keep in `DIAG-orchestrate-500`
- `tests/test_orchestrator.py` -> keep in `DIAG-orchestrate-500`
- `static/js/app.js` -> keep in `MODEL-dynamic-catalog`
- `static/js/chat.js` remains the only `UI3-chat-js-features` code file so batch-69 commit scopes stay disjoint.
- `src/gracekelly/adapters/browser/playwright_driver.py` stays owned by `DIAG-orchestrate-500`, while `MODEL-dynamic-catalog` keeps the catalog-facing adapter and UI wiring files.

Artifacts updated
- `.workflow/outbox/2026-04-20-batch-69-DIAG-orchestrate-500-report.md`
- `.workflow/outbox/2026-04-20-batch-69-MODEL-dynamic-catalog-report.md`

Rationale
- The orchestrator/test pair is part of the browser-backed DIAG path because it forces browser-only live plans through the real `submit_snapshot()` execution path.
- `static/js/app.js` is part of MODEL because it now fetches `/api/v1/models`, stores `window.modelCatalog`, and surfaces runtime catalog freshness and unavailability in the UI shell.
- Narrowing `UI3` to `static/js/chat.js` keeps the voice/export/help behavior in one JS-owned task while HTML/CSS ownership stays with UI1/UI2.
