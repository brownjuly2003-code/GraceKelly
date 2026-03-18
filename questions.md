# Open Questions

Updated: 2026-03-17

- Current authenticated Perplexity UI for the dedicated profile no longer exposes the previously observed `button[aria-label="Model"]` control during automation. Even from a fresh persistent-context page and after a `New Thread` reset attempt, the live browser path still sees only controls such as `New Thread` / `More`, so GraceKelly can no longer verify or change the active browser model safely. Additional DOM capture or a new selector path is required before browser model selection can be treated as stable again.

Resolved on 2026-03-17:
- dedicated Playwright profile created at `D:\GraceKelly\tmp\browser-recon\perplexity-profile`
- authenticated live smoke passed via `pytest -q tests/test_playwright_live.py -rA`
- busy-profile failures now surface as an explicit provider-availability error instead of a generic browser crash
