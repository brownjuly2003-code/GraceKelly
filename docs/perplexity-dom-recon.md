# Perplexity DOM Recon

Date: 2026-03-17

This note captures the first live reconnaissance pass against `https://www.perplexity.ai` before introducing a real Playwright-backed browser driver.

## Method

- Browser tool: Playwright `1.56.0`
- Recon target: `https://www.perplexity.ai/`
- Local artifacts: `tmp/browser-recon/recon-elements.json` and screenshots in `tmp/browser-recon/`
- Profile strategy tested:
  - headless Chromium without a profile
  - headed persistent Chrome context with a copied user-data directory

## Summary

- Headless Chromium hit Cloudflare immediately and returned HTTP `403` with the title `Just a moment...`.
- Headed persistent Chrome reached the real app shell and returned HTTP `200`.
- A copied Chrome profile was enough to render the shell, but it did not preserve authenticated state because locked cookie/session stores could not be copied cleanly while the source browser was active.
- Guest mode still exposed the core composer controls, so the first live slice can anchor itself on real DOM selectors even before a fully authenticated smoke passes.
- A manual Playwright smoke against the copied profile reached prompt entry, but submit was blocked by a `Sign in or create an account` overlay, which is now mapped to `auth_failed` rather than a generic browser crash.

## Stable anchors observed on 2026-03-17

- Prompt input: `div#ask-input[role="textbox"][contenteditable="true"]`
- Model button: `button[aria-label="Model"]`
- Submit button: `button[aria-label="Submit"]` after prompt text is entered
- Attachment/tools button: `button[aria-label="Add files or tools"]`
- Dictation button: `button[aria-label="Dictation"]`
- Cookie banner buttons:
  - `Accept All Cookies`
  - `Necessary Cookies`
- Signed-out markers:
  - `Sign in or create an account`
  - `Continue with Google`
  - `Continue with Apple`
  - `Single sign-on (SSO)`

## Shell text observed

The headed app shell exposed these stable phrases before any authenticated flow:

- `Type @ for connectors and sources`
- `Type / for search modes`
- `Model`
- `Computer`

Those markers are useful for "shell is ready" detection even when the page is not logged in.

## Authenticated model menu observed

A dedicated-profile authenticated pass on 2026-03-17 exposed this menu content after clicking `Model`:

- `Best`
- `Sonar`
- `GPT-5.4`
- `Gemini 3.1 Pro`
- `Claude Sonnet 4.6`
- `Claude Opus 4.6`
- `Max`
- `Nemotron 3 Super`

This matters because the static browser catalog still contains models such as `Kimi K2.5` that were not present in this authenticated menu. The driver now treats a missing requested option as a real model mismatch rather than silently staying on the current default.
The public catalog route also now annotates browser entries against the last observed authenticated menu, so `/api/v1/models` can mark a browser model as `observed_unavailable` instead of advertising it as generically available.

## New authenticated drift observed later on 2026-03-17

Subsequent authenticated Playwright runs against the same dedicated profile still completed prompt submission, but they no longer exposed the previously observed `button[aria-label="Model"]` picker in a stable way.

Observed controls during this drifted state:

- `New Thread`
- `More`
- repeated `More options` buttons in the conversation list

What stayed true:

- prompt submission still worked
- the best response source was still `body_after_prompt`
- model-selection evidence stayed unverified (`model_menu_snapshot=[]`, no selection indicator, no stable post-click model label)

Current implication: browser execution can still prove prompt -> response transport, but explicit model selection should be treated as unstable again until the new authenticated model-picker path is captured.

Latest runtime fallback on 2026-03-18:

- authenticated live smoke passed again after changing the browser adapter to degrade gracefully when the picker is unavailable
- the browser step now keeps running with:
  - `model_picker_unavailable=true`
  - `model_selection_attempted=false`
  - `model_selection_verified=false`
- the winning response source in that degraded state was still `body_after_prompt`

Repeatable capture path from 2026-03-18:

- use `gracekelly-capture-perplexity-recon` to save the current authenticated shell into `tmp/browser-recon/YYYY-MM-DD/`
- use `--interactive-pause` only if the automatic pass still cannot expose the model-picker path

Authenticated recon update on 2026-03-18:

