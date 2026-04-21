# DIAG-orchestrate-500

## Context
- Batch 69 fixed the route-side unknown-error fallback and made Playwright sign-in overlays surface as `PermissionError` instead of an opaque crash.
- The live repro captured on `2026-04-20` against `http://127.0.0.1:8012/` did not reproduce an unhandled HTTP `500`; it returned `200` from `/api/v1/orchestrate/stream`, then the task failed because Perplexity's login modal intercepted model selection.
- Fresh closure verification on `2026-04-21` is green on the current tree: `2566 passed`, `6 skipped`, `coverage 97%`, `ruff` and `mypy` clean.

## Options
- A = partial close in place: keep the DIAG report only, note that the remaining live failure is auth-related, and stop without creating follow-up work.
- B = split new task: close the route-level `500` work as partial and create a dedicated auth-flow task for the Perplexity login overlay.

## Chosen
- B = split new task.

## Rationale
- The remaining live failure is an authentication/session problem, not the same root cause as the original unhandled `500` path.
- Keeping it in the DIAG task would blur two separate acceptance conditions: structured server fallback versus browser-session readiness.
- The current code changes from batch 69 remain valid and should not be reverted: structured `500` fallback in the route and `PermissionError` handling in the Playwright driver both belong to the diagnosis work already completed.

## Rollback
- If a later repro shows a real unhandled `500` again on the same current tree, reopen DIAG-orchestrate-500 and merge the AUTH overlay task back into the DIAG track.
