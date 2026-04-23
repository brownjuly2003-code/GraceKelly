# RECON-best-alias-live

Status: success

## Pre-check

- `Get-CimInstance Win32_Process ... chrome-profile|perplexity-profile` returned no active `chrome.exe` processes.
- No `Singleton*` or `LOCK` files were present under:
  - `D:\GraceKelly\chrome-profile`
  - `D:\GraceKelly\tmp\browser-recon\perplexity-profile`

## Command

```powershell
.\.venv\Scripts\gracekelly-capture-perplexity-recon.exe `
  --profile-dir D:\GraceKelly\tmp\browser-recon\perplexity-profile `
  --output-dir D:\GraceKelly\tmp\browser-recon\2026-04-23
```

Exit code: `0`

## Bundle

Captured in `tmp/browser-recon/2026-04-23/`:

- `recon-01-buttons.json`
- `recon-01-composer.html`
- `recon-01-home.png`
- `recon-03-model-menu.json`
- `recon-03-model-menu-attrs.json`
- `recon-03-model-picker.png`
- `recon-99-manifest.json`

Manifest confirms:

- `direct_model_button_visible=true`
- `more_button_visible=false`
- `more_clicked=false`
- `model_menu_snapshot` present
- `model_menu_attrs_snapshot` present

## Comparison

| item | tag | role | aria_label | aria_selected | data_state | data_testid | class_list (top-3) | parent_tag |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Best | `div` | `menuitemradio` | `null` | `false` | `unchecked` | `null` | `focus:outline-none`, `max-w-full`, `w-full` | `div` |
| Sonar | `div` | `menuitemradio` | `null` | `false` | `unchecked` | `null` | `focus:outline-none`, `max-w-full`, `w-full` | `div` |
| GPT-5.4 | `div` | `menuitemradio` | `null` | `false` | `unchecked` | `null` | `focus:outline-none`, `max-w-full`, `w-full` | `div` |
| Claude Sonnet 4.6 | `div` | `menuitemradio` | `null` | `false` | `unchecked` | `null` | `focus:outline-none`, `max-w-full`, `w-full` | `div` |

Additional observed item state:

- current checked item in the menu: `Gemini 3.1 Pro`
- checked marker shape: `role="menuitemradio"`, `aria_selected=true` (via `aria-checked` fallback), `data_state=checked`

## Findings

1. `Best` is present in the live menu and is not hidden or removed.
2. `Best`, `Sonar`, `GPT-5.4`, and `Claude Sonnet 4.6` are all represented by the same clickable container shape:
   - `div[role="menuitemradio"][data-state="unchecked"]`
   - same parent tag (`div`)
   - same leading classes
3. There is no unique `aria-label` or `data-*` attribute on `Best`.
4. The distinguishing signal is structural/textual, not attribute-based:
   - one clickable `menuitemradio` entry per target model in `recon-03-model-menu-attrs.json`
   - but multiple nested DOM nodes per label across `span` and ancestor `div`s
5. Whole-DOM text/label counts while the menu is open:
   - `Best`: exact text `4`, aria-label `0`
   - `Sonar`: exact text `7`, aria-label `0`
   - `GPT-5.4`: exact text `7`, aria-label `0`
   - `Claude Sonnet 4.6`: exact text `7`, aria-label `0`
6. Those repeated text hits are nested nodes inside the same menu item subtree, not duplicate menu choices.
7. No live submit was performed. DOM evidence was sufficient and the batch quota remained unused.

## Answers

### Multiple elements matching `Best`

Yes, but only if the selector is too broad.

- Broad text matching (`*` / `:has-text("Best")`) sees multiple nested nodes in the same subtree.
- Clickable menu-entry matching is unambiguous: exactly one `role="menuitemradio"` item corresponds to `Best`.
- No `aria-label="Best"` element exists.

### Unique attribute for `Best`

No.

- `aria_label`: `null`
- `data_state`: same as the other unchecked entries
- `data_testid`: `null`

The stable discriminator is:

- menu scope: `[data-radix-popper-content-wrapper]`
- item role: `[role="menuitemradio"]`
- exact child text: `Best`

### Optional live submit

Skipped by design. DOM capture alone answered the selector question.

## Decision

`SELECTOR_DISAMBIGUATE`

Reasoning:

- `Best` is still a real, visible, clickable menu item.
- The failure is not that `Best` disappeared or is unreachable.
- The failure is that a broad selector can over-match nested text nodes, and older logic that only looked for `menuitem` / `option` / `button` misses the actual `menuitemradio` nodes used by the live UI.

Recommended batch-88 locator:

```text
[data-radix-popper-content-wrapper] [role="menuitemradio"]
  filtered to the entry that contains exact text "Best"
```

Playwright shape:

```python
page.locator('[data-radix-popper-content-wrapper] [role="menuitemradio"]').filter(
    has=page.get_by_text("Best", exact=True)
)
```

This keeps the match at the clickable container level and avoids broad nested-text overreach.
