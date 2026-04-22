# Batch 82 SMART Report

Дата: 2026-04-22
Task: SMOKE-smart-live
Статус: failure

## Что подтверждено

- Pre-check был чистый: процессов `chrome.exe` с `chrome-profile` в `CommandLine` не было, lock-маркеры `SingletonLock/SingletonSocket/SingletonCookie` отсутствовали.
- `uvicorn` поднят на `http://127.0.0.1:8011/` с:
  - `GRACEKELLY_BROWSER_ENABLED=true`
  - `GRACEKELLY_BROWSER_AUTOMATION_BACKEND=playwright`
  - `GRACEKELLY_BROWSER_PROFILE_DIR=D:/GraceKelly/chrome-profile`
  - `GRACEKELLY_EXECUTION_PROFILE=hybrid`
- `GET /api/v1/models` подтвердил живой browser catalog и наличие `claude-sonnet-4-6`.
- UI после выбора `Умный выбор` возвращал:
  - `pattern = smart`
  - `model = claude-sonnet-4-6`
- Реальный `POST /api/v1/smart` ушёл с body `{"model":"claude-sonnet-4-6", ...}` и вернул `200`.
- `response.body_json.model_id = "claude-sonnet-4-6"`.
- Auth banner не показывался.

## Failure Mode

Live SMART нельзя засчитать как успешный, потому что сам prompt ушёл в backend в искажённом виде:

- request body содержал `prompt = "?????? ????? EV ? ??????, ??? ? ????? ?? ???????? ????????: ..."`
- это было вызвано локальной PowerShell -> Python кодировкой в automation harness
- из-за искажённого prompt ответ ушёл мимо `done_when`: вместо сравнения Европы / США / Китая вернулся off-target текст про EV-рынок Греции

То есть pin/routing на `claude-sonnet-4-6` сработал, но live smoke как batch acceptance не выполнен, потому что входной текст до модели дошёл некорректно.

## Evidence

- Screenshot before: `.workflow/outbox/screenshots/batch-82/smart-before-1280x800.png`
- Screenshot after: `.workflow/outbox/screenshots/batch-82/smart-after-1280x800.png`
- Diagnostic JSON: `.workflow/outbox/2026-04-22-batch-82-SMART-response.json`
- Uvicorn stdout/stderr: `.workflow/outbox/2026-04-22-batch-82-SMART-uvicorn.stdout.log`, `.workflow/outbox/2026-04-22-batch-82-SMART-uvicorn.stderr.log`

## Вывод

- Quota spent: 1 SMART submit.
- По hard rules batch-82 после проваленного SMART дальнейшие live DEBATE и DOCS closure не выполнялись.
