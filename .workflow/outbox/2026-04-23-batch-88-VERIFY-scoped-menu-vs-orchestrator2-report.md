# VERIFY-scoped-menu-vs-orchestrator2

Статус: success

Вердикт: `PATTERN_EQUIVALENT` — scoped-menu-search в GraceKelly семантически эквивалентен reference pattern из `D:/Perplexity_Orchestrator2/browser/model_selection.py:182-240`; explicit anchor к `[role="menuitemradio"]` с exact child text для закрытия Best-alias не требуется.

Сравнение:
- (a) **Menu scope selector**: Orchestrator2 объединяет `'[role="menu"], [role="listbox"], [data-radix-popper-content-wrapper]'` в один locator; GraceKelly перебирает `('[data-radix-popper-content-wrapper]', '[role="dialog"]', '[role="listbox"]', '[role="menu"]')` по одному. Разница не критична для текущего DOM: live recon показывает, что реальный picker живёт внутри `[data-radix-popper-content-wrapper]`, а добавочный `[role="dialog"]` лишь расширяет совместимость. Теоретическое отличие combined-DOM-order vs selector-order возможно только если одновременно видны несколько разных menu scopes; recon и reference такого не показывают.
- (b) **Primary option locator**: Orchestrator2 делает `menu_scope.locator(f'text={name}').first`; GraceKelly делает тот же descendant text lookup, но по каждому scope отдельно и возвращает `.first` у первого visible match. По Playwright `locator.locator(...)` ищет внутри subtree outer locator, text matching нормализует whitespace, а `locator.first()` возвращает первый match. В recon DOM у Best два descendant text match внутри одного `div[role="menuitemradio"]`: `<span>Best</span>` и описание `Selects the best available model`; exact span идёт раньше по DOM, поэтому `.first` попадает в него, а click поднимается к `menuitemradio` parent. Это ровно тот же рабочий принцип, что и в Orchestrator2.
- (c) **Fallback**: Orchestrator2 агрессивнее — retry/reopen menu и JS `evaluate('(el) => el.click()', target_item)`. GraceKelly проще: `role_filter` (включая `[role="menuitemradio"]`) и затем legacy global `get_by_role/get_by_text`. Это различие относится к hardening fallback-path, а не к primary scoped-menu behavior. Для вопроса Best/nested-text-node material divergence нет.

Регрессии:
- Добавлены 3 tests-only сценария в `tests/test_playwright_driver.py`:
- `test_find_option_in_menu_scope_returns_first_when_multiple_text_matches`
- `test_find_option_in_menu_scope_returns_none_when_all_scopes_empty`
- `test_find_option_in_menu_scope_prefers_earlier_scope_selector`
- Fail-first подтверждён: первый прогон новых тестов упал на test double, который не умел моделировать отдельный `.first`; затем `_FakeLocator` минимально расширен только под эту Playwright-семантику.

Future hardening:
- Retry/reopen menu + JS click из Orchestrator2 стоит держать как `FUTURE_HARDENING`, но это не blocker для закрытия Best-alias Remaining.

Проверки:
- targeted new tests: `3 passed`
- `tests/test_playwright_driver.py`: `36 passed`
- R3: `63 passed / 0 failed / 0 skipped` (`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_playwright_driver.py tests/test_browser_adapter.py`)
- R1: `2614 passed / 0 failed / 6 skipped` (`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`)
- `ruff check src tests` -> clean
- `.venv\Scripts\python.exe -m mypy src` -> `Success: no issues found in 105 source files`

Scope:
- Изменены только `tests/test_playwright_driver.py` и этот report; `src/` не тронут.
