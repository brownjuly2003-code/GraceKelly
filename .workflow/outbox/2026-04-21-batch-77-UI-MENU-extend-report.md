# Batch 77 UI Menu Extend Report

Дата: 2026-04-21
Task: `UI-MENU-extend`
Статус: `completed`

## Итог

- В `static/js/model-menu.js` добавлена группа `Авто` с двумя пользовательскими пунктами: `Дебаты` (`pattern=debate`) и `Умный выбор` (`pattern=smart`).
- Для `debate` и `smart` меню теперь возвращает `model=null`, поэтому `chat.js` отправляет чистые тела `{"topic": ...}` и `{"prompt": ...}` без лишнего поля `model`.
- Группа `Авто` стоит после блока `1 модель`, чтобы при урезанном каталоге не ломать старый дефолтный фоллбек на single-модель.
- Визуальные подтверждения сняты на реальном SPA с мокнутым `/api/v1/*`.

## Изменённые файлы

- `static/js/model-menu.js`

## Visual Evidence

- `.workflow/outbox/screenshots/batch-77/menu-open-1280x800.png`
- `.workflow/outbox/screenshots/batch-77/smart-chat-1280x800.png`
- `.workflow/outbox/screenshots/batch-77/debate-chat-1280x800.png`

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

- По ходу проверки была поймана и сразу устранена регрессия: при каталоге только с одной моделью меню начинало по умолчанию выбирать `debate`. Причина была в порядке групп; после перестановки `Авто` ниже `1 модель` старые auth-banner сценарии снова зелёные.
- `mypy src` остаётся красным на уже существующем `src/gracekelly/middleware.py:120`; этот файл вне scope batch-77, поэтому правка туда не вносилась.
