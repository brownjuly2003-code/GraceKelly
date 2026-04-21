# AUTH-FIX3 full suite

- Full suite: `python -m pytest --tb=short -q` → `2571 passed, 6 skipped, 11 subtests passed`
- Coverage: baseline from `.workflow/state/test-baseline.json` was `96%`; current `python -m coverage report` TOTAL is `97%` (`+1%`)
- Static checks: `python -m ruff check src tests` and `python -m mypy src` are clean
- Artifacts refreshed: both AUTH1/AUTH2 `result.json` files now carry the common R1/R2/R4 numbers, and both AUTH test logs were replaced with the same full-suite summary
- Warnings: coverage emitted `no-ctracer`; this is environment-specific and did not affect exit status
