# GraceKelly

Multi-model LLM orchestrator powered by your Perplexity Pro subscription.
Access GPT-5.4, Claude, Gemini, Kimi, and other models through Perplexity's
browser interface - then compare, debate, and reach consensus across models,
all within a single subscription.

The current operating target is a single-user local deployment: browser execution
via Perplexity is primary, and direct provider APIs remain optional fallbacks.

For a fast orientation, start with [docs/architecture.md](docs/architecture.md),
then [docs/operator-runbook.md](docs/operator-runbook.md), and finish with
[docs/phased-roadmap.md](docs/phased-roadmap.md).

## Quick Start

**1. Start the backend:**
```bash
pip install -e ".[dev,browser]"
cp .env.example .env
# Set GRACEKELLY_BROWSER_ENABLED=true
# Set GRACEKELLY_BROWSER_AUTOMATION_BACKEND=playwright
# Set GRACEKELLY_EXECUTION_PROFILE=hybrid
# Set GRACEKELLY_BROWSER_PROFILE_DIR to your Chrome profile with Perplexity login
python -m uvicorn gracekelly.main:create_app --factory --host 127.0.0.1 --port 8011
```

**2. Open the web UI:**

Open http://localhost:8011

**Docker alternative:**
```bash
docker-compose up
```

## Configuration

Copy `.env.example` and configure:

### Required: Perplexity (browser execution)

| Variable | Default | Description |
|----------|---------|-------------|
| `GRACEKELLY_BROWSER_ENABLED` | `false` | Set `true` to enable browser execution |
| `GRACEKELLY_BROWSER_AUTOMATION_BACKEND` | `null` | `playwright` for real browser, `scripted` for testing |
| `GRACEKELLY_BROWSER_PROFILE_DIR` | - | Path to Chrome profile with Perplexity login |
| `GRACEKELLY_BROWSER_CALL_TIMEOUT_SECONDS` | `120` | Per-call budget for one Perplexity submit. Raise for very long prompts; lower for aggressive fail-fast. |
| `GRACEKELLY_BROWSER_SCREENSHOTS_DIR` | - | Directory for per-step PNGs (session start, auth, model select, submit, response). Leave empty to disable. |

### Optional: API fallbacks

API adapters are optional. Use them only if you have separate API keys and want direct provider access alongside browser execution. Mistral remains embeddings-only.

| Variable | Description |
|----------|-------------|
| `GRACEKELLY_MISTRAL_API_KEY` | Optional. Used only for consensus-pattern embeddings (semantic clustering), not as an LLM provider |
| `GRACEKELLY_OPENAI_API_KEY` | OpenAI-compatible API |
| `GRACEKELLY_ANTHROPIC_API_KEY` | Anthropic API |

### General

| Variable | Default | Description |
|----------|---------|-------------|
| `GRACEKELLY_STORAGE_BACKEND` | `memory` | `memory` or `postgres` |
| `GRACEKELLY_POSTGRES_DSN` | - | PostgreSQL connection string |
| `GRACEKELLY_API_KEY` | - | Optional bearer token for endpoint auth |
| `GRACEKELLY_EXECUTION_PROFILE` | `dry-run` | one of: `dry-run`, `api-only`, `hybrid` |
| `GRACEKELLY_RATE_LIMIT_RPM` | `60` | Per-IP steady-state request limit enforced by the API middleware |
| `GRACEKELLY_RATE_LIMIT_BURST` | `10` | Extra burst capacity allowed above the steady-state per-minute limit |

Full reference: `.env.example`

## UI

Built-in HTML SPA served at `http://localhost:8011/` by the same FastAPI
process. Pattern is chosen from the model menu at the top of the main panel:

- **Sonar**, **Best**, **Claude 4.6**, **GPT-5.4**, **Gemini 3.1** — single-model patterns streaming into the chat panel
- **Claude + GPT**, **Claude + Gemini**, **Claude + Best**, **GPT + Best** — pairwise consensus
- **5М.Все мнения**, **5М.Сравнение**, **5М.Консенсус** — five-model compare / consensus bundles
- **Умный выбор** (smart), **Дебаты** (debate) — auto-routing patterns in the `Авто` group; both pin to `claude-sonnet-4-6` and hit `/api/v1/smart` / `/api/v1/debate`

Sidebar: task history with drill-down into steps and events, voice capture,
export, file attachments.

## API

| # | Method | Path | Description |
|---|--------|------|-------------|
| 1 | GET | `/health` | Service health |
| 2 | GET | `/healthz/live` | Liveness probe |
| 3 | GET | `/healthz/ready` | Readiness probe |
| 4 | GET | `/api/v1/readiness` | Component readiness |
| 5 | GET | `/metrics` | Prometheus metrics |
| 6 | POST | `/api/v1/orchestrate` | Multi-model execution |
| 7 | POST | `/api/v1/orchestrate/upload` | Multi-model execution with file attachments |
| 8 | POST | `/api/v1/orchestrate/stream` | Streaming execution (SSE) |
| 9 | GET | `/api/v1/tasks` | List recent tasks |
| 10 | GET | `/api/v1/tasks/{task_id}` | Task detail + steps + events |
| 11 | GET | `/api/v1/tasks/{task_id}/export` | Export task as Markdown |
| 12 | POST | `/api/v1/tasks/{task_id}/retry` | Retry a failed or cancelled task |
| 13 | GET | `/api/v1/models` | Model catalog |
| 14 | POST | `/api/v1/models/refresh` | Refresh model catalog snapshot |
| 15 | POST | `/api/v1/consensus` | Majority-vote consensus |
| 16 | GET | `/api/v1/analytics` | Model performance analytics |
| 17 | POST | `/api/v1/smart` | Auto-profile execution |
| 18 | POST | `/api/v1/smart/v2` | Consensus V2 (HAC clustering) |
| 19 | POST | `/api/v1/batch` | Parallel multi-prompt |
| 20 | POST | `/api/v1/pipeline` | Sequential task graph |
| 21 | GET | `/api/v1/health/detailed` | Per-component health |
| 22 | POST | `/api/v1/debate` | Devil's Advocate debate |
| 23 | POST | `/api/v1/compare` | Multi-model comparison |

Interactive docs: http://localhost:8011/docs

## Development

```bash
pip install -e ".[dev,postgres,browser]"
python -m pytest                    # tests
mypy src/gracekelly/                # type check (strict)
ruff check src/ tests/              # lint
python -m pytest --cov=gracekelly   # coverage
```

### Live end-to-end smoke

`scripts/live_smart_smoke.py` drives the SPA through a separate bundled
chromium and captures the `/api/v1/smart` or `/api/v1/debate` response.
It expects uvicorn already running with the browser env vars set and the
Chrome profile signed in to Perplexity; no chrome.exe must be using the
profile.

```bash
python scripts/live_smart_smoke.py --pattern smart --tag smoke-1
python scripts/live_smart_smoke.py --pattern debate --tag smoke-1 \
    --prompt "Your debate topic here."
```

Artifacts land in `.workflow/outbox/<tag>-<SMART|DEBATE>-*`
(response.json, before/after screenshots, report.md). Exit code 0 on a
meaningful answer that hits the topic keywords and carries no `[auth_failed]`
or streaming-chrome markers; 1 otherwise.

## Architecture

Routes -> Orchestrator -> Router -> Adapters (API / Browser) -> Storage (Memory / PostgreSQL).
See [docs/architecture.md](docs/architecture.md),
[docs/operator-runbook.md](docs/operator-runbook.md), and
[docs/phased-roadmap.md](docs/phased-roadmap.md).
