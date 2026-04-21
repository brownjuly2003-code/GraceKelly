# BOOTSTRAP-onboarding (retrospective CC-authored)

Date: 2026-04-21
Authored by: CC (CX didn't write a report, generated retrospectively from inspection of the working tree).

## Files changed
- `scripts/bootstrap_chrome_profile.py` (new)
- `docs/onboarding.md` (new)
- `.env.example` (updated — reference to bootstrap script + dedicated profile recommendation)

## Result
- Cross-platform script (Windows primary) that (a) creates `./chrome-profile/` if missing, (b) locates `chrome.exe`/Chrome binary, (c) launches with `--user-data-dir=<profile>` on `https://www.perplexity.ai/`, (d) waits for Enter, (e) terminates Chrome tree (`taskkill /T /F` on Windows), (f) prints the final `GRACEKELLY_BROWSER_PROFILE_DIR=...` hint.
- `--dry-run` flag verified locally: prints plan without side effects.
- `docs/onboarding.md` covers Prerequisites / First-time setup / Daily use / Troubleshooting (503, BrowserProfileBusyError).
- `.env.example` now points to `python scripts/bootstrap_chrome_profile.py --dry-run` for first-time setup.

## Tests
- stdlib-only, no new deps.
- `--dry-run` smoke passes without spawning Chrome.

## ruff / mypy
- `ruff check src tests` — clean (no changes to `src/tests`).
- `mypy src` — clean (no changes to `src`).

## Open questions
- Script not automated in CI (no harness for headless Chrome login).
