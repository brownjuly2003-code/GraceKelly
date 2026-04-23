# batch-98 - HEALTH-ready-probe-semantic

## Summary

Aligned `/healthz/ready` with the Gate 2 readiness semantics while keeping the
probe shallow. The endpoint now returns `503` for missing storage, missing
`execution_router`, and for `browser_enabled=True` when `browser_adapter` is
not initialised. No deep healthcheck calls, I/O, or per-hit logging were added.

## Deliverables

- `src/gracekelly/api/routes/health.py`
  - Extended `readiness_probe` to gate on `task_repository`,
    `execution_router`, `settings.browser_enabled`, and `browser_adapter`
    through attribute reads only.
- `tests/test_healthz_live.py`
  - Updated the existing green path to provide `execution_router`.
  - Added readiness regressions:
    - `test_readiness_returns_503_without_execution_router`
    - `test_readiness_returns_503_when_browser_enabled_without_adapter`
    - `test_readiness_returns_ok_when_browser_disabled_without_adapter`
- `docs/gates/2026-04-23-gate-2-operational-review.md`
  - Criterion 2 moved from `FAIL` to `PASS`.
  - Verdict moved from `PASS with conditions` to `PASS`.
  - Open deviation for the shallow probe was removed and recorded as fixed in
    batch-98.

## Readiness attributes used

- `state.task_repository`
- `state.execution_router`
- `state.settings.browser_enabled`
- `state.browser_adapter`

## Criterion 2 status

- Before: `FAIL`
- After: `PASS`

## Gate verification

- `ruff check src tests` -> clean.
- `.venv/Scripts/python.exe -m mypy src --strict` -> `Success: no issues found in 106 source files`.
- `.venv/Scripts/python.exe -m pytest tests/test_http_api.py -q` -> `56 passed`.
- `.venv/Scripts/python.exe -m pytest tests/test_healthz_live.py -q` -> `6 passed`.

## Notes

- The regression coverage lives in `tests/test_healthz_live.py` because that is
  the existing readiness-probe test file referenced by the batch spec's
  "corresponding test-file" allowance.
