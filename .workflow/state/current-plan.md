# GraceKelly — 9.8/10 Production Readiness Plan

> **For agentic workers:** Process tasks from .workflow/inbox/ per AGENTS.md.

**Goal:** Bring GraceKelly from ~8.2/10 to 9.8/10 across all quality dimensions.

**Architecture:** Three phases targeting the biggest scoring gaps: (A) observability/DX, (B) correctness/reliability, (C) performance/advanced quality. Each phase produces independently deployable improvements.

**Tech Stack:** Python 3.11+, FastAPI, httpx, asyncio, hypothesis (property tests), pytest-cov

---

## Status — COMPLETE 2026-03-29
- [x] Phase A: Observability & DX — README, correlation IDs, RFC 7807 errors
- [x] Phase B: Correctness & Reliability — strict auth, k8s probes, config validation, event buffering
- [x] Phase C: Performance & Advanced Quality — property tests, coverage gaps, Docker multi-stage, coverage 93.85%

**Final score: ~9.7/10** (2355 tests, 93.85% coverage, mypy strict 0 errors)
Deferred: async httpx.AsyncClient (C1) — low risk, high complexity

---

## Phase A: Observability & DX

### Task A1: Coverage report + raise threshold (cx-task)
**Files:**
- Modify: `pyproject.toml` — raise cov-fail-under to 80
- Modify: `.github/workflows/ci.yml` — add --cov-report=term-missing
- Create: `tests/test_coverage_baseline.py` — placeholder noting current gaps
- Run: `python -m pytest --cov=gracekelly --cov-report=term-missing -q`

**Type:** cx-task (batch A)
**Done when:** CI passes with ≥80% coverage threshold

---

### Task A2: README.md with quickstart (cx-task)
**Files:**
- Create: `README.md`

**Content sections:**
1. Title + 1-sentence description
2. Quick Start (Docker: `docker-compose up`, then `curl /health`)
3. Configuration (link to .env.example, key env vars table: 8 most important)
4. API Overview (table of 15 endpoints, one-liner each)
5. Development Setup (`pip install -e ".[dev]"`, `pytest`, `mypy`, `ruff`)
6. Architecture (2 sentences)

**Type:** cx-task (batch A)
**Done when:** `README.md` exists, renders cleanly, covers all 4 sections.

---

### Task A3: Request correlation IDs (cx-task)
**Files:**
- Modify: `src/gracekelly/middleware.py` — add `setup_correlation_id(app)` middleware
- Modify: `src/gracekelly/main.py` — call setup_correlation_id in create_app
- Create: `tests/test_correlation_id.py`

**Implementation:**
```python
import uuid

def setup_correlation_id(app: FastAPI) -> None:
    @app.middleware("http")
    async def correlation_id_middleware(request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response
```

**Tests:**
- Server generates X-Request-ID when absent
- Server echoes back client X-Request-ID
- X-Request-ID is valid UUID when auto-generated

**Type:** cx-task (batch A)
**Done when:** 3 tests pass, header present in every response.

---

### Task A4: Standardize error responses — RFC 7807 Problem Details (cc-only → then cx-task)
**Design (cc-only, done inline):**
- All 4xx/5xx responses use `{"type": "...", "title": "...", "status": N, "detail": "..."}`
- FastAPI exception handlers in `main.py`
- 422 Validation errors → standardized format

**Files:**
- Modify: `src/gracekelly/main.py` — add exception_handler for RequestValidationError, HTTPException
- Create: `tests/test_error_responses.py`

**Type:** cc-only for design, cx-task (batch A) for implementation
**Done when:** 422, 400, 404 all return RFC 7807 format, tests pass.

---

## Phase B: Correctness & Reliability

### Task B1: Rate limiting strict enforcement (cx-task)
**Files:**
- Modify: `src/gracekelly/config.py` — add `rate_limit_strict: bool = False` from env `GRACEKELLY_RATE_LIMIT_STRICT`
- Modify: `src/gracekelly/middleware.py` — if strict and no API key configured, return 503 with clear message
- Modify: `src/gracekelly/main.py` — pass strict flag to setup_rate_limiting
- Create: `tests/test_rate_limit_strict.py`

**Type:** cx-task (batch B)
**Done when:** `GRACEKELLY_RATE_LIMIT_STRICT=true` + missing API key → 503 on protected endpoints.

---

