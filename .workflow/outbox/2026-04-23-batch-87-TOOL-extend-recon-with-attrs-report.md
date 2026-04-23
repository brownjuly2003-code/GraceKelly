# TOOL-extend-recon-with-attrs

Status: success

## Goal

Extend `capture_perplexity_recon.py` so a successful model-menu capture always emits `recon-03-model-menu-attrs.json` and records it in the manifest.

## Files changed

- `src/gracekelly/tools/capture_perplexity_recon.py`
- `src/gracekelly/adapters/browser/selectors.py`
- `tests/test_capture_perplexity_recon_tool.py`

## What landed

- Added `model_menu_attrs_snapshot` emission alongside the existing `model_menu_snapshot`.
- Implemented a single `page.evaluate(...)` DOM walk that records:
  - `tag`
  - `role`
  - `aria_label`
  - `aria_selected` (with `aria-checked` fallback for `menuitemradio`)
  - `data_state`
  - `data_testid`
  - `class_list`
  - `text`
  - `outer_html` (truncated to 1024 chars)
  - `parent_tag`
  - `bounding_box`
- Preserved the legacy `recon-03-model-menu.json` artifact.
- Added a regression test for the new attrs artifact and a second regression test proving the live Perplexity menu uses `role="menuitemradio"` entries.

## Root cause found during live validation

The first implementation only queried `[role="menuitem"], [role="option"], button`.
Live Perplexity currently renders most model choices as `div[role="menuitemradio"]` with `aria-checked`, so the attrs snapshot initially collapsed to a single non-radio entry.

## Verification

- R1: `2607 passed, 6 skipped, 11 subtests passed`
- R2: `2607 passed, 6 skipped, 11 subtests passed`, total coverage `96%` (`+0%` vs `.workflow/state/test-baseline.json`)
- R3: `39 passed`
- R4: no warnings / errors / deprecations in the scoped verbose run
- R5 kill check:
  - killed line: `PerplexitySelectors.model_menu_item_selector`
  - mutation: removed `[role="menuitemradio"]`
  - result: `test_model_menu_attributes_snapshot_includes_menuitemradio_entries` failed with `['Claude Opus 4.7'] != ['Best', 'Sonar', 'GPT-5.4', 'Claude Sonnet 4.6']`

## Notes

- No CLI flags changed.
- No code was added to `playwright_driver.py`, `perplexity.py`, `scripted.py`, or `automation.py`.
