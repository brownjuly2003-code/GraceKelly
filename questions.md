# Open Questions

Updated: 2026-03-18

## Current blocker

The browser path is no longer blocked on prompt transport.
That part is already working.

The remaining blocker is narrower:
- the dedicated authenticated Perplexity profile can still execute `prompt -> response`
- explicit model selection is still unstable
- the next safe step is a fresh authenticated DOM reconnaissance pass against the current UI

## Questions for the next recon pass

1. Profile state
   - Is `D:\GraceKelly\tmp\browser-recon\perplexity-profile` still authenticated and ready for a live headed recon run?
   - Has the profile stayed stable since the last successful smoke, or did Perplexity ask for re-login / extra verification again?

   **Ответ:** Профиль жив и, скорее всего, аутентифицирован:
   - `Local State` обновлён сегодня (2026-03-18 13:55), значит профиль использовался недавно.
   - `live-smoke-result.json` показывает успешное выполнение промпта (`"submitted_prompt": "Reply with only OK"`, `"response_source": "body_after_prompt"`), что возможно только в authenticated state — неаутентифицированный профиль получил бы `auth_failed`.
   - В `button_debug_snapshot` нет `signed_out_markers` (`Sign in or create an account` и т.д.).
   - Re-login не потребовался — smoke прошёл без ошибок авторизации.

   **Вывод:** профиль готов к recon-сессии. Единственный риск — если Perplexity инвалидирует сессию за время между последним smoke и запуском recon, но это маловероятно в пределах одного дня.

2. Permission to run recon
   - Can a new headed browser recon session be launched now with that dedicated profile?
   - Is it acceptable to save screenshots and JSON/HTML artifacts under `tmp/browser-recon/2026-03-18/`?

   **Ответ:** Это вопрос к тебе (пользователю), не ко мне. Со стороны кода никаких препятствий нет:
   - Профиль существует и активен.
   - `tmp/browser-recon/` уже содержит артефакты от предыдущих recon-сессий — конвенция установлена.
   - Директория `tmp/` в `.gitignore` — артефакты не попадут в коммит.

   Для запуска recon нужно:
   - Убедиться, что никакой другой Chrome-процесс не держит профиль (иначе `exitCode=21`).
   - Запустить headed Playwright с `launch_persistent_context` — headless заблокирует Cloudflare.

   Если даёшь добро — могу написать recon-скрипт, который соберёт все 5 артефактов из списка и сохранит в `tmp/browser-recon/2026-03-18/`.

3. Interactive help during recon
   - If the current Perplexity shell requires a manual click path, can the user briefly help during the capture session?
   - In particular: open the clean composer, click `More`, or expose the place where the model picker now lives, if it is not reachable automatically on the first pass.

   **Ответ:** Тоже вопрос к тебе. Но могу предложить два режима recon-скрипта:

   **(a) Полностью автоматический** — скрипт сам:
   1. Открывает `perplexity.ai` → скриншот + кнопки toolbar
   2. Ищет `button[aria-label="Model"]` → если найдён, кликает, скриншот меню
   3. Если не найден — ищет кнопку «More», кликает, скриншот + повторный поиск model picker
   4. Собирает HTML composer-area
   5. Сохраняет всё в `tmp/browser-recon/2026-03-18/`

   **(b) Полуинтерактивный** — скрипт открывает headed-браузер, делает автоматические шаги, затем ставит паузу (`input("Если нужно — покликай в браузере, затем Enter")`) перед финальным снимком. Это позволит вручную найти пикер, если он за непредсказуемым UI-переходом.

   Рекомендую **(a)** первым прогоном — если он не находит пикер, тогда **(b)** вторым.

## Minimum artifact set needed

- screenshot of the authenticated home composer
- screenshot after opening `More`, if that control exists
- button inventory from the current toolbar shell
- HTML fragment or DOM snapshot for the composer / toolbar area
- screenshot of the model picker, if it becomes visible

## Recon results (2026-03-18)

Recon-скрипт `capture_perplexity_recon.py` уже отработал сегодня. Артефакты в `tmp/browser-recon/2026-03-18/`. Ключевые находки:

### Модель-пикер не пропал — он сменил aria-label

**Старый селектор (мёртв):** `button[aria-label="Model"]`

**Реальная кнопка на home composer:**
```html
<button aria-label="Claude Sonnet 4.6" aria-haspopup="menu" data-state="closed">
  <span>Claude Sonnet 4.6</span>
  <svg>#pplx-icon-chevron-down</svg>
</button>
```

Perplexity теперь ставит **имя текущей выбранной модели** как `aria-label`, а не слово «Model». Поэтому `button[aria-label="Model"]` ничего не находит.

**Надёжный новый селектор:** `button[aria-haspopup="menu"][data-state]` в области composer — кнопка с `aria-haspopup="menu"` и `chevron-down` иконкой. Или точнее: кнопка внутри composer, у которой `aria-haspopup="menu"` и текст совпадает с одной из известных моделей.

### Пикер виден только на home composer

- **Home (`/`):** кнопка модели видна, кликабельна, меню открывается (`recon-01-buttons.json`).
- **Thread view:** пикера нет, только `New Thread`, `More`, `More options` (`recon-02-buttons.json`).
- Это объясняет нестабильность: если `ensure_session()` оставляет страницу в thread view (после предыдущего промпта), пикер не отрисовывается.

### Меню моделей — полный набор

`recon-03-model-menu.json`:
- Best, Sonar, GPT-5.4, Gemini 3.1 Pro, Claude Sonnet 4.6, Thinking, Claude Opus 4.6, Max, Nemotron 3 Super, New

Все текущие browser-модели из `MODEL_SPECS` (кроме Kimi K2.5) присутствуют.

### Response extraction работает

`recon-04-response-candidates.json`: `main div.prose` вернул чистый «OK» — лучший source, `body_after_prompt` содержит шум из sidebar/history.

### Что нужно исправить в коде

1. **Селектор model button** (`selectors.py:9`): заменить `button[aria-label="Model"]` на `button[aria-haspopup="menu"]` внутри composer-контейнера, или искать кнопку по списку известных model names.

2. **Навигация перед model selection** (`playwright_driver.py`): перед `select_model()` убедиться, что страница на home composer (`/`), а не в thread view. Либо всегда делать `page.goto(base_url)` перед выбором модели, либо проверять наличие пикера и только при отсутствии — navigating home.

3. **Kimi K2.5** (`models.py:72`): модель отсутствует в реальном меню Perplexity — пометить как `observed_unavailable` или убрать из browser-каталога.

## Why these questions remain open

- ~~what is still missing is the current real DOM path for model selection in the authenticated UI~~ **RESOLVED** — путь найден: `aria-haspopup="menu"` на home composer
- Осталось: имплементировать новый селектор и навигацию home-before-select в коде

## Resolved since the last question round

- Browser runs no longer fail the whole step when the picker is missing; they continue with `model_selection_verified=false`.
- Browser execution now exposes `model_picker_unavailable=true` when the picker does not render.
- `/api/v1/models` now exposes `observed_unverified` and `last_verified_at`.
- The current implementation state is committed in `7d69ace` (`Degrade browser model selection honestly`).
