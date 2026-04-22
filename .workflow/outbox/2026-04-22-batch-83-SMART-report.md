# Batch 83 SMART Report

Дата: 2026-04-22
Task: SMOKE-smart-live
Статус: failure

## Что подтверждено

- Pre-check перед запуском был чистый: процессов `chrome.exe` с `chrome-profile` в `CommandLine` не было, lock-маркеры `SingletonLock/SingletonSocket/SingletonCookie` отсутствовали.
- `uvicorn` поднят на `http://127.0.0.1:8011/` с:
  - `GRACEKELLY_BROWSER_ENABLED=true`
  - `GRACEKELLY_BROWSER_AUTOMATION_BACKEND=playwright`
  - `GRACEKELLY_BROWSER_PROFILE_DIR=D:/GraceKelly/chrome-profile`
  - `GRACEKELLY_EXECUTION_PROFILE=hybrid`
- `GET /api/v1/models` подтвердил живой browser catalog и наличие `claude-sonnet-4-6`.
- Отдельный pre-submit diagnostic без live submit подтвердил, что `window.modelMenu` item `smart` резолвится в `pattern = smart` и `model = claude-sonnet-4-6`; см. `.workflow/outbox/2026-04-22-batch-83-SMART-diag-test-output.log`.
- В live UI перед submit был выбран `Умный выбор`, а в composer находился корректный кириллический prompt; скриншот after фиксирует кириллицу в user bubble.
- Server stderr подтвердил, что submit действительно вошёл в browser-backed smart flow для `model claude-sonnet-4-6`.

## Failure Mode

Live SMART нельзя зачесть как успешный:

- harness не получил HTTP response на `/api/v1/smart` в пределах 180 секунд, поэтому не удалось зафиксировать request body и финальный route payload;
- UI остался в loading state (`...`) на момент остановки harness;
- server-side trace для этого submit показывает три внутренних browser execution в smart flow:
  - `18:52:56+03:00` — старт execution #1, timeout через 60s;
  - `18:54:04+03:00` — старт execution #2, успешный extraction `source=main div.prose length=2730` через ~53s;
  - `18:54:57+03:00` — старт execution #3, timeout через 60s.

Иными словами, selection/pinning и prompt delivery в UI сработали, но acceptance criteria batch-а не выполнены: нет captured `POST /api/v1/smart` response `200`, нет зафиксированного request body без `?`, нет подтверждённого route-level ответа в outbox artefacts.

По hard rules batch-83 после такого SMART live дальнейшие `DEBATE` и `DOCS` не выполняются и retry не допускается.

## Evidence

- Screenshot before: `.workflow/outbox/screenshots/batch-83/smart-before-1280x800.png`
- Screenshot after: `.workflow/outbox/screenshots/batch-83/smart-after-1280x800.png`
- Diagnostic JSON: `.workflow/outbox/2026-04-22-batch-83-SMART-response.json`
- Raw harness output: `.workflow/outbox/2026-04-22-batch-83-SMOKE-smart-live-test-output.log`
- Pre-submit selection diagnostic: `.workflow/outbox/2026-04-22-batch-83-SMART-diag-test-output.log`
- Uvicorn stdout/stderr: `.workflow/outbox/2026-04-22-batch-83-SMART-uvicorn.stdout.log`, `.workflow/outbox/2026-04-22-batch-83-SMART-uvicorn.stderr.log`

## Вывод

- Quota spent: 1 SMART submit.
- Retry не выполнялся.
- После cleanup `uvicorn` остановлен, процессов `chrome.exe` с `chrome-profile` не осталось, lock-файлы в `chrome-profile/` отсутствуют.
