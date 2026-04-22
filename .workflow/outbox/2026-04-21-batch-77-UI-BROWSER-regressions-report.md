# Batch 77 UI Browser Regressions Report

Дата: 2026-04-21
Task: `UI-BROWSER-regressions`
Статус: `completed`

## Итог

- Добавлен новый файл `tests/test_playwright_ui_scenarios.py`.
- Добавлена фикстура `tests/fixtures/sample-attachment.txt` для upload-сценария.
- Три новых Playwright-теста драйвят реальный SPA на `/` и мокают только `/api/v1/*` через `page.route()`:
  - `test_ui_upload_flow_drives_orchestrate_upload`
  - `test_ui_smart_decomposition_flow`
  - `test_ui_debate_flow`
- Тесты проверяют и transport-level контракт, и UI-рендер:
  - upload шлёт `multipart/form-data` на `/api/v1/orchestrate/upload` и рендерит `output_text`
  - smart шлёт `{"prompt": ...}` на `/api/v1/smart` и рендерит `answer`
  - debate шлёт `{"topic": ...}` на `/api/v1/debate` и рендерит `improved_response`
- Во время полного прогона эти тесты выявили регрессию default selection в auth-banner сценариях; причина была в `model-menu`, фикс записан в задаче `UI-MENU-extend`, после чего полный suite снова зелёный.

## Изменённые файлы

- `tests/test_playwright_ui_scenarios.py`
- `tests/fixtures/sample-attachment.txt`

## Verification

```text
pytest tests/test_playwright_ui_scenarios.py -q
3 passed in 6.81s

pytest tests/test_ui_auth_banner.py tests/test_playwright_ui_scenarios.py -q
6 passed in 19.96s

pytest -q
2582 passed, 6 skipped, 11 subtests passed in 648.14s

ruff check .
All checks passed!

mypy src
src/gracekelly/middleware.py:120: error: Call to untyped function "from_url" in typed context  [no-untyped-call]
Found 1 error in 1 file (checked 104 source files)
```

## Notes

- Live Perplexity в новых тестах не вызывается: весь API-трафик перехватывается `page.route("**/api/v1/**", ...)`.
- Для выбора menu item в тестах используется реальный `model-trigger`; клик по пунктам выполняется через DOM `closest('.model-item').click()`, потому что стандартный pointer-click для popup label у этого SPA нестабилен в headless Playwright.
- `mypy src` остаётся красным на уже существующем `src/gracekelly/middleware.py:120`; файл вне scope batch-77.
