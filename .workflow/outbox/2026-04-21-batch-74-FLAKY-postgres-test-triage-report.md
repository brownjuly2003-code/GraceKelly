# FLAKY-postgres-test-triage (retrospective CC-authored)

Date: 2026-04-21
Closure status: **triaged, fix deferred**.

## Observed symptom
- `python -m pytest --tb=short -q` — fails on `tests/test_import_postgres_tool.py::ImportPostgresToolTests::test_main_rejects_checksum_mismatch`.
- Isolated `pytest tests/test_import_postgres_tool.py` — 31 passed.
- Failure appears only when the whole suite is run, suggesting a cross-test leak (shared global/fixture state).

## Files changed
- None in this pass.

## Hypothesis
- `test_import_postgres_tool` uses the import-tool CLI which mutates filesystem state (tempdir, checksum file). Another earlier test likely leaves a state that partially satisfies a precondition the checksum-mismatch test relies on, so the "mismatch" path never triggers.
- Candidates to inspect: any test that touches `src/gracekelly/tools/import_postgres_tool.py`, global logging handlers (batch-72 LOGGER-visibility added one — worth verifying its idempotence in test collection order), or a monkeypatched `open`.

## Plan (deferred to a focused follow-up)
1. Run `pytest -p no:cacheprovider --collect-only` to dump collection order.
2. Bisect: `pytest -q --lf` and `pytest -q -k "not <suspect_test>"` until the failing test passes.
3. Identify the preceding test that flips state.
4. Fix via teardown/fixture reset in the offending test — NOT via `@pytest.mark.skip`.

## Note
- Existing in this repo pre-batch-74 — not introduced by batch-72/73/74 changes. Verified by the fact that tests pass in isolation and the touched files are independent of import_postgres_tool.