- the current picker path is visible again on the clean composer, but not under the old `aria-label="Model"` shape
- the active-model control is now a composer-scoped menu button labeled with the current model itself, for example `aria-label="GPT-5.4"` with visible text `GPT-5.4`
- an automatic recon pass captured the menu snapshot:
  - `Best`
  - `Sonar`
  - `GPT-5.4`
  - `Gemini 3.1 Pro`
  - `Claude Sonnet 4.6`
  - `Claude Opus 4.6`
  - `Nemotron 3 Super`
- after scoping Playwright to that composer control, a live smoke switched from `GPT-5.4` to `Claude Sonnet 4.6` and returned `model_selection_verified=true`
- a later 2026-03-18 live smoke still extracted the final answer from `body_after_prompt`, not from a stable assistant-message selector, so response extraction remains heuristic even though model selection is restored
- a later prompt-driven recon plus runtime guard around `Stop response` captured the final answer DOM and showed a stable answer path through `main div.prose`
- after that fix, the live adapter path also returned `response_source=main div.prose` with `response_used_body_fallback=false`

## Anti-automation findings

- Headless mode is not a safe default. On 2026-03-17 it was blocked by Cloudflare before the app shell loaded.
- Headed persistent Chrome is a better default for the first live slice.
- Reusing a live `Default` Chrome profile is fragile because the browser keeps cookies and session stores locked.
- The safer operating model is a dedicated browser user-data directory reserved for GraceKelly or an exported state created while Chrome is not running.
- A copied profile may look "ready" enough for prompt entry but still fail at submit time behind a late sign-in overlay.

## Implications for Slice 1

- Keep selectors centralized in one browser-layer module.
- Default the first Playwright backend to headed Chrome.
- Treat signed-out markers as stronger auth evidence than prompt visibility alone.
- Keep model verification shallow in Slice 1; deeper UI verification can wait for a logged-in recon pass.
- Expect response extraction to remain heuristic until an authenticated answer DOM is captured.

## Follow-up capture still needed

- Logged-in response container selector(s) from a successful answer render
- Logged-in model-menu structure after opening the model picker
- Better model-picker selectors than the current best-effort fallback

## Dedicated profile bootstrap

The repo now provides `gracekelly-create-perplexity-profile` to create the dedicated Playwright profile described above. The default output path is `tmp/browser-recon/perplexity-profile`, and the resulting directory can be reused for:

- `GRACEKELLY_BROWSER_PROFILE_DIR` in app runtime
- `pytest -q tests/test_playwright_live.py -rA` for the manual authenticated smoke

Important: close any Chrome windows already using that profile before running the Playwright smoke. If the profile is still busy, the browser adapter now reports an explicit profile-in-use failure instead of a generic crash.

## Best alias recon (2026-04-23)

A fresh authenticated recon bundle in `tmp/browser-recon/2026-04-23/` (committed in `9203f50`) captured the current live model menu with a new `recon-03-model-menu-attrs.json` artifact.

Key findings from that pass:

- `Best`, `Sonar`, `GPT-5.4`, and `Claude Sonnet 4.6` are all visible as `div[role="menuitemradio"]` entries under the same `[data-radix-popper-content-wrapper]` menu.
- `Best` has no unique `aria-label` or `data-*` attribute; like the other unchecked entries, it exposes `data_state=unchecked`, `data_testid=null`, and the same leading class pattern (`focus:outline-none`, `max-w-full`, `w-full`).
- The ambiguity comes from nested text nodes, not duplicate menu items: broad text matching can see multiple descendants whose text includes `Best`, but there is exactly one clickable `role="menuitemradio"` container for the `Best` item.
- The currently checked item in this capture was `Gemini 3.1 Pro`, which also confirmed that the new attrs snapshot must map `aria-checked` into `aria_selected` for radio-style items.

Resolved decision: `SELECTOR_DISAMBIGUATE`.

Reasoning:

- `Best` is still present and clickable in the live UI, so deprecating it would be premature.
- The fix path is to anchor selection to the menu container and the clickable `menuitemradio` element, then filter by exact child text `Best`, instead of relying on broad `has-text("Best")` matching or `menuitem`/`button`-only selectors.
