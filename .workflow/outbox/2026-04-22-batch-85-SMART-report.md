# Batch 85 SMART Report

Дата: 2026-04-22
Task: SMOKE-smart-live-rerun
Статус: failure

## Что подтверждено

- Pre-check перед submit был чистый: процессов `chrome.exe` с `chrome-profile` не было, lock-файлы в `chrome-profile/` отсутствовали, `8011` был свободен.
- `uvicorn` поднят на `http://127.0.0.1:8011/` с:
  - `GRACEKELLY_BROWSER_ENABLED=true`
  - `GRACEKELLY_BROWSER_AUTOMATION_BACKEND=playwright`
  - `GRACEKELLY_BROWSER_PROFILE_DIR=D:/GraceKelly/chrome-profile`
  - `GRACEKELLY_EXECUTION_PROFILE=hybrid`
  - `GRACEKELLY_BROWSER_CALL_TIMEOUT_SECONDS=120`
- Harness использовал ASCII fallback prompt и передал его через `page.fill()`, без PowerShell pipeline-encoding.
- UI выбрал `Умный выбор`, отправил `POST /api/v1/smart` и получил route-level `200`.
- Server stderr подтвердил, что первый внутренний browser call реально пошёл с `timeout=120s`, а не со старым `60s`.

## Failure Mode

Smoke нельзя зачесть как успешный:

- route-level HTTP ответ был `200`, но итоговый payload не содержал осмысленного EV-обзора;
- `response.body_json.answer` оказался равен `[auth_failed] Unable to determine browser login state from the current page.`;
- длина ответа составила только `76` символов, `was_decomposed=false`, признаков ответа по теме EV/Europe/China/adoption/subsidies нет;
- server-side trace показал такой smart flow:
  - `21:11:49+03:00` — execution #1 submit с `timeout=120s`;
  - `21:11:50+03:00` — execution #1 успешно извлёк ответ (`source=body_after_prompt length=1326`);
  - `21:11:50+03:00` — execution #2 завершился `auth_failed`;
  - `21:11:50+03:00` — execution #3 завершился `auth_failed`.

Иными словами, timeout regression действительно снят, но acceptance batch-а всё равно не выполнен: smart auto-decomposition не завершился end-to-end осмысленным итогом, а деградировал в `[auth_failed]` payload.

По hard rule batch-85 после такого live SMART retry не допускается, а DOCS-task блокируется.

## Evidence

- Screenshot before: `.workflow/outbox/screenshots/batch-85/smart-before-1280x800.png`
- Screenshot after: `.workflow/outbox/screenshots/batch-85/smart-after-1280x800.png`
- Diagnostic JSON: `.workflow/outbox/2026-04-22-batch-85-SMART-response.json`
- Raw harness output: `.workflow/outbox/2026-04-22-batch-85-SMOKE-smart-live-test-output.log`
- Uvicorn stdout/stderr: `.workflow/outbox/2026-04-22-batch-85-SMART-uvicorn.stdout.log`, `.workflow/outbox/2026-04-22-batch-85-SMART-uvicorn.stderr.log`

## Вывод

- Quota spent: 1 SMART submit.
- Retry не выполнялся.
- После cleanup `uvicorn` остановлен, процессов `chrome.exe` с `chrome-profile` не осталось, lock-файлы в `chrome-profile/` отсутствуют.
