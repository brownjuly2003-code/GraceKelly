# LOGGER-visibility-fix (retrospective CC-authored)

Date: 2026-04-21

## Files changed
- `src/gracekelly/main.py` (logging setup in `create_app`, ~:317 per CX note)
- `tests/test_app_startup.py` (caplog-based regression tests)

## Result
- `create_app` now applies `settings.log_level` to `logging.getLogger("gracekelly")`.
- Idempotent fallback `StreamHandler(sys.stderr)` attached only if neither gracekelly-logger nor root logger already have handlers — avoids duplication with uvicorn's log config.
- `log_message` schema in `logging_utils.py` unchanged.

## Tests
- New caplog-based regressions in `tests/test_app_startup.py`: (a) `GRACEKELLY_LOG_LEVEL=INFO` — `gracekelly.main` INFO record captured; (b) `GRACEKELLY_LOG_LEVEL=WARNING` — INFO suppressed, WARNING captured.
- Idempotency test: repeated `create_app` calls — no duplicate handlers.

## Live verify
- `python -m uvicorn gracekelly.main:create_app --factory --port 8011` printed: `2026-04-21 10:22:40,798 INFO gracekelly.main: model_catalog.ready ... count=8` within ~3s of startup (per CX note).

## ruff / mypy
- `ruff check src tests` — clean.
- `mypy src` — clean.

## Open questions
- Current formatter is minimal (`%(asctime)s %(levelname)s %(name)s: %(message)s`). If uvicorn is launched with `--log-config <file>`, the handler condition `root has handlers` short-circuits — ok by design.
