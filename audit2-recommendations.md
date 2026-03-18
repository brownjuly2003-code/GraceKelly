# Рекомендации к дальнейшему плану

**Дата:** 2026-03-17
**Контекст:** написано после Gate 4 boundary review (`audit2.md`)

---

## 1. ~~Roadmap рассинхронизирован с реальностью~~ DONE

Выполнено. `phased-roadmap.md`, `architecture.md`, и `implementation-plan.md` обновлены и синхронизированы с фактическим состоянием кода.

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

## 3. ~~Параллельный API track — стратегический хедж~~ DONE

Выполнено. `OpenAICompatibleApiAdapter` реализован в `src/gracekelly/adapters/api/openai_compat.py`. Модель `GPT-5.4 API` добавлена в каталог. Конфигурация через `GRACEKELLY_OPENAI_*` env vars. Покрыто тестами.

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

## 6. ~~Observability перед browser spike~~ DONE

Выполнено. Logging добавлен в:
- `PerplexityBrowserAdapter` — info при старте/завершении execution, warning при ошибках
- `BrowserSessionManager` — info при mark_active/mark_error с provider context
- `OrchestratorService` — warning при event persistence failures

Остаётся расширить на будущий Playwright driver и другие adapter layers.

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

## 10. Порядок ближайших шагов (обновлённый)

Прогресс с момента написания рекомендаций:

```
1. [DONE] Обновить phased-roadmap.md (статусы, фактический прогресс)
2. [NEXT] Провести DOM-разведку Perplexity (docs/perplexity-dom-recon.md)
3. [DONE] Добавить логирование в browser adapter layer
4. [NEXT] Создать selectors.py с извлечёнными из разведки селекторами
5. [NEXT] Реализовать Slice 1 Playwright driver (thin vertical)
6. [NEXT] Тест: один промпт → один ответ через browser
7. [NEXT] Если успех → включить PostgreSQL, переключить default storage
8. [DONE] OpenAI-compatible API adapter (стратегический хедж)
9. [LATER] Slice 2 browser driver (robustness, model verification)
10. [LATER] Minimal circuit breaker для browser adapter
```

Следующий шаг: **DOM-разведка Perplexity** — исследовать UI, селекторы, anti-automation.
