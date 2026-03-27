# GraceKelly Pain Fixes Round 2

> **For agentic workers:** Use superpowers:executing-plans.

**Goal:** Устранить второй слой боли: flaky тест, отсутствие typed AppState, неграсефулное падение при отсутствии Mistral API ключа.

**Architecture:** Три независимых области — тесты, типизация, graceful degradation.

---

## Task 1: Fix flaky HTTP API test (shared memory state)

**Files:**
- Modify: `tests/test_http_api.py`

- [x] Найти setUp в `HttpApiSmokeTests` и убедиться что каждый тест-класс создаёт свой `create_app()` — сейчас OK, но `InMemoryTaskRepository` shared внутри test class
- [x] Перенести `self.client` создание в `setUp` (уже так) но проверить что тест использует `limit=2` и берёт по task_id, не полагаясь на позицию
- [x] Исправить тест: добавлен `__import__("time").sleep(0.002)` между двумя POST для гарантии уникальных `accepted_at` (Windows ms precision)
- [x] Прогнать 5 раз: 5/5 passed

## Task 2: Typed AppState class

**Files:**
- Create: `src/gracekelly/app_state.py`
- Modify: `src/gracekelly/main.py`
- Modify: `pyproject.toml` (убрать per-module ignores для routes)

- [ ] Создать `AppState` dataclass с типами для всех атрибутов app.state
- [ ] Подключить в `create_app()` через `app.state` присвоение
- [ ] Обновить routes для доступа через типизированный state

## Task 3: EmbeddingsClient graceful degradation

**Files:**
- Modify: `src/gracekelly/core/embeddings.py`
- Modify: `src/gracekelly/api/routes/consensus.py`
- Modify: `src/gracekelly/api/routes/smart.py`
- Modify: `src/gracekelly/api/routes/smart_v2.py`

- [ ] EmbeddingsClient.embed() при пустом api_key должен возвращать fallback или выбрасывать понятную ошибку
- [ ] Routes должны возвращать 503 с понятным сообщением если embeddings недоступны

## Task 4: Check and fix .gitignore

**Files:**
- Modify: `.gitignore`

- [ ] Проверить что .env, secrets, __pycache__, dist, *.egg-info в .gitignore
