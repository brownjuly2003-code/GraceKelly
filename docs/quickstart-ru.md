# GraceKelly — Памятка по развёртыванию и использованию

Личная памятка для single-user локального запуска. Всё что нужно знать на одном листе.

## Что это

Локальный оркестратор поверх Perplexity Pro. Один процесс FastAPI на `:8011` отдаёт REST API
и SPA. За API стоит браузерная автоматизация Playwright, которая ходит в `https://www.perplexity.ai`
залогиненной сессией и достаёт ответы любой модели, к которой даёт доступ твоя Pro-подписка
(Claude Sonnet 4.6, GPT-5.4, Gemini Pro, Kimi K2.5, и т. д.).

Платных API-ключей **не нужно** — оплачивается только Perplexity Pro.

## Развёртывание (с нуля, Windows)

1. Установи зависимости:
   ```bash
   cd D:\GraceKelly
   python -m venv .venv
   .venv\Scripts\pip install -e ".[dev,browser]"
   .venv\Scripts\python -m playwright install chromium
   ```

2. Создай `.env` из примера:
   ```bash
   copy .env.example .env
   ```

3. В `.env` обязательно проставь:
   ```
   GRACEKELLY_BROWSER_ENABLED=true
   GRACEKELLY_BROWSER_AUTOMATION_BACKEND=playwright
   GRACEKELLY_BROWSER_PROFILE_DIR=D:\GraceKelly\chrome-profile
   GRACEKELLY_EXECUTION_PROFILE=hybrid
   ```

4. Создай Chrome профиль и залогинь его в Perplexity Pro **руками**:
   ```bash
   .venv\Scripts\gracekelly-create-perplexity-profile
   ```
   Откроется Chromium → войди в Perplexity Pro → закрой окно. Профиль сохранится в
   `chrome-profile/` (gitignored).

5. Запусти сервис:
   ```bash
   .venv\Scripts\uvicorn gracekelly.main:create_app --factory --host 127.0.0.1 --port 8011
   ```

6. Открой UI: <http://127.0.0.1:8011>

## Профили выполнения

Через `GRACEKELLY_EXECUTION_PROFILE`:

| Профиль | Когда использовать |
|---|---|
| `dry-run` | Никаких внешних вызовов. Smoke-тесты, регрессы без затрат квоты. |
| `api-only` | Только direct provider API (если настроены ключи). Без браузера. |
| `hybrid` | **Дефолт для работы.** Браузер первичен, API как fallback. |

Переключить без правки `.env`: `scripts\win-autostart\set_profile.bat hybrid`.

## Базовое использование

### Через UI

<http://127.0.0.1:8011> — выбор модели в дропдауне «Авто», ввод промпта, отправка.
Поддерживаются smart / debate / consensus / compare / batch / orchestrate сценарии.

### Через API

```bash
# Простой запрос
curl -X POST http://127.0.0.1:8011/api/v1/smart \
  -H "Content-Type: application/json" \
  -d '{"prompt":"What is 2+2?","model":"claude-sonnet-4-6"}'

# Оркестрация (Self-RAG / consensus / debate)
curl -X POST http://127.0.0.1:8011/api/v1/orchestrate \
  -H "Content-Type: application/json" \
  -d '{"prompt":"...","models":["claude-sonnet-4-6","gpt-5-4"],"mode":"consensus"}'

# Здоровье
curl http://127.0.0.1:8011/healthz/ready
curl http://127.0.0.1:8011/api/v1/readiness    # подробный статус всех компонентов
```

Полный API в `docs/architecture.md` (раздел Endpoints) — 23 эндпоинта.

### Из Python

```python
import httpx
r = httpx.post(
    "http://127.0.0.1:8011/api/v1/smart",
    json={"prompt": "Привет", "model": "claude-sonnet-4-6"},
    timeout=120,
)
print(r.json()["answer"])
```

## Always-on на Windows

