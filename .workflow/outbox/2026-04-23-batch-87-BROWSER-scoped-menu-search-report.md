# BROWSER-scoped-menu-search

Статус: success

Что сделано:
- `PerplexitySelectors.model_menu_candidates` расширен до 4 вариантов добавлением `'[role="menu"]'` в конец кортежа.
- В `PlaywrightBrowserAutomation.select_model` lookup опции теперь идёт в порядке `menu_scope -> role_filter -> global_fallback`.
- Добавлены приватные helper'ы `_find_option_in_menu_scope()` и `_find_option_via_role_filter()`.
- В `BrowserModelSelection.details` добавлен `option_lookup_source` со значениями `menu_scope`, `role_filter`, `global_fallback`, `not_found`.
- Глобальный broad `button:has-text(...)` оставлен только в legacy fallback; role-filter не использует `button`, чтобы не цеплять off-menu UI.
- Добавлены 4 tests-first сценария под новые lookup-paths; test doubles для locator-chain сузлены до реалистичного поведения.

Проверки:
- R1: `2611 passed / 0 failed / 6 skipped` (`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`)
- R3: `60 passed / 0 failed / 0 skipped` (`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_playwright_driver.py tests/test_browser_adapter.py -q`)
- `python -m ruff check src tests` -> clean
- `.venv\Scripts\python.exe -m mypy src` -> `Success: no issues found in 105 source files`

Scope:
- Изменены только `src/gracekelly/adapters/browser/selectors.py`, `src/gracekelly/adapters/browser/playwright_driver.py`, `tests/test_playwright_driver.py`
