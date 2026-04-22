# Batch 85 ADAPTER Report

Дата: 2026-04-22
Task: ADAPTER-raise-call-timeout
Статус: success

## Root Cause

- Browser adapter брал per-call timeout из `model.timeout_seconds`.
- Для browser-backed smart flow это означало фактический лимит `60s`, приходящий из browser model catalog, даже когда реальная проблема была именно в слишком агрессивном adapter-level budget.
- В config не было отдельного env-переключателя для browser call timeout, поэтому поднять лимит без изменения кода было нельзя.

## Fix

- В `src/gracekelly/config.py` добавлен `browser_call_timeout_seconds` со значением по умолчанию `120` и env `GRACEKELLY_BROWSER_CALL_TIMEOUT_SECONDS`.
- `src/gracekelly/adapters/browser/perplexity.py` теперь использует resolved timeout из config для `submit_prompt(...)` и для timeout failure message, а не `model.timeout_seconds`.
- В `.env.example` добавлена документированная строка для `GRACEKELLY_BROWSER_CALL_TIMEOUT_SECONDS=120`.
- Публичный browser model catalog не менялся: `/api/v1/models` остаётся со старым `timeout_seconds=60`, а route/UI-логика не затронута. Изменение ограничено adapter-level execution budget.

## Validation

- Red-phase до фикса:
  - `tests/test_config.py` падал на отсутствии `browser_call_timeout_seconds` и WARN fallback.
  - `tests/test_browser_adapter.py` показывал, что adapter продолжает слать `timeout_seconds=60`.
- После фикса:
  - `uv run pytest tests/test_config.py -q` -> `11 passed`
  - `uv run pytest tests/test_browser_adapter.py -q` -> `25 passed`
  - `uv run ruff check src tests` -> clean
  - `uv run mypy src` -> `Success: no issues found in 105 source files`
  - Full suite: `2594 passed, 6 skipped, 11 subtests passed`

## Evidence

- Test log: `.workflow/outbox/2026-04-22-batch-85-ADAPTER-raise-call-timeout-test-output.log`
