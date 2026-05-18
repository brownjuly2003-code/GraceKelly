# CX task — Fix Perplexity model picker drift (runtime opens MODE menu instead of MODEL menu)

## Goal

Restore `select_model` reliability against the current Perplexity Pro composer UI. After this task lands, `POST /api/v1/pipeline {model: claude-sonnet-4-6}` (and `gpt-5-4`, etc.) against a running `:8011` uvicorn with `GRACEKELLY_EXECUTION_PROFILE=hybrid` and a logged-in `chrome-profile/` must consistently end with `model_selection_verified=true`, not `code=model_mismatch ... UI shows 'Search'`.

## Context — root cause as observed

Direct consumer reproducer recorded at `logs/gk-day3.log` (2026-05-17 23:10:27..23:11:43). Two pipeline calls (`gpt-5-4`, `claude-sonnet-4-6`) each retried 3× with the same diagnostic:

```
gracekelly.adapters.browser.playwright_driver: Perplexity model option
  '<MODEL>' was not found; current menu appears to start with 'Search'.
```

The shell-noise list in `src/gracekelly/adapters/browser/selectors.py:43-74` (`shell_noise_lines`) confirms `'Search'` belongs to the **Mode** picker surface (Search / Pro Search / Deep Research / Labs), not the Model picker. So the runtime is opening the wrong dropdown.

Static recon snapshot at `.workflow/state/perplexity-selectors-latest.json` (captured 2026-04-26, 22 days stale) still records the correct Model menu (`Best, Claude Opus 4.7, Claude Sonnet 4.6, GPT-5.4, GPT-5.5, Gemini 3.1 Pro, Kimi K2.6, Max, Nemotron 3 Super, ...`) and `direct_model_button_visible=true` — meaning recon's click selector chain landed correctly *then*. The runtime adapter and the recon tool use the same selector pair (`PerplexitySelectors.composer_model_button` / `PerplexitySelectors.model_button` via `_resolve_model_button` at `src/gracekelly/adapters/browser/playwright_driver.py:1072`), so the regression is selector-level: either Perplexity added another `aria-haspopup="menu"` button to the composer (Mode picker) which now wins the `:first-visible` race against the Model picker, or it renamed the Model button's `aria-label` away from the literal `"Model"`.

Three observable hints in the same recon snapshot support the latter:

1. `home_buttons` order: `['Add files or tools::', 'Claude Sonnet 4.6::Claude Sonnet 4.6', 'Computer', 'Dictation::', 'Use voice mode::']`. The second entry has the **current model name** as both visible text *and* `aria-label` — so `button[aria-label="Model"]` (selectors.py:9) will not match any button. Only `composer_model_button` (selectors.py:10-14, `aria-haspopup="menu"` with negative filters for `Add files or tools` and `More`) carries weight.
2. `direct_model_button_visible: true` proves *some* `aria-haspopup="menu"` button is visible in the composer. But the filter list is incomplete — a new Mode picker button with `aria-haspopup="menu"` and a label like `Search` / `Search mode` / `Mode` would pass the existing `:not()` guards.
3. The `shell_noise_lines` already enumerates `Search` and friends — i.e. previous batches knew these strings exist somewhere in the composer chrome. They're now reachable through a real dropdown.

The cron `gracekelly-recon-weekly` (Task Scheduler, Friday 03:00) is the existing drift sentinel, but the snapshot file is dated 2026-04-26, so either no cron has fired since (the file would still be re-written on no-drift runs depending on implementation) or recon's diff logic doesn't catch *additions* of a sibling button with the same selector signature. That is in scope to verify but a separate finding from the runtime fix.

## Deliverables

