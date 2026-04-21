# CATALOG-async-lifespan-fix

Дата: 2026-04-21

Файлы
- `src/gracekelly/main.py`
- `tests/test_app_startup.py`

Результат
- Синхронная инициализация каталога переведена в `async def _initialize_model_catalog_async(...)` и теперь вызывается через `await` из `app_lifespan`.
- Sync refresh каталога перенесён в `await asyncio.to_thread(_refresh_model_catalog_labels, _catalog_refresh_adapter(app))`, поэтому Playwright sync API больше не исполняется внутри running event loop на startup.
- Fallback-поведение не менялось: при ошибке refresh сохраняется snapshot-path, а при пустом/недоступном каталоге остаются `clear_browser_catalog()` и WARN-лог.

Регрессия
- Добавлен `AppStartupAsyncTests.test_startup_refreshes_catalog_when_sync_refresh_requires_no_running_loop`.
- Тест поднимает ASGI через `httpx.AsyncClient` + `ASGITransport` внутри `app.router.lifespan_context(app)` и подставляет sync adapter, который падает, если его вызвать внутри event loop.
- До фикса тест воспроизводил регрессию как `503` на `/api/v1/models`; после фикса проходит с `200` и непустым runtime catalog.

Проверка
- `pytest -q tests/test_app_startup.py tests/test_model_catalog_runtime.py` -> `7 passed`
- `ruff check src tests` -> `All checks passed!`
- `mypy src` -> `Success: no issues found in 104 source files`
- `pytest -q` -> `2572 passed`, `6 skipped`, `11 subtests passed`