### Task B2: Kubernetes liveness + readiness probes (cx-task)
**Files:**
- Modify: `src/gracekelly/api/routes/health.py` — add GET /healthz/live (always 200) and GET /healthz/ready (checks storage)
- Modify: `src/gracekelly/main.py` — include health router already includes these
- Create: `tests/test_k8s_probes.py`

**Implementation:**
```python
@router.get("/healthz/live")
async def liveness() -> dict[str, str]:
    return {"status": "ok"}

@router.get("/healthz/ready")
async def readiness(request: Request) -> dict[str, object]:
    state = get_app_state(request)
    if state.task_repository is None:
        raise HTTPException(status_code=503, detail="Storage unavailable")
    return {"status": "ok"}
```

**Type:** cx-task (batch B)
**Done when:** 5 tests pass: /healthz/live always 200, /healthz/ready 200 with storage, 503 without.

---

### Task B3: Config validation on startup (cx-task)
**Files:**
- Modify: `src/gracekelly/config.py` — add `validate()` method checking contradictions
- Modify: `src/gracekelly/main.py` — call settings.validate() early in create_app
- Create: `tests/test_config_validation.py`

**Validations:**
- `storage_backend == "postgres"` but `postgres_dsn is None` → ValueError
- `browser_enabled` but no `browser_profile_dir` → warning (not error)
- `orchestrate_timeout_seconds` < 1.0 and not None → ValueError

**Type:** cx-task (batch B)
**Done when:** 5 tests for validation scenarios pass; `create_app(invalid_settings)` raises ValueError with clear message.

---

### Task B4: Event buffering for storage failures (cx-task)
**Files:**
- Modify: `src/gracekelly/core/orchestrator.py` — add `_event_buffer: deque[TaskEventRecord]` (maxlen=500) + `_flush_buffer()` called at next submit
- Create: `tests/test_event_buffer.py`

**Implementation sketch:**
```python
from collections import deque

# In __init__:
self._event_buffer: deque[TaskEventRecord] = deque(maxlen=500)

# In _append_event_safe: on failure → self._event_buffer.append(event)
# In submit_snapshot: call self._flush_buffer() first

def _flush_buffer(self) -> None:
    while self._event_buffer:
        event = self._event_buffer.popleft()
        try:
            self._repository.append_event(event)
        except Exception:
            self._event_buffer.appendleft(event)
            break
```

**Type:** cx-task (batch B)
**Done when:** 4 tests: buffer fills on failure, flushes on next submit, maxlen enforced.

---

## Phase C: Performance & Advanced Quality

### Task C1: httpx.AsyncClient migration for API adapters (cc-only)
**Complexity:** HIGH — changes adapter interface, execution model, all tests
**Decision:** BaseApiAdapter gets `async def execute_async()`. Router calls via `asyncio.to_thread` stays for now but optional async path added.
**Status:** Deferred — do only if phases A+B score still below 9.6.

---

### Task C2: Property-based tests for consensus/clustering (cx-task)
**Files:**
- Modify: `pyproject.toml` — add `hypothesis>=6.0,<7.0` to dev deps
- Create: `tests/test_consensus_properties.py`
- Create: `tests/test_clustering_properties.py`

**Tests:**
- `hac_cluster(texts, threshold)` — any input → cluster count ∈ [1, len(texts)]
- `compute_cluster_confidence(clusters)` — result ∈ [0.0, 1.0] always
- `similarity(a, b)` == `similarity(b, a)` (symmetry)
- Consensus with identical responses → score == 1.0

**Type:** cx-task (batch C)
**Done when:** hypothesis tests pass, no crashes on random inputs.

---

### Task C3: Raise coverage threshold to 85% + identify top gaps (cx-task)
**Files:**
- Modify: `pyproject.toml` — cov-fail-under from 80 → 85
- Create: `tests/test_coverage_gaps_*.py` — fill top 5 coverage gaps found by analysis

**Type:** cx-task (batch C)
**Done when:** `pytest --cov=gracekelly --cov-fail-under=85 -q` passes.

---

### Task C4: Docker multi-stage build (cx-task)
**Files:**
- Modify: `Dockerfile` — add builder stage, copy only necessary artifacts

**Type:** cx-task (batch C)
**Done when:** `docker build -t gracekelly .` succeeds, image size ≤ 200MB (vs current ~800MB).

---

## Quality Gate (per §10)
Before marking phase complete:
- `python -m pytest --tb=no -q` → 0 failures
- `mypy src/gracekelly/` → 0 errors
- `ruff check src/ tests/` → 0 errors
- `git diff --stat` → only expected files changed
- No TODO/FIXME/debug prints in new code
