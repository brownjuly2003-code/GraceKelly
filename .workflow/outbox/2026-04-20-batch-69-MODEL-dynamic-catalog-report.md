# MODEL-dynamic-catalog report

Date: 2026-04-21

Files changed
- `src/gracekelly/core/models.py`
- `src/gracekelly/main.py`
- `src/gracekelly/adapters/browser/perplexity.py`
- `src/gracekelly/api/routes/models.py`
- `src/gracekelly/storage/base.py`
- `src/gracekelly/storage/memory.py`
- `src/gracekelly/storage/postgres.py`
- `src/gracekelly/storage/migrations/0006_add_model_catalog_snapshot.sql`
- `static/js/app.js`
- `static/js/model-menu.js`
- `tests/conftest.py`
- `tests/test_browser_adapter.py`
- `tests/test_models_route.py`
- `tests/test_model_catalog_runtime.py`

## Scope reconcile
- Kept `static/js/app.js` in MODEL because the dynamic catalog work had to fetch `/api/v1/models`, persist `window.modelCatalog`, and surface snapshot freshness/unavailability in the legacy shell that `model-menu.js` now consumes.
- Left `src/gracekelly/adapters/browser/playwright_driver.py` owned by DIAG so the browser-driver overlap stays in one commit while MODEL retains the catalog-facing adapter, storage, and UI wiring changes.

Tests: N passed / coverage
- `python -m pytest --tb=short -q` -> `2566 passed`, `6 skipped`, `11 subtests passed in 440.80s`
- Fresh coverage companion run: `python -m coverage run -m pytest --tb=short -q` + `python -m coverage report` -> `TOTAL 97%`
- Relevant runtime coverage is present in:
  - `tests/test_model_catalog_runtime.py`
  - `tests/test_models_route.py`
  - `tests/test_browser_adapter.py`

ruff/mypy status
- `python -m ruff check src tests` -> `All checks passed!`
- `python -m mypy src` -> `Success: no issues found in 103 source files`

Traceback / screenshots
- No traceback in the final gate runs.
- Model-catalog visual artifacts exist:
  - `.workflow/outbox/screenshots/model-catalog-empty-banner.png`
  - `.workflow/outbox/screenshots/model-catalog-seeded-warning.png`
- Batch-69 screenshot directory exists and contains UI artifacts, including:
  - `.workflow/outbox/screenshots/batch-69/ui-1280x800.png`
  - `.workflow/outbox/screenshots/batch-69/ui-1920x1080.png`

Migration guide
- Runtime catalog source is now the persisted browser snapshot plus static API models; browser entries are no longer hardcoded in `MODEL_SPECS`.
- Existing persisted task names continue to resolve through `resolve_model()` normalization plus browser compatibility aliases:
  - `Best` -> `best`
  - `Sonar` -> `sonar`
  - `Claude Sonnet 4.6`, `Claude 4.6`, `Claude Sonnet` -> `claude-sonnet-4-6`
  - `GPT-5.4`, `GPT 5.4`, `GPT-5` -> `gpt-5-4`
  - `Gemini 3.1 Pro`, `Gemini Pro 3.1`, `Gemini Pro` -> `gemini-3-1-pro`
  - `Kimi K2.5`, `Kimi K2`, `Kimi`, `Kimi K2 Thinking` -> `kimi-k2-5`
  - `Claude Opus 4.6`, `Claude Opus` -> `claude-opus-4-6`
  - `Max` -> `max`
  - `Nemotron 3 Super`, `Nemotron 3` -> `nemotron-3-super`
- API-only models remain stable and are appended to the live browser catalog:
  - `mistral-small` -> `mistral-small`
  - `GPT-5.4 API`, `GPT 5.4 API`, `OpenAI GPT-5.4` -> `gpt-5-4-api`
  - `Claude Sonnet 4.6 API`, `Claude API`, `Anthropic Claude` -> `claude-sonnet-4-6-api`
- Startup behavior:
  - if no snapshot exists, app lifespan performs a Perplexity refresh and persists the result;
  - if the latest snapshot is older than 24h, app lifespan refreshes it;
  - if refresh fails and a stored snapshot exists, `/api/v1/models` serves the last snapshot;
  - if refresh fails and storage is empty, `/api/v1/models` returns `503 model_catalog_unavailable`.

Open questions for CC
- Model-specific screenshots currently live in `.workflow/outbox/screenshots/` root, while the rest of batch-69 visual artifacts are under `.workflow/outbox/screenshots/batch-69/`. Confirm whether that layout is acceptable for closure.
- If storage already contains historical browser labels outside the compatibility alias table above, add them before the next Perplexity rename; otherwise `resolve_model()` will reject those names.
