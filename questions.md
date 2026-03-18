# Open Questions

Updated: 2026-03-18

## Browser model-picker drift

Context:
- The dedicated authenticated Perplexity profile still supports `prompt -> response` execution.
- Explicit browser model selection is no longer stable.
- Earlier authenticated recon saw `button[aria-label="Model"]` and a real model menu.
- Later authenticated runs often expose only `New Thread`, `More`, and repeated `More options` buttons.
- Current live diagnostics show `model_menu_snapshot=[]` and `model_selection_verified=false`, so GraceKelly can no longer claim that it selected the requested browser model safely.

Questions:

1. Current DOM path
   - In the current authenticated Perplexity UI, where does model selection live now?
   - Is it still a visible top-level control, hidden behind `More`, shown only on the clean home composer, or shown only after some other UI transition?

2. Recon artifact set
   - What is the most practical artifact set to capture this reliably?
   - Recommended minimum:
     - screenshot of the clean authenticated composer
     - screenshot after opening `More`
     - screenshot after opening the model picker, if it exists
     - the key button labels / selectors that actually appear in this state

3. Runtime behavior until rediscovery
   - Until the new picker path is confirmed, what behavior is preferable in production-like browser runs?
   - Options under consideration:
     - fail closed when an explicit browser model is requested
     - continue with prompt execution but mark `model_selection_verified=false`
     - allow prompt-only smoke mode and block model-specific browser runs

4. Selector strategy after rediscovery
   - Once the new control is found, what implementation is safer?
   - Candidate strategies:
     - one strict selector for the real picker
     - layered fallback: direct picker -> `More` -> model menu
     - feature-flagged unverified mode for accounts where the picker is inconsistent

5. Catalog semantics
   - If browser model selection remains unstable for some accounts, how should `/api/v1/models` represent browser availability?
   - Should browser models stay `observed_available` only when the live picker is verified, or is menu observation without successful selection still enough?

Request for practical advice:
- If you have a recommended implementation path here, the most useful guidance would be:
  - which fallback policy to prefer
  - whether to route through `More`
  - whether browser runs should temporarily degrade to prompt-only mode until model selection is re-stabilized

Resolved:
- 2026-03-17: dedicated Playwright profile created at `D:\GraceKelly\tmp\browser-recon\perplexity-profile`
- 2026-03-17: authenticated live smoke passed at least once via `pytest -q tests/test_playwright_live.py -rA`
- 2026-03-17: busy-profile failures now surface as an explicit provider-availability error instead of a generic browser crash
