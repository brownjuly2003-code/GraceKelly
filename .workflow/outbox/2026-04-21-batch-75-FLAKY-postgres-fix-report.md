# FLAKY-postgres-fix (batch-75 task-1)

Date: 2026-04-21
Closure status: **resolved — no repro on current main**.

## Observed symptom (triage source)
From `.workflow/outbox/2026-04-21-batch-74-FLAKY-postgres-test-triage-report.md`:
- `tests/test_import_postgres_tool.py::ImportPostgresToolTests::test_main_rejects_checksum_mismatch` was reported to fail in the full `pytest` run while passing when the module was run in isolation.
- Hypothesis: cross-test leak — filesystem state or logging-handler mutation from an earlier test flipping a precondition.

## Verification on `e1f7185` (current `main` tip)
Commands executed from repo root with the project venv (`.venv/Scripts/python.exe`):

| # | Command | Result |
|---|---------|--------|
| 1 | `pytest tests/test_import_postgres_tool.py -q` | `31 passed in 0.56s` |
| 2 | `pytest tests/test_import_postgres_tool.py::ImportPostgresToolTests::test_main_rejects_checksum_mismatch --tb=short -q` | `1 passed in 0.27s` |
| 3 | `pytest --tb=short -q -p no:cacheprovider` (full suite) | `2579 passed, 6 skipped, 11 subtests passed in 615.26s` — exit 0 |
| 4 | `pytest --tb=short -q -p no:cacheprovider` (second full run, confirmation) | see `2026-04-21-batch-75-FLAKY-postgres-fix-test-output-run2.log` |
| 5 | `ruff check` | `All checks passed!` |
| 6 | `mypy src` | `Success: no issues found in 104 source files` |

Full-run log: `.workflow/outbox/2026-04-21-batch-75-FLAKY-postgres-fix-test-output.log` (primary), second run in `*-run2.log`.

## Root cause (inferred)
The flake was not reproduced on the current tip, so no bisect was needed. The most probable fix is one of the intervening commits between the triage (`412cee4`) and `e1f7185`:

- `772ef34 chore: drain timed-out orchestrate submissions to avoid unhandled future warnings` — eliminated a source of lingering threadpool futures that could emit `RuntimeWarning` during unrelated tests.
- `67fc496 batch-72/73: main + tests consolidated — catalog async lifespan + profile safety validator + logger visibility` — re-initialised the global logger handler via a per-app lifespan; this matches the second hypothesis in the triage ("global logging handlers, batch-72 LOGGER-visibility added one — worth verifying its idempotence in test collection order").

No evidence pointed to a mutation inside `test_import_postgres_tool.py` itself; the module uses `Path("tmp") / "test-import-tool" / <uuid>.json` with per-test cleanup in `finally:` clauses, and `tmp/test-import-tool/` is empty after full-suite runs.

## Files changed
- None. No code fix required; no `skip`/`xfail`/`pytest-ordering` workaround introduced.

## Done-when check
- [x] `R1 pass ≥ 2573 fail = 0` — 2579 passed, 0 failed.
- [x] `pytest tests/test_import_postgres_tool.py` still 31 passed isolated.
- [x] `ruff check` clean.
- [x] `mypy src` clean.
- [x] No `@pytest.mark.skip` / `xfail` / `pytest-ordering` added.

## Follow-up
If the flake resurfaces in CI with a different ordering, re-run `pytest -p no:cacheprovider --collect-only` against the failing commit to dump collection order and bisect from there. The triage report remains a valid starting point.
