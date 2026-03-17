# Рекомендации к дальнейшему плану

**Дата:** 2026-03-17
**Контекст:** написано после Gate 4 boundary review (`audit2.md`)

---

## 1. Roadmap рассинхронизирован с реальностью

`docs/phased-roadmap.md` устарел. Phase 0 помечена "in progress", хотя фактически выполнены Phase 0, Phase 1, значительные части Phase 2 (browser skeleton), Phase 3 (PostgreSQL), и Phase 5 (operator surfaces). Concurrency limits из Phase 4 тоже уже реализованы.

**Рекомендация:** Перед browser spike обновить roadmap, чтобы он отражал фактический статус. Иначе новый контрибьютор (или будущий ты) не поймёт, что уже сделано. Это 15 минут работы, но экономит часы ориентации.

---

## 2. Browser spike: сначала разведка, потом код

Перед написанием Playwright-драйвера стоит провести **исследовательскую сессию** (30-60 минут), которая ответит на конкретные вопросы:

1. **DOM-структура Perplexity на сегодня.** Какие селекторы нужны для:
   - Выбора модели (dropdown? sidebar? radio buttons?)
   - Ввода промпта (textarea? contenteditable div?)
   - Отправки (кнопка? Ctrl+Enter?)
   - Ожидания ответа (streaming? финальный блок?)
   - Копирования ответа (текстовый блок? markdown?)

2. **Anti-automation защита.** Перед инвестицией в код — проверить:
   - Работает ли headless Chrome или нужен headed?
   - Есть ли CAPTCHA, fingerprinting, rate limits?
   - Хватает ли cookie-based auth или нужен re-login?

3. **Стабильность селекторов.** Perplexity — React SPA. Класс-имена скорее всего генерируются (типа `css-1a2b3c`). Нужно найти устойчивые anchor-точки: `data-testid`, `aria-label`, semantic structure.

**Формат:** Записать результаты разведки в `docs/perplexity-dom-recon.md`. Этот документ — фундамент для выбора архитектуры драйвера.

**Зачем:** Если разведка покажет, что Perplexity активно борется с автоматизацией — лучше узнать это до написания 500 строк кода драйвера, а не после.

---

## 3. Параллельный API track — стратегический хедж

Browser-канал хрупок по своей природе. Один редизайн Perplexity — и драйвер ломается. Юридический risk (ToS) тоже сохраняется.

**Рекомендация:** Параллельно с browser spike добавить один OpenAI-compatible API adapter. Это простой HTTP-клиент, который закрывает:
- OpenAI (GPT-5.4)
- Anthropic (через OpenAI-compatible proxy)
- Together, Groq, Fireworks, DeepSeek
- Любой self-hosted vLLM/Ollama endpoint

Реализация:
- Новый `src/gracekelly/adapters/api/openai_compat.py`
- Тот же `ExecutionAdapter` контракт
- Тот же `_post_json` паттерн, что в `mistral.py`
- Различия: endpoint path (`/v1/chat/completions`), формат ответа (стандартный OpenAI)
- Новые `ModelSpec` записи с `adapter_kind="api"`, `provider="openai"`

Это ~100 строк кода, и это **план Б**, если browser-канал окажется нежизнеспособным.

---

## 4. Тактика browser spike: thin vertical slice

Не пытаться реализовать весь `BrowserAutomationPort` за один подход. Вместо этого — **тонкий вертикальный срез**:

**Slice 1 (минимум):** Один промпт → один ответ
- `ensure_session`: открыть Perplexity в Playwright с existing profile
- `select_model`: кликнуть на нужную модель
- `submit_prompt`: ввести текст, нажать Submit, дождаться ответа
- `auth_status`: проверить, виден ли UI залогиненного пользователя
- `dismiss_popups`: просто Escape (текущий `PopupPolicy.escape_key_retries`)
- `recover_auth`: не реализовывать (return auth_status as-is)

**Slice 2 (если Slice 1 работает):** Robustness
- Правильное ожидание streaming-ответа (не просто `time.sleep`)
- Model verification: сравнить label в UI с запрошенным
- Popup detection: cookie banners, upgrade prompts
- Screenshot на каждом шаге (для debug, в `details`)

**Slice 3 (отложить):** Recovery
- Auth recovery (re-login flow)
- DOM mutation observers для streaming
- Retry на уровне DOM-операций

---

## 5. Selector architecture

