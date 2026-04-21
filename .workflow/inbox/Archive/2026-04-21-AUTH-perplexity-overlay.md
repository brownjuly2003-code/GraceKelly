# AUTH Perplexity overlay — recover or fail-fast on sign-in modal
Date: 2026-04-21
Tier: M (3 tasks — adapter→route→UI; AUTH3 optional)

Context (CX read-first):
- Batch 69 DIAG уже детектит `<div data-testid="login-modal">` через `_body_has_signed_out_marker(page)` и бросает `PermissionError` в playwright_driver на путях catalog inspection / model selection / prompt submission.
- Perplexity adapter (`src/gracekelly/adapters/browser/perplexity.py:180, 256`) переподнимает `PermissionError` вызывающему.
- Orchestrate route НЕ маппит `PermissionError` в HTTP; sync-путь падает как unknown_error 500, async-task уходит в `status=failed` без machine-readable `error.code`.
- Live repro 2026-04-20 на `http://127.0.0.1:8012/`: `POST /api/v1/orchestrate/stream` → `200`; `GET /api/v1/tasks/{task_id}` → `status=failed`, error без кода.
- Decision split зафиксирован в `.workflow/decisions/2026-04-21-diag-orchestrate-500.md` (option B).

Goal батча: PermissionError → end-to-end понятный auth-signal: HTTP 503 `model_auth_required` на sync, structured `error.code` в async task, UI-баннер с Retry.

---

## Task: AUTH1-route-auth-mapping

goal: Смапить `PermissionError` из browser-адаптера в `HTTP 503 model_auth_required` на sync-пути и в structured `task.error` на async-пути.
scope: src/gracekelly/api/routes/orchestrate.py, src/gracekelly/core/orchestrator.py, src/gracekelly/storage/base.py (если `TaskResult.error` расширяется), tests/test_http_api.py, tests/test_orchestrator.py
done_when: [sync `POST /api/v1/orchestrate` при `PermissionError` из адаптера возвращает `HTTPException(503, {"code":"model_auth_required","message":<exc.args[0]>,"trace_id":<uuid>})`; async `POST /api/v1/orchestrate/stream` → `200`, но task завершается с `task.error={"code":"model_auth_required","message":..,"trace_id":..}`; `GET /api/v1/tasks/{task_id}` возвращает этот error в payload; regression-тесты с моком адаптера, бросающим `PermissionError`, покрывают оба пути; текущий 500 unknown_error fallback НЕ расширяется этой веткой; `2566+ passed`, `ruff`+`mypy` clean]
visual_check: false
blocked_by: []

Не менять существующие `PermissionError`-бросалки в `playwright_driver.py` — они корректны после batch 69.

---

## Task: AUTH2-ui-auth-banner

goal: UI рендерит inline-баннер при получении `model_auth_required`, с текстом «Perplexity session expired — open perplexity.ai and sign in, then retry» и кнопкой Retry.
scope: static/js/api.js, static/js/chat.js, static/css/style.css, static/index.html
done_when: [fetch-обёртка в `api.js` распознаёт `{"code":"model_auth_required"}` (и на 503, и в `task.error`) и эмитит event `auth:required` с `{message, trace_id, retry}`; `chat.js` слушает event и рендерит inline-баннер в верхней части main-панели (НЕ modal, НЕ перекрытие чата); баннер: тёмный фон как в PO2, левая оранжевая граница 4px `#f97316`, текст + ссылка `https://www.perplexity.ai` (target=_blank) + кнопка «Retry» справа; Retry повторно триггерит последний запрос; баннер скрывается после успешного retry; Playwright-тест с моком API подтверждает появление/скрытие баннера; no regressions в threads/history/voice/download; скриншоты в `.workflow/outbox/screenshots/auth/` для 1280×800 и 1920×1080]
visual_check: true
blocked_by: [AUTH1-route-auth-mapping]

Одна горизонтальная полоса. Минимал, не редизайн.

---

## Task: AUTH3-persistent-session (optional)

goal: Playwright context переиспользует `storage_state.json`, чтобы пользователь не логинился при каждом рестарте uvicorn.
scope: src/gracekelly/adapters/browser/playwright_driver.py, src/gracekelly/adapters/browser/perplexity.py, src/gracekelly/config.py (или эквивалент), tests/test_playwright_driver.py
done_when: [context создаётся с `storage_state=<path>`, если файл существует и валиден; по graceful shutdown адаптера storage_state пишется обратно; путь настраивается через env `GRACEKELLY_PERPLEXITY_SESSION_PATH`, дефолт `~/.gracekelly/perplexity-session.json`; при повреждённом/expired JSON — fallback на чистый context без краша, WARN в лог; tests покрывают load-existing / save-on-close / fallback-on-invalid; `2566+ passed`, `ruff`+`mypy` clean]
visual_check: false
blocked_by: [AUTH1-route-auth-mapping]

Если CX оценивает, что AUTH1+AUTH2 дают достаточно UX (юзер логинится <2 раз/день) — skip с short report `AUTH3-skipped.md: rationale=low friction`, это допустимо.

---

## HARD RULES

- НЕ менять существующие `PermissionError`-броски в `playwright_driver.py`.
- НЕ запускать реальный Perplexity для тестов — регрессии через моки; live smoke факультативно и только для AUTH3.
- AUTH2 — баннер, не modal.
- Запреты: `git add -A`, `git commit -am`, `reset --hard`, трогать `.claude/`, `.codex/`, `.workflow/outbox/`.
- `R1.fail ≥ 1` после задачи → STOP + `AUTH-regressions-report.md`, не коммитить.

---

## Отчёты

Каждая task → `.workflow/outbox/2026-04-21-AUTH-{task-id}-report.md` + `.result.json` (схема Auto-Accept из `cx-workflow.md`). Коммиты атомарные, формат `auth: {task-id} — {goal}`.
