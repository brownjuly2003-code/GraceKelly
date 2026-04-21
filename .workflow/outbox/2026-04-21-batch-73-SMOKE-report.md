# SMOKE-perplexity-live-200-rerun

Дата: 2026-04-21

Артефакты
- `.workflow/outbox/2026-04-21-batch-73-SMOKE-server.log`
- `.workflow/outbox/screenshots/batch-73/before-1280x800.png`
- `.workflow/outbox/screenshots/batch-73/after-1280x800.png`

Результат
- `python -m uvicorn gracekelly.main:create_app --factory --port 8011` поднял сервис на `127.0.0.1:8011`.
- `GET /api/v1/models` -> `200`; `source=perplexity-model-menu`; live browser-catalog непустой.
- Модель для live запроса выбрана динамически из ответа `/api/v1/models`: `claude-sonnet-4-6`.
- `POST /api/v1/orchestrate` с `{"prompt":"Say the word OK","models":["claude-sonnet-4-6"],"dry_run":false}` -> `200`; `task_id=ca1698b3-50d1-448d-bfeb-4eeedd522909`; `duration_ms=9190`; `output_text="OK"`.
- UI smoke через frontend stream тоже вернул `OK`; сохранены `before/after` скриншоты `1280x800`.

Логи и teardown
- В `SMOKE-server.log` есть `GET /api/v1/models 200`, `POST /api/v1/orchestrate 200`, `POST /api/v1/orchestrate/stream 200`.
- `model_catalog.unavailable` в логах не встречается.
- Строка `model_catalog.ready ...` не попала в лог при штатном `python -m uvicorn ...`: текущее runtime-логирование публикует warning и access logs, но не `logger.info` из `gracekelly.main`. Готовность каталога подтверждена живым `GET /api/v1/models` и успешным browser execution.
- Через 10 секунд после shutdown `uvicorn` на `8011` не осталось `chrome.exe` с `--user-data-dir=D:/GraceKelly/chrome-profile`.
