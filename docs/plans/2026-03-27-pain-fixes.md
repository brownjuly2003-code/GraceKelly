# GraceKelly Pain Fixes Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Устранить 8 боевых болей проекта: неотслеживаемые файлы, отсутствие линтера, дыры в CI, отсутствие security headers, утечка памяти в rate limiter, hardcoded версия, нет HEALTHCHECK в Docker, нет mypy.

**Architecture:** Каждый таск — изолированный fix без рефакторинга соседнего кода. Никакой новой функциональности. Только устранение боли.

**Tech Stack:** Python 3.11+, FastAPI, pytest, ruff, mypy, GitHub Actions, Docker

---

## Task 1: Commit untracked live test files

**Files:**
- Commit: `tests/test_live_multi_model.py`
- Commit: `tests/test_thinking_recon.py`

- [ ] Проверить что оба файла корректны (пропускают без `GRACEKELLY_BROWSER_LIVE_TEST=true`)
- [ ] `git add tests/test_live_multi_model.py tests/test_thinking_recon.py`
- [ ] `git commit -m "test: add live multi-model and thinking recon tests (gate-protected)"`

---

## Task 2: Add ruff linter + fix all violations

**Files:**
- Modify: `pyproject.toml`
- Modify: `.github/workflows/ci.yml`
- Fix: various `src/` и `tests/` files по результатам ruff

- [ ] Добавить в `pyproject.toml`:

```toml
[tool.ruff]
target-version = "py311"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP"]
ignore = ["E501"]
```

- [ ] Добавить `ruff>=0.4` в `[project.optional-dependencies] dev`
- [ ] Запустить `pip install -e ".[dev]"` (после добавления ruff)
- [ ] Запустить `python -m ruff check src/ tests/ --fix` — авто-фикс
- [ ] Запустить повторно `python -m ruff check src/ tests/` — убедиться что 0 нарушений
- [ ] Добавить в CI (`.github/workflows/ci.yml`) шаг после install:

```yaml
      - name: Lint with ruff
        run: python -m ruff check src/ tests/
```

- [ ] `git add -A && git commit -m "ci: add ruff linter, fix all violations"`

---

## Task 3: Add security headers middleware

**Files:**
- Modify: `src/gracekelly/middleware.py`
- Modify: `src/gracekelly/main.py`

- [ ] Добавить в `middleware.py` функцию `setup_security_headers`:

```python
def setup_security_headers(app: FastAPI) -> None:
    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'none'"
        return response
```

- [ ] В `main.py` импортировать `setup_security_headers` и вызвать в `create_app()` перед `setup_api_key_auth`
- [ ] Запустить `python -m pytest tests/ -q -k "middleware or security or http_api" --tb=short`
- [ ] Написать/дополнить тест что headers присутствуют в ответе `/health`
- [ ] `git add -A && git commit -m "feat: add security headers middleware (CSP, X-Frame-Options, etc)"`

---

## Task 4: Fix RateLimiter — memory leak + multi-process warning

**Files:**
- Modify: `src/gracekelly/middleware.py`

Проблемы:
1. `_buckets` dict никогда не чистит ключи неактивных IP → потенциальная утечка
2. Rate limiter на `threading.Lock` + in-memory → не работает при нескольких workers

- [ ] Добавить в `__init__` переменную `_request_count` для periodic purge
- [ ] В `is_allowed` добавить логику периодического purge (каждые 1000 вызовов) устаревших ключей:

```python
def _purge_stale(self, now: float) -> None:
    cutoff = now - self._window_seconds
    stale = [k for k, ts in self._buckets.items() if not ts or max(ts) < cutoff]
    for k in stale:
        del self._buckets[k]
```

- [ ] В `setup_rate_limiting` добавить log.warning если `requests_per_minute` задан, что rate limiter работает только в одном процессе (in-process only):

```python
logger.warning(
    "Rate limiting is in-process only — "
    "does not work correctly with multiple uvicorn workers or instances"
)
```

- [ ] Запустить `python -m pytest tests/ -q -k "rate" --tb=short`
- [ ] `git add src/gracekelly/middleware.py && git commit -m "fix: patch RateLimiter memory leak, document single-process limitation"`

---

## Task 5: Sync app version from package metadata

**Files:**
- Modify: `src/gracekelly/main.py`

Проблема: `version="0.1.0"` hardcoded в `create_app()`. При изменении версии в `pyproject.toml` FastAPI продолжает показывать старое.

- [ ] В `main.py` добавить импорт:

```python
from importlib.metadata import version as _pkg_version, PackageNotFoundError
```

- [ ] Заменить в `create_app()`:

```python
# было
version="0.1.0",
# стало
version=_get_version(),
```

- [ ] Добавить helper перед `create_app`:

```python
def _get_version() -> str:
    try:
        return _pkg_version("gracekelly")
    except PackageNotFoundError:
        return "0.0.0-dev"
```

- [ ] Запустить `python -c "from gracekelly.main import create_app; app = create_app(); print(app.version)"`
- [ ] `git add src/gracekelly/main.py && git commit -m "fix: read app version from package metadata instead of hardcoded string"`

---

## Task 6: Add HEALTHCHECK to Dockerfile

**Files:**
- Modify: `Dockerfile`

- [ ] Добавить в `Dockerfile` перед `CMD`:

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8011/health')" || exit 1
```

- [ ] Проверить что `docker build` проходит: `docker build -t gracekelly-test . 2>&1 | tail -5`
- [ ] `git add Dockerfile && git commit -m "fix: add HEALTHCHECK to Dockerfile"`

---

## Task 7: Add PostgreSQL service to GitHub Actions CI

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] Добавить `services:` блок с PostgreSQL 16:

```yaml
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: gracekelly
          POSTGRES_PASSWORD: gracekelly
          POSTGRES_DB: gracekelly_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
```

- [ ] Добавить в шаг install: `pip install -e ".[dev,postgres]"`
- [ ] Добавить шаг "Run PostgreSQL tests":

```yaml
      - name: Run PostgreSQL tests
        env:
          GRACEKELLY_POSTGRES_TEST_DSN: postgresql://gracekelly:gracekelly@localhost:5432/gracekelly_test
        run: python -m pytest tests/test_postgres_live.py -q -v
```

- [ ] `git add .github/workflows/ci.yml && git commit -m "ci: add PostgreSQL service, run live DB tests in CI"`

---

## Task 8: Add mypy configuration + fix critical type errors

**Files:**
- Modify: `pyproject.toml`
- Modify: `.github/workflows/ci.yml`
- Fix: критические ошибки типов в `src/`

- [ ] Добавить в `pyproject.toml`:

```toml
[tool.mypy]
python_version = "3.11"
warn_return_any = false
warn_unused_ignores = true
ignore_missing_imports = true
```

- [ ] Добавить `mypy>=1.10` в `[project.optional-dependencies] dev`
- [ ] Запустить `python -m mypy src/gracekelly/ --ignore-missing-imports 2>&1 | head -50`
- [ ] Исправить ошибки по одной (начиная с `error:`, игнорируя `note:`)
- [ ] Добавить в CI шаг после ruff:

```yaml
      - name: Type check with mypy
        run: python -m mypy src/gracekelly/ --ignore-missing-imports
```

- [ ] Запустить полный тест-сьют убедиться ничего не сломано: `python -m pytest -q`
- [ ] `git add -A && git commit -m "ci: add mypy type checking, fix critical type errors"`
