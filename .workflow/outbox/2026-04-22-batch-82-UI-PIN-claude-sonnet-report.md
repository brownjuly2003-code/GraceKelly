# Batch 82 UI-PIN Report

Дата: 2026-04-22
Task: UI-PIN-claude-sonnet
Статус: completed

## Что изменено

- В `static/js/model-menu.js` у items `debate` и `smart` поле `pinned_model` изменено с `"best"` на `"claude-sonnet-4-6"`.
- В `tests/test_playwright_ui_scenarios.py` обновлены целевые ассерты:
  - `test_ui_smart_decomposition_flow`
  - `test_ui_debate_flow`
  - `test_smart_menu_item_does_not_emit_null_model`
- `MODELS_PAYLOAD` уже содержал `claude-sonnet-4-6`, дополнительная правка payload не потребовалась.
- `_resolveItem`, `chat.js` и backend не трогались.

## TDD и проверка

- Сначала были обновлены тестовые ожидания на `claude-sonnet-4-6`.
- Красное состояние подтверждено командой:
  - `pytest -q tests/test_playwright_ui_scenarios.py -k "test_ui_smart_decomposition_flow or test_ui_debate_flow or test_smart_menu_item_does_not_emit_null_model"`
  - падения показали, что UI всё ещё эмитил `model="best"`.
- После точечной правки `model-menu.js` проверки прошли:
  - `python -m pytest tests/test_playwright_ui_scenarios.py -q --tb=short` -> `4 passed`
  - `python -m ruff check .` -> clean
  - `.venv\Scripts\python.exe -m mypy src` -> `Success: no issues found in 104 source files`
  - `python -m pytest --tb=short -q` -> `2587 passed, 6 skipped, 11 subtests passed`

## Итог

UI-контракт для smart/debate теперь пинит известную рабочую модель `claude-sonnet-4-6`, и общий R1 baseline не регрессировал.
