# Open Questions

Updated: 2026-03-18

## Current blocker

The browser path is no longer blocked on prompt transport.
That part is already working.

The remaining blocker is narrower:
- the dedicated authenticated Perplexity profile can still execute `prompt -> response`
- explicit model selection is still unstable
- the next safe step is a fresh authenticated DOM reconnaissance pass against the current UI

## Questions for the next recon pass

1. Profile state
   - Is `D:\GraceKelly\tmp\browser-recon\perplexity-profile` still authenticated and ready for a live headed recon run?
   - Has the profile stayed stable since the last successful smoke, or did Perplexity ask for re-login / extra verification again?

2. Permission to run recon
   - Can a new headed browser recon session be launched now with that dedicated profile?
   - Is it acceptable to save screenshots and JSON/HTML artifacts under `tmp/browser-recon/2026-03-18/`?

3. Interactive help during recon
   - If the current Perplexity shell requires a manual click path, can the user briefly help during the capture session?
   - In particular: open the clean composer, click `More`, or expose the place where the model picker now lives, if it is not reachable automatically on the first pass.

## Minimum artifact set needed

- screenshot of the authenticated home composer
- screenshot after opening `More`, if that control exists
- button inventory from the current toolbar shell
- HTML fragment or DOM snapshot for the composer / toolbar area
- screenshot of the model picker, if it becomes visible

## Why these questions remain open

- `prompt -> response` is already proven again under degraded selection mode
- graceful fallback is already implemented
- `/api/v1/models` already distinguishes `observed_available`, `observed_unverified`, `observed_unavailable`, and `unknown`
- what is still missing is the current real DOM path for model selection in the authenticated UI

## Resolved since the last question round

- Browser runs no longer fail the whole step when the picker is missing; they continue with `model_selection_verified=false`.
- Browser execution now exposes `model_picker_unavailable=true` when the picker does not render.
- `/api/v1/models` now exposes `observed_unverified` and `last_verified_at`.
- The current implementation state is committed in `7d69ace` (`Degrade browser model selection honestly`).
