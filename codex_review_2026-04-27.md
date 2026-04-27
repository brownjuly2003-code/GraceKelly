# Codex review — 2026-04-27

В новой функциональности есть два воспроизводимых интеграционных дефекта:
scheduled recon не видит обычную `.env`-конфигурацию, а telemetry теряет
`request_id` для rate-limited запросов. Это не ломает весь проект, но патч
нельзя считать полностью корректным.

## Findings

### [P2] Загрузите `.env` перед чтением профиля recon

Файл: `D:\GraceKelly\src\gracekelly\tools\recon_weekly.py:160`

Когда профиль браузера задан только в `.env` — это обычный путь для приложения
через `Settings.from_env()` — новый scheduled task запускает
`gracekelly-recon-weekly` без `--profile-dir`, а этот CLI не импортирует config
и не вызывает `load_dotenv()`. В такой установке
`GRACEKELLY_BROWSER_PROFILE_DIR` остаётся `None`, и weekly recon завершается
кодом 2 вместо проверки того же профиля, которым пользуется live app.

### [P2] Сгенерируйте `request_id` для rate-limit 429

Файл: `D:\GraceKelly\src\gracekelly\middleware.py:240`

Если включены Redis rate limiting и usage telemetry, запрос без `X-Request-ID`,
отклонённый лимитом, возвращается из rate-limit middleware до запуска
correlation middleware. Тогда здесь в JSONL пишется `request_id: null`, хотя
контракт telemetry требует header или новый uuid, и 429-запись нельзя связать с
ответом/логами.
