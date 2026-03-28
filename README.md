# GraceKelly

Multi-model LLM orchestrator with browser and API execution backends.

## Quick Start

**Docker:**
```bash
docker-compose up
curl http://localhost:8011/health
```

**Local:**
```bash
pip install -e ".[dev]"
cp .env.example .env  # set GRACEKELLY_MISTRAL_API_KEY etc.
uvicorn gracekelly.main:create_app --factory --host 0.0.0.0 --port 8011
```

## Configuration

Copy `.env.example` and set these key variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GRACEKELLY_MISTRAL_API_KEY` | yes (API mode) | — | Mistral AI API key |
| `GRACEKELLY_OPENAI_API_KEY` | no | — | OpenAI-compatible API key |
| `GRACEKELLY_ANTHROPIC_API_KEY` | no | — | Anthropic API key |
| `GRACEKELLY_STORAGE_BACKEND` | no | `memory` | `memory` or `postgres` |
| `GRACEKELLY_POSTGRES_DSN` | if postgres | — | e.g. `postgresql://user:pass@host/db` |
| `GRACEKELLY_API_KEY` | no | — | Bearer token for endpoint auth |
| `GRACEKELLY_EXECUTION_PROFILE` | no | `default` | `default` or `dry-run` |
| `GRACEKELLY_ORCHESTRATE_TIMEOUT_SECONDS` | no | — | 504 timeout for long requests |

Full reference: `.env.example`

## API

| # | Method | Path | Description |
|---|--------|------|-------------|
| 1 | GET | `/health` | Service health |
| 2 | GET | `/api/v1/readiness` | Detailed component readiness |
| 3 | GET | `/metrics` | Prometheus metrics |
| 4 | POST | `/api/v1/orchestrate` | Multi-model LLM execution |
| 5 | GET | `/api/v1/tasks` | List recent tasks |
| 6 | GET | `/api/v1/tasks/{id}` | Task detail with steps + events |
| 7 | GET | `/api/v1/models` | Available models catalog |
| 8 | POST | `/api/v1/consensus` | Majority-vote consensus |
| 9 | POST | `/api/v1/smart` | Auto-profile execution |
| 10 | POST | `/api/v1/smart/v2` | Consensus V2 (HAC clustering) |
| 11 | POST | `/api/v1/batch` | Parallel multi-prompt |
| 12 | POST | `/api/v1/pipeline` | Sequential task graph |
| 13 | POST | `/api/v1/debate` | Devil's Advocate debate |
| 14 | POST | `/api/v1/compare` | Multi-model comparison + judge |
| 15 | GET | `/api/v1/health/detailed` | Per-component health |

Interactive docs: `http://localhost:8011/docs`

## Development

```bash
# Install with all extras
pip install -e ".[dev,postgres,browser]"

# Run tests
python -m pytest

# Type check (strict)
mypy src/gracekelly/

# Lint
ruff check src/ tests/

# Coverage
python -m pytest --cov=gracekelly --cov-report=term-missing
```

## Architecture

GraceKelly routes prompts to parallel model adapters (API or browser), aggregates
results via configurable merge strategies, and persists everything to storage.
See `docs/architecture.md` for the full design.
