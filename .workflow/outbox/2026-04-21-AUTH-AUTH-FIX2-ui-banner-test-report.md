# AUTH-FIX2 ui banner test

- Scope: `tests/test_ui_auth_banner.py`
- Result: pytest-Playwright regression coverage now exercises the three required banner flows with `page.route` mocks: sync `503 model_auth_required`, async polled `failure_code="auth_failed"`, and retry leading to a successful response that hides the banner.
- Runtime behavior: the test suite skips cleanly if Playwright or the Chromium browser binary is unavailable.
- Verification: targeted `python -m pytest --tb=short -q tests/test_ui_auth_banner.py`, then full `python -m pytest --tb=short -q`, `python -m coverage run -m pytest --tb=short -q`, `python -m coverage report`, `python -m ruff check src tests`, `python -m mypy src`
