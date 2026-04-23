# batch-95 — CLEANUP-mypy-and-fallback-logging

## Summary

Reconstructed retroactively by CC: CX produced the code changes for batch-95
(pyproject mypy override removal + fallback structured logging) but did not
create outbox reports, commits, or closure artifacts before chaining forward
to batch-96. This report documents the landed work for audit trail.

## Deliverables

- `pyproject.toml`: removed stale `[[tool.mypy.overrides]]` block at former
  lines 106-112 (modules `test_app_startup`, `test_orchestrate_timeout`,
  `test_postgres_live` no longer exist). `mypy --strict` no longer emits
  `unused section(s)` note.
- `src/gracekelly/core/router.py` (`_try_fallback`): added 4 structured log
  events covering skip reasons (`disabled`, `code_not_triggering`,
  `no_fallback_id`, `fallback_model_not_found`), attempt (`info`), success
  (`info`), and failed-fallback (`warning`). No behaviour change — each log
  emit sits inside an existing branch.
- `tests/test_router_fallback.py`: added `test_try_fallback_logs_attempt_and_success`
  plus follow-up log assertions using pytest `caplog` fixture.

## Gate verification

- `ruff check src tests` clean.
- `.venv/Scripts/python.exe -m mypy src --strict` → `Success: no issues found in 106 source files` (no `unused section(s)` note).
- Scoped `pytest tests/test_router_fallback.py tests/test_router.py -q` → 38 passed.
- Full pytest suite scheduled via CC background run (batch-95 code changes are
  pure additive logging + config removal; scoped tests cover new branches).

## Notes

- CX left the worktree dirty at handover, which is why the usual atomic
  commit + outbox flow did not execute. CC is finishing the landing.