Критически важно с самого начала не разбрасывать CSS/XPath строки по коду.

**Рекомендация:** Один файл `adapters/browser/selectors.py`:

```python
@dataclass(frozen=True, slots=True)
class PerplexitySelectors:
    model_dropdown: str = '[data-testid="model-selector"]'
    prompt_input: str = 'textarea[placeholder*="Ask"]'
    submit_button: str = 'button[aria-label="Submit"]'
    response_block: str = '[data-testid="response-text"]'
    auth_indicator: str = '[data-testid="user-avatar"]'
    # ...
```

Когда Perplexity обновит DOM — правка в одном месте. Тесты могут проверять наличие селекторов в конфигурации.

---

## 6. Observability перед browser spike

Сейчас logging есть только в `orchestrator.py` (один `logger.warning` для event failures). Для browser-отладки этого критически мало.

**Рекомендация:** Добавить structured logging (хотя бы `logging.getLogger(__name__)`) в:
- `PerplexityBrowserAdapter.execute()` — начало/конец каждого шага
- `BrowserSessionManager.mark_active()` / `mark_error()`
- Будущий Playwright driver — каждое DOM-взаимодействие

Это не большая работа (10-15 строк logging), но без неё первый browser spike будет отлаживаться вслепую.

---

## 7. Когда переводить PostgreSQL из optional в production

Сейчас PostgreSQL — optional backend. `memory` — default. Это правильно для разработки, но перед production (даже personal) нужна конкретная точка перехода:

**Trigger:** Как только browser execution станет реальным (Slice 1 работает), все задачи начнут накапливать ценные результаты. Потеря данных при перезапуске сервера станет болезненной.

**Рекомендация:** Переключить default storage на `postgres` сразу после первого успешного browser execution. In-memory останется для тестов и dry-run разработки.

**Pre-requisite:** Перед переключением:
- Запустить `gracekelly-validate-postgres` на живом DSN
- Убедиться, что 3 live-postgres теста проходят
- Добавить `connect_timeout` в `.env.example`

---

## 8. Границы Phase 2 vs Phase 4

Текущий roadmap кладёт в Phase 4:
- Account pool manager
- Model fallback policy
- Circuit breakers

Но после browser spike некоторые из этих вещей понадобятся раньше, чем кажется:

- **Circuit breaker на browser adapter** — если Perplexity начнёт блокировать запросы, нужно автоматически переключаться на API path, а не ломать все browser-модели подряд. Это может понадобиться уже через неделю после первого live spike.

- **Account pool** — если будет больше одного Perplexity account (для concurrency), нужен pool. Но это можно отложить: `concurrency_limit=1` пока достаточно.

**Рекомендация:** Выделить minimal circuit breaker (простой "3 failures → disable adapter for 5 minutes") как Phase 2.5, сразу после browser spike стабилизируется. Полный circuit breaker с configurable thresholds — Phase 4.

---

## 9. Test strategy для browser кода

Playwright-драйвер нельзя тестировать в CI без реального Perplexity аккаунта. Нужна чёткая стратегия:

**Уровень 1: Unit tests (CI)** — тестировать через `ScriptedBrowserAutomation`. Это уже работает (8 тестов). Новый драйвер ничего не ломает на этом уровне.

**Уровень 2: Integration tests (local, manual gate)** — запуск Playwright с реальным Perplexity profile. Гейтить через env var (`GRACEKELLY_BROWSER_LIVE_TEST=true`). Не включать в CI.

**Уровень 3: Visual regression (отложить)** — скриншоты + diff. Только если DOM-хрупкость станет реальной проблемой.

---

## 10. Порядок ближайших шагов

Конкретный план на следующие итерации:

```
1. Обновить phased-roadmap.md (статусы, фактический прогресс)
2. Провести DOM-разведку Perplexity (docs/perplexity-dom-recon.md)
3. Добавить логирование в browser adapter layer
4. Создать selectors.py с извлечёнными из разведки селекторами
5. Реализовать Slice 1 Playwright driver (thin vertical)
6. Тест: один промпт → один ответ через browser
7. Если успех → включить PostgreSQL, переключить default storage
8. Параллельно: OpenAI-compatible API adapter (стратегический хедж)
9. Slice 2 browser driver (robustness, model verification)
10. Minimal circuit breaker для browser adapter
```

Каждый шаг — отдельный коммит. Между 6 и 7 — ручной smoke test с реальным Perplexity.