1. **Adapter disambiguation in `src/gracekelly/adapters/browser/playwright_driver.py`**.
   - After `_open_model_menu` returns (line 745) and before returning `menu_texts`, **validate the opened menu is the Model menu** by checking that the rendered top items contain at least one model-shaped label (heuristic: any line that matches one of the known `model_menu` entries in `.workflow/state/perplexity-selectors-latest.json` or the baseline at `perplexity-selectors-baseline.json`, OR satisfies `_looks_like_model_label` at line 814 and is **not** in `shell_noise_lines`). If the first non-empty line equals `Search`, `Pro Search`, `Deep Research`, `Labs`, or any other `shell_noise_lines` entry, the wrong menu was opened — close it (`page.keyboard.press("Escape")`) and **try the next visible composer popup button** that wasn't the one just clicked.
   - The retry contract: `_open_model_menu` already loops `_MODEL_MENU_OPEN_ATTEMPTS` times reusing the *same* `model_button`. Extend the loop to also rotate through alternate visible candidates returned by `_resolve_model_button` *and* the broader DOM query `div[data-ask-input-container="true"] button[aria-haspopup="menu"]` (minus the previously-tried button). Track tried locators by `aria-label` or by `bounding_box` so a clicked-but-wrong button isn't retried within the same attempt.
   - Log a single WARNING per wrong-menu rotation (`Opened menu starts with '%s'; trying next composer popup`) so the day-3 diagnostic doesn't blow up to N×WARN per call.

2. **Selector hardening in `src/gracekelly/adapters/browser/selectors.py`**.
   - Replace the literal `aria-label="Model"` on `model_button` with a selector that tolerates the **current-model-name** aria-label pattern. Two acceptable approaches: (a) a tuple of fallback selectors driven from the known model catalog (any `button[aria-label]` whose label is in the model catalog labels list), or (b) a structural selector that does not depend on `aria-label` content (e.g. the composer-scoped `button[aria-haspopup="menu"]` that is **adjacent** to the prompt input but not the `Add files or tools` / `More` / `Dictation` buttons — and not a Mode picker). Approach (a) is more robust; approach (b) is the existing `composer_model_button` plus an exclusion. Pick (a) if the catalog is already accessible at runtime, else (b).
   - Extend `composer_model_button`'s `:not()` chain to exclude the Mode picker. Concretely: capture the new button's `aria-label` from a fresh recon (see deliverable 4 below) and add it to the exclusion list, plus add a defensive `:not([aria-label*="Search" i])` / `:not([aria-label*="Mode" i])` if the new button's label contains either.
   - Treat the new selector behaviour as a contract — add a comment block above the `PerplexitySelectors` dataclass describing the disambiguation rule and the date of the regression. Do **not** import the spec date into runtime code.

3. **Regression tests in `tests/test_playwright_driver.py`** (and where appropriate `tests/test_browser_adapter.py`).
   - New test `test_open_model_menu_skips_mode_picker_and_retries_alternate_button`: a `_FakePage` that exposes two composer popup buttons; clicking the first opens a menu whose first item is `'Search'`; clicking the second opens a menu whose first item is `'Best'`. Assert `select_model('GPT-5.4', ...)` ends with `model_selection_verified=True` and `actual_label` matches, and that `_open_model_menu` consumed exactly two distinct clicks plus one `Escape`.
   - New test `test_open_model_menu_returns_model_mismatch_when_no_button_yields_model_menu`: both fake buttons return Mode menus (or any `shell_noise_lines` first entry). Assert the final result is `code=model_mismatch` with `actual_label_source="option_not_found_menu_snapshot"`, and that no production WARNING storm (>3 WARNs per call) fires.
   - New test `test_resolve_model_button_matches_dynamic_aria_label`: a `_FakePage` where the only matching button is `<button aria-label="Claude Sonnet 4.6" aria-haspopup="menu">` inside `div[data-ask-input-container="true"]`. Assert `_resolve_model_button` returns a non-None locator.
   - Keep the existing 29 tests in `tests/test_browser_adapter.py` green. Specifically `_MODEL_SELECT_RETRY_DELAY_S` patching from batch-108 must still work — these new tests should patch the same constant to `0.0` when they exercise the retry loop.

