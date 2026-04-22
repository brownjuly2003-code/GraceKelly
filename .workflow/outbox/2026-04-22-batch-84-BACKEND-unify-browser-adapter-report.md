# Batch 84 BACKEND Report

Дата: 2026-04-22
Task: BACKEND-unify-browser-adapter
Статус: success

## Root Cause

- `smart_v2.py`, `consensus.py` и `compare.py` по-прежнему искали адаптер только через `state.api_adapters.get(model_spec.provider)`.
- Для browser-backed моделей (`resolve_model("best")` -> `adapter_kind="browser"`, `provider="perplexity"`) это сохраняло старое поведение batch-80 era: `400 No API adapter for provider 'perplexity'.` или `no_adapter` в compare.
- `smart.py` и `debate.py` уже имели правильный fallback, но держали его inline, поэтому lookup-логика была раздвоена.

## Fix

- Добавлен общий helper `src/gracekelly/api/routes/_helpers.py::resolve_execution_adapter`.
- `smart.py`, `debate.py`, `smart_v2.py`, `consensus.py`, `compare.py` переведены на единый lookup:
  - dry-run -> `state.dry_run_adapter`
  - browser-backed model -> `state.browser_adapter` + `ExecutionBackend.BROWSER`
  - API model -> `state.api_adapters[...]` + `ExecutionBackend.API`
- `smart_v2` и `consensus` теперь возвращают осмысленный `No browser adapter ...` для browser-backed path без browser adapter.
- `compare` сохраняет прежний shape ответа, но теперь умеет:
  - выполнять browser-backed модель через browser adapter
  - корректно смешивать browser + API модели в одном запросе
  - брать analysis adapter через тот же shared lookup

## Validation

- Новые red-тесты на старом коде дали ожидаемые падения:
  - `smart_v2`: browser-backed `best` -> `400` вместо `200`, detail содержал `No API adapter`
  - `consensus`: browser-backed `best` -> `400` вместо `200`, detail содержал `No API adapter`
  - `compare`: browser-backed `best` -> `no_adapter`, mixed browser+API list давал только 1 success
- Scope route tests после фикса: `81 passed`.
- `ruff check src/ tests/`: clean.
- `mypy src`: вне scope остаётся исторический baseline `src/gracekelly/middleware.py:120` (`no-untyped-call`); новые in-scope mypy-регрессии устранены.
- Full suite после фикса: `2593 passed, 6 skipped, 11 subtests passed`.

## R5

- Kill confirmed red-phase: возврат к pre-helper lookup (`api_adapters.get(...)` без browser fallback) ломает все 6 новых regression tests.
- Existing smart/debate browser tests остаются зелёным guardrail для helper migration этих двух route.
