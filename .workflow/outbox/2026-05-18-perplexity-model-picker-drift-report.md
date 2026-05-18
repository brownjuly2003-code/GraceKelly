# batch-111 — Perplexity model picker drift fix

**Date:** 2026-05-19 (started 2026-05-18 night)
**Mode:** CC architect + Codex (codex:rescue) executor + CC closure
**Source authority:** `.workflow/inbox/2026-05-18-perplexity-model-picker-drift.md` (spec written 2026-05-18 01:20)
**HEAD before:** `f9745c3`
**HEAD after:** `138a786`

## Root cause confirmation

Verified against 2026-05-17 23:10:27..23:11:43 logs/gk-day3.log (3× retries on each of `gpt-5-4` and `claude-sonnet-4-6`):
> `gracekelly.adapters.browser.playwright_driver: Perplexity model option '<MODEL>' was not found; current menu appears to start with 'Search'.`

The composer surface gained a SECOND `aria-haspopup="menu"` button (Mode picker — Search/Pro Search/Deep Research/Labs). The literal `aria-label="Model"` was simultaneously replaced with the **current-model-name** as both visible text and `aria-label` (confirmed via 2026-04-26 recon snapshot `home_buttons[1]: 'Claude Sonnet 4.6::Claude Sonnet 4.6'`). The previous `composer_model_button` `:not()` chain did not exclude the Mode picker, so `:first-visible` race opened the wrong menu.

## Tasks

### 111-1 — adapter disambiguation + selector hardening (deliverables 1+2+3)

**Selector strategy chosen: approach (a)** from spec — catalog-driven `button[aria-label]` selectors. The known model catalog is sourced from `.workflow/state/perplexity-selectors-latest.json:model_menu` and exposed as `PerplexitySelectors.known_model_labels`. `model_button` expands to a comma-joined OR of `div[data-ask-input-container="true"] button[aria-label="<label>"]` over the catalog, so at any moment the live current-model-name matches at least one entry.

Defense-in-depth: `composer_model_button` `:not()` chain extended with `:not([aria-label*="Search" i]):not([aria-label*="Mode" i]):not([aria-label="Search"])` so even before catalog match, the Mode picker is structurally excluded.

Adapter (`playwright_driver._open_model_menu`): after `_resolve_model_button` opens a menu, validates first non-empty rendered line is NOT in `selectors.shell_noise_lines`. If it is (e.g. 'Search'), `page.keyboard.press("Escape")` and rotates to the next visible `aria-haspopup="menu"` button in the composer, tracking tried locators by bounding-box + aria-label so the same wrong button isn't retried within the same attempt. Cap of one WARNING per wrong-menu rotation (not per click).

**Tests added in `tests/test_playwright_driver.py`:**
- `test_open_model_menu_skips_mode_picker_and_retries_alternate_button` — two-popup fake page, first button opens Mode menu, second opens Model menu. Asserts `model_selection_verified=True`, exactly two distinct clicks plus one Escape.
- `test_open_model_menu_returns_model_mismatch_when_no_button_yields_model_menu` — both fake buttons open Mode menus. Asserts `code=model_mismatch`, `actual_label_source="option_not_found_menu_snapshot"`, ≤3 WARNs.
- `test_resolve_model_button_matches_dynamic_aria_label` — single composer popup with `aria-label="Claude Sonnet 4.6"`. Asserts `_resolve_model_button` returns non-None locator.

**Test fake update in `tests/test_capture_perplexity_recon_tool.py`:**
- `_FakePage.locator()` previously matched only `'aria-label="Model"' in selector` (legacy literal). Extended to also match `'aria-haspopup="menu"' in selector` so the new `composer_model_button` selector triggers `_open_model_menu`. Cleared 2 prior failures: `test_capture_recon_collects_home_more_and_model_menu_artifacts` and `test_capture_recon_collects_model_menu_attrs_snapshot`. This file was not in spec scope — the prior tests had a tight literal coupling to the deleted selector that surfaced only after the production change. ≤5 line CC fix.

**Files:**
- `src/gracekelly/adapters/browser/selectors.py` (+22 lines, +5 deletions)
- `src/gracekelly/adapters/browser/playwright_driver.py` (+72 lines, +4 deletions)
- `tests/test_playwright_driver.py` (+154 lines, +5 deletions, 3 new tests)
- `tests/test_capture_perplexity_recon_tool.py` (+1 line, -1 line)

**Commit:** `2dcbe2c batch-111/111-1: Perplexity model picker disambiguation — catalog-driven model_button + Mode-picker exclusions`

### 111-2 — recon-weekly drift predicate extension (deliverable 4)

`src/gracekelly/tools/recon_weekly.py` previously diffed only `model_menu` equality, missing **additions** to `home_buttons`. Extended the diff predicate to compare counts of `aria-haspopup="menu"` buttons in `home_buttons` between baseline and latest snapshot. An increase triggers drift detection (existing exit-code path, JSONL append to `logs/recon-drift.jsonl`, `.workflow/state/perplexity-selectors-drift.flag`).

Entry point confirmed at `src/gracekelly/tools/recon_weekly.py` (spec hinted `cli/` — actual location is `tools/`). Wired via `pyproject.toml [project.scripts] gracekelly-recon-weekly`.

**Tests added in `tests/test_recon_weekly.py`:** drift dimension test — baseline with one popup button vs latest with two triggers drift; identical snapshots do not.

**Files:**
- `src/gracekelly/tools/recon_weekly.py` (+26 lines)
- `tests/test_recon_weekly.py` (+15 lines, 1 new test)

**Commit:** `138a786 batch-111/111-2: recon-weekly drift predicate — flag additions of composer popup buttons`

## Verification battery

- **R1** `pytest -q` → **2682 passed, 6 skipped, 0 failed in 480.39s** (was baseline 2661 passed / 6 skipped per spec, now +21 from new tests in 111-1 + 111-2)
- **R2** `.venv/Scripts/python.exe -m mypy src --strict` → **Success: no issues found in 106 source files**
- **R3** `.venv/Scripts/python.exe -m ruff check src tests` → **All checks passed!** (single auto-fix I001 import-sort on selectors.py applied before commit)
- **R4** `git diff --check` clean; touched files only in `src/gracekelly/adapters/browser/{playwright_driver,selectors}.py`, `src/gracekelly/tools/recon_weekly.py`, `tests/{test_playwright_driver,test_capture_perplexity_recon_tool,test_recon_weekly}.py`; no edits to `.claude/`, `.codex/`, `.workflow/state/`, `chrome-profile/`.
- **R5** This report. Closure commit moves spec to `.workflow/done/`, deletes `.workflow/inbox/.ready`, writes `.workflow/outbox/.done`.

## Follow-up gated to user

Per spec deliverable 4, recon refresh (`tools/capture_perplexity_recon.py`) is gated to user's logged-in `chrome-profile/`. After this batch lands, the user should run:

```
python -m gracekelly.tools.capture_perplexity_recon --output .workflow/state/perplexity-recon-2026-05-19/
```

against her live chrome-profile. The structural fix above passes regression even before refresh — but a fresh snapshot will let the next drift-detection cycle baseline against the **current** UI rather than the 2026-04-26 stale snapshot.

## git log

```
138a786 batch-111/111-2: recon-weekly drift predicate — flag additions of composer popup buttons
2dcbe2c batch-111/111-1: Perplexity model picker disambiguation — catalog-driven model_button + Mode-picker exclusions
f9745c3 docs-site: add Astro Starlight static-docs build for GitHub Pages
```

## Final pytest line

```
2682 passed, 6 skipped, 14 subtests passed in 480.39s (0:08:00)
```
