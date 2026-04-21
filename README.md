# GraceKelly

Multi-model LLM orchestrator powered by your Perplexity Pro subscription.
Access GPT-5.4, Claude, Gemini, Kimi, and other models through Perplexity's
browser interface - then compare, debate, and reach consensus across models,
all within a single subscription.

## Quick Start

**1. Start the backend:**
```bash
pip install -e ".[dev,browser]"
cp .env.example .env
# Set GRACEKELLY_BROWSER_ENABLED=true
# Set GRACEKELLY_BROWSER_AUTOMATION_BACKEND=playwright
# Set GRACEKELLY_BROWSER_PROFILE_DIR to your Chrome profile with Perplexity login
uvicorn gracekelly.main:create_app --factory --host 127.0.0.1 --port 8011
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

### Optional: API fallbacks

API adapters are optional. Use them only if you have separate API keys and want direct provider access alongside browser execution.

| Variable | Description |
|----------|-------------|
| `GRACEKELLY_MISTRAL_API_KEY` | Mistral API (also used for embeddings in consensus v2) |
| `GRACEKELLY_OPENAI_API_KEY` | OpenAI-compatible API |
| `GRACEKELLY_ANTHROPIC_API_KEY` | Anthropic API |

### General

| Variable | Default | Description |
|----------|---------|-------------|
| `GRACEKELLY_STORAGE_BACKEND` | `memory` | `memory` or `postgres` |
| `GRACEKELLY_POSTGRES_DSN` | - | PostgreSQL connection string |
| `GRACEKELLY_API_KEY` | - | Optional bearer token for endpoint auth |
| `GRACEKELLY_EXECUTION_PROFILE` | `dry-run` | `default` or `dry-run` |

Full reference: `.env.example`

## UI

Built-in HTML SPA served at `http://localhost:8011/` by the same FastAPI
process. Pattern is chosen from the model menu at the top of the main panel:

- **Sonar**, **Best**, **Claude 4.6**, **GPT-5.4**, **Gemini 3.1** — single-model patterns streaming into the chat panel
- **Claude + GPT**, **Claude + Gemini**, **Claude + Best**, **GPT + Best** — pairwise consensus
- **5М.Все мнения**, **5М.Сравнение**, **5М.Консенсус** — five-model compare / consensus bundles

Sidebar: task history with drill-down into steps and events, voice capture,
export, file attachments. The `/api/v1/smart` and `/api/v1/debate` endpoints
remain live but are not surfaced in the current model-menu UI — drive them
through the API directly or via the task-replay flow.

## API

| # | Method | Path | Description |
|---|--------|------|-------------|
| 1 | GET | `/health` | Service health |
| 2 | GET | `/api/v1/readiness` | Component readiness |
| 3 | GET | `/metrics` | Prometheus metrics |
| 4 | POST | `/api/v1/orchestrate` | Multi-model execution |
| 5 | POST | `/api/v1/orchestrate/stream` | Streaming execution (SSE) |
| 6 | GET | `/api/v1/tasks` | List recent tasks |
| 7 | GET | `/api/v1/tasks/{id}` | Task detail + steps + events |
| 8 | GET | `/api/v1/models` | Model catalog |
| 9 | POST | `/api/v1/consensus` | Majority-vote consensus |
| 10 | POST | `/api/v1/smart` | Auto-profile execution |
| 11 | POST | `/api/v1/smart/v2` | Consensus V2 (HAC clustering) |
| 12 | POST | `/api/v1/batch` | Parallel multi-prompt |
| 13 | POST | `/api/v1/pipeline` | Sequential task graph |
| 14 | POST | `/api/v1/debate` | Devil's Advocate debate |
| 15 | POST | `/api/v1/compare` | Multi-model comparison |
| 16 | GET | `/api/v1/health/detailed` | Per-component health |

Interactive docs: http://localhost:8011/docs

## Development

```bash
pip install -e ".[dev,postgres,browser]"
python -m pytest                    # tests
mypy src/gracekelly/                # type check (strict)
ruff check src/ tests/              # lint
python -m pytest --cov=gracekelly   # coverage
```

## Architecture

Routes -> Orchestrator -> Router -> Adapters (API / Browser) -> Storage (Memory / PostgreSQL).
See `docs/architecture.md`.
