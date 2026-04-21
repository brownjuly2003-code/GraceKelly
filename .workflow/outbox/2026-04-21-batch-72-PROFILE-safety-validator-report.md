# PROFILE-safety-validator (retrospective CC-authored)

Date: 2026-04-21

## Files changed
- `src/gracekelly/main.py` (startup validator, ~src/gracekelly/main.py:271 per CX note)
- `tests/test_app_startup.py` (new validation tests, ~:112 per CX note)

## Result
- Lifespan startup now fails fast if `GRACEKELLY_BROWSER_ENABLED=true` AND `BROWSER_PROFILE_DIR` matches a live Chrome profile pattern (`AppData\Local\Google\Chrome\User Data\...\Default` on Windows, macOS/Linux equivalents) OR contains an active `SingletonLock`/`SingletonSocket`.
- Error message includes the offending path and a pointer to `python scripts/bootstrap_chrome_profile.py`.
- `BROWSER_ENABLED=false` bypasses the validator (tests verify).

## Tests
- Four new cases in `tests/test_app_startup.py`: (a) dedicated dir — boot succeeds; (b) AppData pattern — RuntimeError with expected message; (c) SingletonLock present — RuntimeError; (d) BROWSER_ENABLED=false — skipped.

## ruff / mypy
- `ruff check src tests` — clean.
- `mypy src` — clean.

## Open questions
- psutil-based live-process scan intentionally not added — stdlib path/file signals only.
