# UI3-chat-js-features report

Date: 2026-04-20

Files changed
- `static/js/chat.js`

Result
- `btn-voice` подключён к Web Speech API. На локальном Chromium в проверке от `2026-04-20` `SpeechRecognition/webkitSpeechRecognition` был доступен, кнопка не disabled.
- `btn-download` экспортирует текущий thread в `.txt`. Проверка через реальный `threadManager` дала имя файла `gracekelly-thread-2026-04-20.txt`.
- JS-управление help overlay (`nav-help` + `help-overlay`) добавлено поверх shell, который уже был сформирован задачами UI1/UI2.
- Добавлены keyboard shortcuts, model-missing warning badge и экспорт/voice state sync без новых зависимостей.

Tests
- `106 passed in 218.61s`
- Playwright UI checks:
- help open: `true`
- help closed after close button: `false` for `:popover-open` state
- export trigger fired: `true`

ruff/mypy
- `ruff check` green
- `mypy` green

Screenshots
- `.workflow/outbox/screenshots/batch-69/gracekelly-1280x800-ui3.png`
- `.workflow/outbox/screenshots/batch-69/gracekelly-1920x1080-ui3.png`

Open questions
- Download smoke проверялся через populated `threadManager`; если нужен отдельный automated regression harness для frontend JS, его в репозитории пока нет.
- `api.js` всё ещё сначала пробует `/api/v1/health`, поэтому в браузерной консоли виден единичный `404` перед fallback на `/health`; этот файл не менялся, т.к. не входил в scope UI3.
