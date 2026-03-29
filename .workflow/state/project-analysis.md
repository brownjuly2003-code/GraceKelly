# GraceKelly — Project Analysis
Updated: 2026-03-29 | CC: Claude Sonnet 4.6

## Stack
- **Language:** Python 3.11–3.13
- **Framework:** FastAPI 0.115, Uvicorn 0.30
- **Storage:** memory (default) | PostgreSQL (psycopg3)
- **Adapters:** httpx (API), Playwright (browser)
- **Tests:** pytest 9.x, **2355 passing**, 2 skipped, 0 failures
- **Quality:** mypy strict 0 errors | ruff 0 errors | coverage **93.85%** (gate: 93%)
- **CI:** GitHub Actions (Python 3.11/3.12), mypy --strict, ruff, pytest-cov ≥93%, pip-audit, bandit

## Code Style
- `from __future__ import annotations` on all files
- `@dataclass(frozen=True, slots=True)` for contracts
- `StrEnum` for all enums
- Imports: stdlib → third-party → local, sorted
- Indentation: 4 spaces, 120-char line limit
- No unused imports (ruff F401 enforced)
- Type annotations: 100% (mypy strict)

## Current Score: ~9.7/10

### By category:
| Category | Score | Notes |
|----------|-------|-------|
| Architecture | 9/10 | Clean layers, submit_snapshot ~80 LOC acceptable |
| Testing | 9.5/10 | 2355 tests, 94% coverage, property-based tests (hypothesis) |
| Security | 9/10 | Strict auth mode, rate limiting, bandit, SAST in CI |
| Performance | 8/10 | Sync adapters in asyncio.to_thread (acceptable) |
| Reliability | 9/10 | Event buffering, config validation, k8s probes |
| UX/DX | 9.5/10 | README, correlation IDs, RFC 7807 errors, /healthz probes |
| DevOps | 9/10 | Multi-stage Docker, CI with coverage gate 93%, SAST |

## Endpoints (17 total)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Service health |
| GET | `/healthz/live` | Kubernetes liveness probe |
| GET | `/healthz/ready` | Kubernetes readiness probe |
| GET | `/api/v1/readiness` | Detailed component readiness |
| GET | `/metrics` | Prometheus metrics |
| POST | `/api/v1/orchestrate` | Multi-model LLM execution |
| GET | `/api/v1/tasks` | List recent tasks |
| GET | `/api/v1/tasks/{id}` | Task detail with steps + events |
| GET | `/api/v1/models` | Available models catalog |
| POST | `/api/v1/consensus` | Majority-vote consensus |
| POST | `/api/v1/smart` | Auto-profile execution |
| POST | `/api/v1/smart/v2` | Consensus V2 (HAC clustering) |
| POST | `/api/v1/batch` | Parallel multi-prompt |
| POST | `/api/v1/pipeline` | Sequential task graph |
| POST | `/api/v1/debate` | Devil's Advocate debate |
| POST | `/api/v1/compare` | Multi-model comparison + judge |
| GET | `/api/v1/health/detailed` | Per-component health |

## Remaining gaps (deferred)
- **Async adapters** — httpx.AsyncClient migration (high complexity, low risk: already in asyncio.to_thread)
- **Redis rate limiting** — for multi-process deployments
- **OpenTelemetry** — distributed tracing
- **Sentry** — error tracking integration

## Key files
- `src/gracekelly/main.py` — app factory, lifespan, middleware wiring, RFC 7807 handlers
- `src/gracekelly/config.py` — Settings dataclass, env loading, validate()
- `src/gracekelly/middleware.py` — auth, rate limiting, metrics, X-Request-ID correlation
- `src/gracekelly/core/orchestrator.py` — submit_snapshot, _event_buffer (deque maxlen=500)
- `src/gracekelly/adapters/api/base.py` — httpx.Client, retry logic
- `src/gracekelly/api/routes/health.py` — /health, /healthz/live, /healthz/ready, Prometheus metrics
