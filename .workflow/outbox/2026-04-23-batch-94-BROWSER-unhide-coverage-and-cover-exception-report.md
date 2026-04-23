# BROWSER-unhide-coverage-and-cover-exception

Status: success

What changed:
- Removed the coverage omit that hid `src/gracekelly/adapters/browser/playwright_driver.py` from the default report.
- Added `test_find_option_in_menu_scope_skips_selector_on_locator_exception` to cover the `_find_option_in_menu_scope` exception branch and verify fallback to the next menu scope selector.
- Left `src/gracekelly/adapters/browser/playwright_driver.py` unchanged.

Verification:
- `.\.venv\Scripts\python.exe -m pytest tests/test_playwright_driver.py -k "test_find_option_in_menu_scope_skips_selector_on_locator_exception"` -> `1 passed`.
- `.\.venv\Scripts\python.exe -m pytest tests/test_playwright_driver.py --cov=gracekelly.adapters.browser.playwright_driver --cov-report term-missing` -> `37 passed`; targeted coverage still reports the file and no longer lists lines `709-716` as missing.
- `.\.venv\Scripts\python.exe -m pytest --cov --cov-report= -q` -> `2651 passed, 6 skipped, 11 subtests passed in 916.45s`.
- `.\.venv\Scripts\python.exe -m coverage report` -> `src/gracekelly/adapters/browser/playwright_driver.py` appears at `76%`; `TOTAL` is `96%`.
- `.\.venv\Scripts\ruff.exe check src tests` -> clean.
- `.\.venv\Scripts\python.exe -m mypy src --strict` -> clean.

Coverage notes:
- Overall coverage moved from the `97%` baseline to `96%` after unhiding `playwright_driver.py` and stays within the allowed 2pp drop.
- `src/gracekelly/adapters/browser/playwright_driver.py` is now visible in the default coverage report at `76%`.
- `_find_option_in_menu_scope` line range `709-716` is fully covered; exception lines `712-713` are hit.

Scope:
- `pyproject.toml`
- `tests/test_playwright_driver.py`
