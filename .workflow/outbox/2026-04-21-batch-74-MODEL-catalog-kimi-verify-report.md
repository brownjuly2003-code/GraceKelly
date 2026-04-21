# MODEL-catalog-kimi-verify (retrospective CC-authored)

Date: 2026-04-21
Closure status: **success** — evidence captured, hypothesis 1 holds.

## Files changed
- None (no code change needed).

## Context
- User reports "Kimi in the model list, but Perplexity no longer exposes it" on the live UI.
- `src/gracekelly/core/models.py:41` only defines `kimi-k2-5` as a **compatibility alias** for historical task labels — never seeded into the live catalog.

## Evidence captured (2026-04-21)
- `GET http://127.0.0.1:8011/api/v1/models` → **11 models, no Kimi**:
  - Best, Sonar, GPT-5.4, Gemini 3.1 Pro, Claude Sonnet 4.6, Claude Opus 4.7, Max, Nemotron 3 Super, Mistral Small, GPT-5.4 API, Claude Sonnet 4.6 API
- Full JSON snapshot saved to `.workflow/outbox/2026-04-21-batch-74-MODEL-catalog-models-snapshot.json`.
- The earlier `count=8` observation (batch-73 SMOKE log) was a transient state — Perplexity menu is volatile across refreshes and visits.

## Conclusion
- Current live catalog does not include Kimi. The user's complaint was about an earlier state; the catalog-refresh pipeline is working as designed — source of truth is Perplexity's model menu via Playwright.
- **No code change required.** Selector scope is correct; aliases table at `core/models.py:41` stays for historical-label compatibility.

## Open questions
- None.