4. **Recon refresh + drift logic**. **Do not run** `tools/capture_perplexity_recon.py` from CX — it requires the user's logged-in `chrome-profile/` and is currently held by her running Chrome. Instead:
   - Document in the closure report what static evidence supports the new selector (e.g. `home_buttons` ordering, button counts, the new `aria-label` value if it's already in the existing snapshot via the `composer_html` artefact at `.workflow/state/perplexity-recon-*/composer_html`).
   - If `composer_html` does not contain the new button (likely — snapshot is from 2026-04-26), flag this as a follow-up for the user to run `python -m gracekelly.tools.capture_perplexity_recon --output .workflow/state/perplexity-recon-2026-05-18/` herself, against her live chrome-profile, **after** the adapter fix is committed. The fix above is structural — it should pass regression even before a refreshed recon.
   - In `src/gracekelly/cli/recon_weekly.py` (or wherever the `gracekelly-recon-weekly` entry point lives — look at `pyproject.toml [project.scripts]`), audit the diff predicate. If it only checks `model_menu` *equality* and ignores **additions** to `home_buttons`, extend it to detect a new composer popup button (count of `aria-haspopup="menu"` buttons in `home_buttons` increases vs baseline) and fail-with-drift accordingly. Add at least one test for this drift dimension in `tests/test_recon_weekly.py`.

## Verification (R1-R5 battery)

- **R1 (unit/integration)**: `pytest tests/test_playwright_driver.py tests/test_browser_adapter.py tests/test_recon_weekly.py -v` — all green. Full suite `pytest -q` continues to report **0 failures** (current baseline: 2661 passed / 6 skipped per batch-110 closure).
- **R2 (type)**: `.venv/Scripts/python.exe -m mypy src --strict` — 0 errors on the touched files. Per `Known gotchas` in the project memory, use the venv Python, not global.
- **R3 (lint)**: `ruff check src tests` clean.
- **R4 (diff hygiene)**: `git diff --check` clean. No edits to `.claude/`, `.codex/`, `.workflow/state/` (recon refresh is gated to the user). No edits to `selectors.py` beyond the disambiguation chain — preserve `prompt_input`, `submit_button`, `stop_response_button`, `response_candidates`, `ready_markers`, `signed_out_markers` exactly.
- **R5 (closure report)**: write `.workflow/outbox/2026-05-18-perplexity-model-picker-drift-report.md` summarising root cause confirmation, the chosen selector strategy (approach a vs b), test additions, and the recon-cron drift-predicate change. Include the `git log --oneline` for the new commits and the final `pytest -q` summary line. Move this spec to `.workflow/done/2026-05-18-perplexity-model-picker-drift.md`, refresh `.workflow/.done`, remove `.workflow/inbox/.ready`.

## Out of scope

- Switching the runtime adapter to `*-api` direct paths. `.env` does not carry `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` by design and that's a separate user decision documented in `CLAUDE.md` Operating Risks.
- Refactoring `_open_model_menu` beyond the disambiguation rotation (no architectural change to the picker resolution flow).
- Touching the `chrome-profile/` directory or running any live Playwright against `perplexity.ai` — the user's Chrome session must not be evicted.
- Re-running `tools/capture_perplexity_recon.py` from CX (see deliverable 4 — gated to the user).
- Pinned-model UI work in `static/js/model-menu.js` (batch-82 territory, unrelated).
- Touching the `*-api` fallback path (batch-89 — works once API keys are present).

## Commit convention

`batch-NN: task-id — phrase` per project convention. Two suggested commits: one for the adapter+selector fix, one for the recon-weekly drift-predicate extension. Closure commit refreshes `.done`. If unsure about NN, the last landed batch in `.workflow/done/` is batch-109; this slot is batch-111 (batch-110 was the test-double goto signature fix on `b166de8`, docs-site is unnumbered).
