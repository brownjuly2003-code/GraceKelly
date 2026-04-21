# MODEL-catalog-kimi-verify (retrospective CC-authored)

Date: 2026-04-21
Closure status: **pending-evidence** — no code change required, evidence pass deferred.

## Files changed
- None planned. CX did modify `static/js/model-menu.js` as part of UI-PO2-parity-rework — that commit owns those changes, not this task.

## Context
- User reports "Kimi in the model list, but Perplexity no longer exposes it" on the live UI.
- `GET /api/v1/models` during batch-73 live smoke returned `count=8`, among them `Kimi K2.5`.
- `src/gracekelly/core/models.py:41` only defines `kimi-k2-5` as a **compatibility alias** for historical task labels — it is NOT seeded into the live catalog.
- Live catalog is built exclusively from `_refresh_model_catalog_labels(adapter)`, which parses the Perplexity model menu via Playwright selectors in `src/gracekelly/adapters/browser/playwright_driver.py`. No hardcoded seed.

## Reasoning
- If Kimi appears in the live catalog, it is because Playwright parsed it out of the Perplexity DOM. Two possibilities:
  1. **Perplexity actually exposes Kimi for Pro accounts** (including user's account) — no fix, close with confirming screenshot of the Perplexity model menu.
  2. **Selector scope is too broad** — catches hidden/archived entries along with active ones. Needs selector narrowing in `playwright_driver.py` plus a regression test with a mock HTML containing both hidden and visible items.

## Evidence required (deferred)
- [ ] `GET /api/v1/models` JSON snapshot from live uvicorn
- [ ] Playwright screenshot of `https://www.perplexity.ai/` model menu opened in `D:/GraceKelly/chrome-profile`
- [ ] Diff: catalog labels vs menu labels

## Open questions
- None blocking; pending evidence pass.
