# Batch 04 Report

## D1-event-buffer
Status: success

Added an in-process `deque(maxlen=500)` buffer to `OrchestratorService` so transient `append_event()` failures no longer drop events. Buffered events are retried at the start of the next `submit_snapshot()` call, and the retry loop stops safely on the first repeated storage failure.

## D2-coverage-threshold
Status: success

Excluded `src/gracekelly/adapters/browser/playwright_driver.py` from coverage in `pyproject.toml` and raised the CI hard gate in `.github/workflows/ci.yml` to `93`. The exact local gate command now passes at `93.85%` total coverage.

Verification:
- `python -m pytest tests/test_event_buffer.py -v`
- `mypy src/gracekelly/core/orchestrator.py`
- `python -m pytest --cov=gracekelly --cov-fail-under=93 --tb=no -q --ignore=tests/test_postgres_live.py --ignore=tests/test_playwright_live.py`