Чтобы сервис стартовал при логоне и переживал краши:
```bash
cd scripts\win-autostart
install_autostart.bat    # запустить от Администратора
```
Логи: `%LOCALAPPDATA%\GraceKelly\uvicorn.log`.
Удалить: `uninstall_autostart.bat` (тоже от Админа).

## Health check всей экосистемы

Проверить что и сам сервис, и три известных клиента (RAG / agent_toolkit / juhub)
работают одной командой:
```bash
.venv\Scripts\python scripts\ecosystem_smoke.py
```
Exit 0 = всё ок (или skipped по причине отсутствия клиента).
Флаги: `--skip-rag`, `--skip-agent-toolkit`, `--skip-juhub`, `--verbose`.

## Что делать когда сервис упал

1. **Проверь живой:** `curl http://127.0.0.1:8011/healthz/live`
   - Не отвечает → uvicorn упал, перезапусти (см. Развёртывание шаг 5)
   - Отвечает 200 → дальше

2. **Проверь готовность:** `curl http://127.0.0.1:8011/api/v1/readiness`
   - `status: degraded` + `browser` компонент в ошибке → Chromium умер, см. ниже
   - `status: ok` → проблема не в GK, ищи в клиенте

3. **Browser упал** (PermissionError / ProviderUnavailable):
   - Закрой все процессы Chromium: `taskkill /F /IM chrome.exe` (если нет других хром-окон)
   - Перезапусти uvicorn — сессия пересоздастся автоматически

4. **Circuit breaker open** (`gracekelly_browser_circuit_breaker_state` метрика = "open"):
   - Подожди 60s — breaker сам перейдёт в half-open и сделает probe-запрос
   - Или принудительно: `curl -X POST http://127.0.0.1:8011/api/v1/circuit-breaker/reset`

5. **Sonar override** (`MODEL_MISMATCH` в логе чаще обычного):
   - Это quota-throttling от Perplexity, не баг GK. Подожди 30-120 минут, либо
     переключись на другую модель, либо перейди в `api-only` профиль (если есть API ключ).

## Известные ограничения

- **Single-user** — Chrome профиль один, параллельные запросы сериализуются через single-worker
  threadpool. Под высокую нагрузку нужен `gracekelly-mixed` routing на стороне клиента
  (Mistral для дешёвых вызовов, GK только для главного ответа).
- **Кириллица в PowerShell pipe** — `echo "тест" | curl` ломает кодировку на PS 5.1.
  Workaround: использовать Windows Terminal или JSON-файл для входных данных.
- **Quota Perplexity Pro** — лимиты на запросы в час. Если упёрлись — Perplexity начинает
  подсовывать Sonar вместо запрошенной модели. GK ловит как `MODEL_MISMATCH` и retry'ит,
  но если пул пуст — зацикливается. См. пункт 5 выше.

## Где что лежит

| Что | Путь |
|---|---|
| Конфиг | `.env` (gitignored) — копируй из `.env.example` |
| Chrome профиль | `chrome-profile/` (gitignored) |
| Логи uvicorn (autostart) | `%LOCALAPPDATA%\GraceKelly\uvicorn.log` |
| Архитектура | `docs/architecture.md` |
| Operator runbook | `docs/operator-runbook.md` (детально все процедуры) |
| Roadmap | `docs/phased-roadmap.md` (15 фаз, все закрыты) |
| Скрипты | `scripts/` (live_smart_smoke, ecosystem_smoke, win-autostart) |

## Чек-лист «всё работает»

```bash
# 1. Liveness
curl -s http://127.0.0.1:8011/healthz/live
# → {"status":"ok"}

# 2. Readiness с профилем
curl -s http://127.0.0.1:8011/api/v1/readiness | grep execution_profile
# → "execution_profile": "hybrid"

# 3. Реальный запрос (cold start первый раз ~30s, потом ~10-30s)
curl -s -X POST http://127.0.0.1:8011/api/v1/smart \
  -H "Content-Type: application/json" \
  -d '{"prompt":"2+2=","model":"claude-sonnet-4-6"}'
# → {"answer":"2 + 2 = 4", ...}
```

Если все три прошли — сервис здоров и готов к работе.
