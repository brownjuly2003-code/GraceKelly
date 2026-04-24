# Orchestrator2 vs GraceKelly — partial comparison (archived, incomplete)

**Status:** incomplete research, archived as reference.
**Date:** 2026-04-23.
**Coverage:** 4 of 10 planned fragments (01-inventory, 02-api-schemas, 03-api-behaviour, 04-patterns-consensus).

## Why archived

Original batch-101-a planned a 10-chunk deep comparison between `D:/Perplexity_Orchestrator2/` (reference production orchestrator) and `D:/GraceKelly/`. After 4 fragments landed, the series was cancelled as too expensive for the available budget. Focus shifted to the integrator-unblocking fix (batch-101-b) and Mistral-as-LLM ripout (batch-101-c).

## What's here

- `2026-04-23/01-inventory.md` — dual-codebase inventory (endpoints, patterns, models, adapters, services, env vars, deps).
- `2026-04-23/02-api-schemas.md` — request/response schemas side-by-side for all HTTP endpoints (4223 lines, most substantial fragment).
- `2026-04-23/03-api-behaviour.md` — routing defaults, error surface, streaming, retry, observability.
- `2026-04-23/04-patterns-consensus.md` — consensus-family patterns (INTERSECTIONS ↔ consensus V1/V2).

## What's missing (planned but never executed)

- 05-patterns-debate-compare-synth
- 06-patterns-smart-decomp-roles
- 07-browser-models
- 08-api-adapters-fallback
- 09-config-deps-services
- 10-assembly (consolidated doc + findings + prioritized recommendations)

## How to use

- If future work needs to compare Orchestrator2 vs GraceKelly: these 4 fragments are a validated starting point, no need to redo.
- Mistral-as-LLM artefact was first surfaced in this research (see `01-inventory.md` adapter inventory + `02-api-schemas.md` default-model field diffs). Resolved by batch-101-c.
- Do not cite as authoritative — incomplete by design; specific pre-ripout state of `src/gracekelly/adapters/api/mistral.py` reflected in `01-inventory.md` and `02-api-schemas.md` no longer matches HEAD.
