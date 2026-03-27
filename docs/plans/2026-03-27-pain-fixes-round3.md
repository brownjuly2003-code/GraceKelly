# GraceKelly Pain Fixes Round 3

> **For agentic workers:** Use superpowers:executing-plans.

**Goal:** Третий слой боли: getattr(app.state) паттерны, bare exception handlers, доступ к приватным атрибутам.

**Architecture:** Три независимые области — типизация state во всех routes, structured error handling, API adapter interface.

---

## Task 1: Replace getattr(app.state) with get_app_state() in all routes

**Files:**
- Modify: `src/gracekelly/api/routes/batch.py`
- Modify: `src/gracekelly/api/routes/compare.py`
- Modify: `src/gracekelly/api/routes/consensus.py`
- Modify: `src/gracekelly/api/routes/debate.py`
- Modify: `src/gracekelly/api/routes/analytics.py`
- Modify: `src/gracekelly/api/routes/smart.py`
- Modify: `src/gracekelly/api/routes/smart_v2.py`
- Modify: `src/gracekelly/api/routes/pipeline.py`
- Modify: `src/gracekelly/api/routes/health_detailed.py`
- Modify: `src/gracekelly/api/routes/models.py`
- Modify: `src/gracekelly/app_state.py` (добавить browser_session_manager)

- [x] Все getattr(app.state, ...) заменены на get_app_state(request) в 10 route файлах
- [x] analytics.py: сохранены None-проверки для опциональных атрибутов (task_repository=None в тестах)
- [x] 964 passed

## Task 2: Fix bare Exception handlers — structured 500 errors

**Files:**
- Modify: `src/gracekelly/api/routes/compare.py`
- Modify: `src/gracekelly/api/routes/batch.py`
- Modify: `src/gracekelly/api/routes/consensus.py`
- Modify: `src/gracekelly/api/routes/analytics.py`

- [x] consensus.py: добавлен str(exc) в detail HTTPException и from exc цепочка
- [x] compare/batch: bare handlers намеренны (batch loop), не меняем

## Task 3: Fix private _api_key access in routes

**Files:**
- Modify: `src/gracekelly/api/routes/health_detailed.py`
- Modify: `src/gracekelly/api/routes/pipeline.py`

- [x] Добавлен `has_api_key: bool` property в BaseApiAdapter и EmbeddingsClient
- [x] health_detailed.py и pipeline.py используют has_api_key вместо _api_key
- [x] Тест обновлён: mock использует has_api_key вместо _api_key
