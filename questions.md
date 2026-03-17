# Open Questions

Updated: 2026-03-17

1. Authenticated browser profile blocker
The thin Playwright backend, selector module, and manual live smoke harness are now in place. A real smoke run against the copied profile at `D:\GraceKelly\tmp\browser-recon\chrome-user-data` reaches prompt entry but is blocked at submit by a `Sign in or create an account` overlay, which now maps cleanly to `auth_failed` and skips the live smoke.

To continue the next plan item (`prompt -> response` proof on the live browser path), GraceKelly now needs a dedicated unlocked and authenticated Perplexity browser profile directory, not a copy of a live Chrome `Default` profile.

### Ответ

**Почему копия Chrome Default не работает:**

Копирование живого профиля Chrome (`Default`) ломает аутентификацию по нескольким причинам:
- Session cookies Perplexity привязаны к encryption key профиля Chrome. При копии ключ теряется или становится невалидным — cookies расшифровываются в мусор.
- Chrome использует `lockfile` и `DevToolsActivePort` — при одновременном запуске оригинала и копии возникают конфликты, а сессии инвалидируются.
- Perplexity может привязывать сессию к fingerprint браузера (user-data-dir path, machine ID) — при смене пути сессия отбрасывается.

**Решение — создать выделенный профиль через Playwright:**

1. **Одноразовый скрипт для ручного логина:**

```python
# scripts/create_perplexity_profile.py
from playwright.sync_api import sync_playwright

PROFILE_DIR = r"D:\GraceKelly\tmp\browser-recon\perplexity-profile"

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        PROFILE_DIR,
        channel="chrome",
        headless=False,
        args=["--disable-blink-features=AutomationControlled"],
    )
    page = context.pages[0] if context.pages else context.new_page()
    page.goto("https://www.perplexity.ai", wait_until="domcontentloaded")
    input(">>> Залогиньтесь в Perplexity вручную, затем нажмите Enter здесь <<<")
    context.close()
```

2. **Запустить скрипт**, залогиниться в Perplexity в открывшемся окне (Google/Apple/email), дождаться появления prompt input, нажать Enter в терминале.

3. **Указать новый профиль в конфиге:**

```
GRACEKELLY_BROWSER_PROFILE_DIR=D:\GraceKelly\tmp\browser-recon\perplexity-profile
```

**Почему это сработает:**
- `launch_persistent_context` Playwright создаёт собственный профиль Chromium с собственным encryption key — cookies сохраняются корректно.
- Профиль не конфликтует с основным Chrome, т.к. это отдельная user-data директория.
- При повторном запуске через тот же `launch_persistent_context` с тем же путём — сессия сохранена, overlay не появляется.

**Что уже готово в коде и не требует изменений:**
- `PlaywrightBrowserAutomation.ensure_session()` (`playwright_driver.py:53`) уже использует `launch_persistent_context` с `state.profile_dir` — подхватит новый путь автоматически.
- `_body_has_signed_out_marker()` (`playwright_driver.py:322`) и `_infer_auth_status()` (`playwright_driver.py:349`) корректно детектят signed-out state через `signed_out_markers` в `selectors.py:24`.
- `PerplexityBrowserAdapter.execute()` (`perplexity.py:47`) уже возвращает `AUTH_FAILED` при неавторизованной сессии — graceful degradation работает.

**Ограничения:**
- Сессия Perplexity имеет TTL (обычно 7–30 дней). Профиль придётся переаутентифицировать периодически. Можно добавить healthcheck-шаг, который проверяет `auth_status` перед первым запросом в серии.
- `AuthRecoveryPolicy.allow_relogin = False` по умолчанию (`policy.py:14`) — автоматический re-login не реализован, что правильно для текущей фазы.

### Реализация

Ответ принят. В проект добавлен helper `gracekelly-create-perplexity-profile`, который создает выделенный persistent Playwright profile по умолчанию в `D:\GraceKelly\tmp\browser-recon\perplexity-profile`.

Следующее внешнее действие для снятия blocker:
- запустить `gracekelly-create-perplexity-profile`
- вручную залогиниться в открывшемся окне
- затем прогнать `pytest -q tests/test_playwright_live.py -rA` с тем же `GRACEKELLY_BROWSER_PROFILE_DIR`
