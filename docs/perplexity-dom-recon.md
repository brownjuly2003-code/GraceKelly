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

- One authenticated prompt -> response smoke with a dedicated unlocked profile
- Logged-in response container selector(s) from a successful answer render
- Logged-in model-menu structure after opening the model picker
