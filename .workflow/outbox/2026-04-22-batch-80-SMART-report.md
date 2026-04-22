# Batch 80 SMART Report

Дата: 2026-04-22
Task: SMOKE-smart-live
Статус: failure

## Что подтверждено

- `uvicorn` поднят на `http://127.0.0.1:8011/` с `GRACEKELLY_BROWSER_ENABLED=true`, `GRACEKELLY_BROWSER_AUTOMATION_BACKEND=playwright`, `GRACEKELLY_BROWSER_PROFILE_DIR=D:/GraceKelly/chrome-profile`, `GRACEKELLY_EXECUTION_PROFILE=hybrid`.
- `GET /api/v1/models` подтвердил, что browser catalog жив и `best` доступен.
- Перед submit UI selection принудительно зафиксирован как:
  - `id = smart`
  - `pattern = smart`
  - `model = best`
- Живой `POST /api/v1/smart` теперь действительно уходит в нужный route и возвращает `200`.

## Failure Mode

- Response body:
  - `model_id = "best"`
  - `answer = "[provider_unavailable] Browser profile directory 'D:/GraceKelly/chrome-profile' is already in use by another Chrome process."`
- `auth-banner` не показан.
- В server log после этого browser adapter трижды получает тот же `provider_unavailable` и открывает circuit breaker.

## Вывод

Frontend contract и backend route selection починены: live SMART дошёл до `/api/v1/smart` c `model="best"`.
Новый blocker batch-80 находится в browser session/profile handling: live execution не может повторно открыть `D:/GraceKelly/chrome-profile`.

По зависимостям batch-а `SMOKE-debate-live` не выполнялся, `DOCS-phase-17-refresh` пропущен.
