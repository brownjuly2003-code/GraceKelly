# Batch 80 BACKEND Report

Дата: 2026-04-22
Task: BACKEND-smart-debate-browser-support
Статус: success

## Root Cause

- `src/gracekelly/api/routes/smart.py` и `src/gracekelly/api/routes/debate.py` брали адаптер только из `state.api_adapters`.
- Для browser-backed моделей `resolve_model("best")` уже возвращает `adapter_kind="browser"` и `provider="perplexity"`, поэтому оба route падали с `400 No API adapter for provider 'perplexity'.`

## Fix

- В обоих route добавлено ветвление по `model_spec.adapter_kind`.
- Browser-backed path теперь использует `state.browser_adapter`.
- `ExecutionStep.backend` и `ExecutionPlan.adapter_hint` для browser-backed path переключены на `BROWSER`.
- API path не регрессировал: для `mistral-small` без API adapter всё ещё возвращается осмысленный `400`.

## Validation

- Новые/обновлённые route tests подтверждают:
  - `smart` с `model="best"` идёт через browser adapter и возвращает `200`.
  - `debate` с `model="best"` идёт через browser adapter и возвращает `200`.
  - browser-backed path без `browser_adapter` возвращает `400`.
  - API path без `api_adapters["mistral"]` всё ещё возвращает `400`.
- Scope run: `32 passed`.
- `ruff check src/ tests/`: clean.
- `mypy src`: clean (`104 source files`).
- Full suite после фикса: `2587 passed, 6 skipped, 11 subtests passed`.

## R5

- Kill confirmed для `test_smart_browser_model_uses_browser_adapter`: временный возврат к старому `api_adapters.get(...)` ломает тест (`200 != 400`).
- Kill confirmed для `test_debate_browser_model_uses_browser_adapter`: временный возврат к старому `api_adapters.get(...)` ломает тест (`200 != 400`).
