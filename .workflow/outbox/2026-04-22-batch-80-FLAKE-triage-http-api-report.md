# Batch 80 FLAKE Report

Дата: 2026-04-22
Task: FLAKE-triage-http-api
Статус: success

## Root Cause

- Проблема оказалась не cross-test leak, а timing-dependent ожидание внутри самого `tests/test_http_api.py::HttpApiSmokeTests::test_list_tasks_exposes_winning_model_and_short_circuit_summary`.
- Старый вариант теста использовал реальный `mistral` adapter без API key. Этот шаг иногда успевал завершиться с `provider_unavailable` раньше browser-win, поэтому `cancelled_step_count` прыгал между `0` и `1`.

## Fix

- Тест получил локальный `SlowCancellableAdapter`, который удерживает второй шаг живым до получения `request.cancellation`.
- После этого проверка реально валидирует short-circuit path, а не случайное планирование потоков.

## Validation

- Изолированно проблемный тест прогнан 20 раз подряд: `0` падений.
- Scope run по изменённым test files: `88 passed`.
- Full suite после фикса:
  - run 1: `2587 passed, 6 skipped, 11 subtests passed`
  - run 2: `2587 passed, 6 skipped, 11 subtests passed`
  - run 3: `2587 passed, 6 skipped, 11 subtests passed`
- Coverage run: `97%`.
- `ruff` и `mypy src` зелёные.

## R5

- Kill confirmed: временное отключение `cancel_on_quorum` в самом тесте ломает ожидание (`cancelled_step_count: 0 != 1`).
