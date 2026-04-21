# AUTH-FIX1 consolidate codes

- Scope: `src/gracekelly/api/error_codes.py`, `src/gracekelly/api/routes/orchestrate.py`, `src/gracekelly/core/orchestrator.py`, `static/js/api.js`, `static/js/chat.js`, `.workflow/docs/auth-error-codes.md`
- Result: auth nomenclature is explicit instead of scattered magic strings. Python uses shared constants for sync HTTP `model_auth_required` and persisted async `auth_failed`; frontend reads the async code from `window.api.authTaskFailureCode`; mapping is documented in `.workflow/docs/auth-error-codes.md`.
- Constraints held: behavior unchanged, no API/schema/data migration, `FailureCode.AUTH_FAILED` was not renamed.
- Verification: targeted `python -m pytest --tb=short -q tests/test_http_api.py tests/test_orchestrator.py tests/test_ui_auth_banner.py`, then full `python -m pytest --tb=short -q`, `python -m coverage run -m pytest --tb=short -q`, `python -m coverage report`, `python -m ruff check src tests`, `python -m mypy src`
