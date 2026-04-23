# DOCS-operator-runbook-live-smoke

Status: success

Summary:
- Added `## Live smoke harness` to `docs/operator-runbook.md`.
- Documented preconditions for the authenticated Chrome profile, uvicorn runtime, and the PowerShell pre-check that verifies no `chrome.exe` process is holding the profile.
- Added a supported-pattern matrix covering `smart`, `debate`, `consensus`, `compare`, and `upload` with API path, UI label/fallback note, default prompt summary, quota expectation, and minimum answer length.
- Added concrete usage examples for all five patterns, including `--attachment <path>` for upload.
- Added report location guidance, result interpretation, the fallback coverage note pointing to `tests/test_router_fallback.py`, and the explicit non-coverage note for `smart/v2`, `batch`, and `pipeline`.

Diff notes:
- The new section was inserted after storage validation and before task inspection workflow to keep operational runbook flow intact.
- No other documentation files were changed.

Verification:
- `D:\GraceKelly\.venv\Scripts\python.exe -m pytest -q` -> `2647 passed / 0 failed / 6 skipped / 11 subtests passed`
- `D:\GraceKelly\.venv\Scripts\python.exe -m ruff check D:\GraceKelly\src D:\GraceKelly\tests D:\GraceKelly\scripts\live_smart_smoke.py` -> clean
- `D:\GraceKelly\.venv\Scripts\python.exe -m mypy D:\GraceKelly\src` -> `Success: no issues found in 106 source files`

Scope:
- `docs/operator-runbook.md`

