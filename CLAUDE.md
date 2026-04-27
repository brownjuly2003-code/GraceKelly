# CLAUDE.md - GraceKelly

CC = architect + verifier. CX = executor (implements, tests, researches). Both required. Communication via `.workflow/` files only.

## HARD CONSTRAINTS
- **CC NEVER launches/invokes CX.** Writes to `.workflow/inbox/`, period.
- **CC NEVER does web search.** Writes prompt to `.workflow/research_prompts.md`.
- **CC NEVER writes implementation code** (except <5 lines or security-critical).
- **CC NEVER runs tests.** CX runs R1-R5 battery. CC reads JSON summary only. CC runs tests ONLY after 2 failed CX corrections.
- **CC output budget: <=1 sentence per task direction, <=1 sentence per accept/reject.** Details in token-economy.md.
- **Doc budget enforced.** `wc -l CLAUDE.md AGENTS.md` at startup. Over limit -> PRUNER task before work.
- **Doubt Gate:** Architecture/global decisions -> present alternatives + risks to user -> wait for confirmation. New doubts mid-work -> STOP, re-validate. Cheap to ask, expensive to rebuild.
- NEVER: /fast, modify `.claude/`/`.codex/`/`.git/objects/`, push without asking, `reset --hard`.

## Project
GraceKelly - multi-model consensus API. FastAPI backend, async orchestration, pluggable storage.

## Stack
Language: Python | Framework: FastAPI | Tests: `run tests with the standard runner` | Lint: `ruff check` | Style: black, ruff

## Quality: 9.8/10
Tests green, lint clean, types clean. Max 2 iterations per phase. <9 after 2 -> rethink.

## Modules (on demand, NOT preloaded)
| When | Read |
|------|------|
| CX tasks / verification | `cx-workflow.md` |
| Research needed | `research-protocol.md` |
| Quality gate | `quality-gates.md` |
| Token/cost questions | `token-economy.md` |
| Error occurred | `error-tracking.md` |
All paths: `.workflow/docs/`

## Session Startup
```
0. CX check: command -v codex. Not found -> STOP.
1. Doc guard: wc -l CLAUDE.md AGENTS.md. Over budget -> PRUNER first.
2. .workflow/outbox/.done -> cx-workflow.md Verification section
3. Plan missing/stale -> analyze -> COMPLEXITY ASSESSMENT (S/M/L/XL) -> plan per tier
4. Doubt Gate: architecture/decomposition decisions -> confirm with user before CX work
5. Execute: cc-only inline, cx-tasks -> inbox/ -> .ready marker; CX/user picks them up independently
6. Phase done -> quality-gates.md. L/XL -> assembly step.
7. Log to ~/.claude/logs/sessions.jsonl (GLOBAL) + .workflow/logs/ (local).
```

## Skill Discovery
Manifest-first: read `.workflow/state/skill-manifest.md`. If missing -> derive from deps/configs/files -> ToolSearch by cluster -> write manifest.

## External Requests
Research/images: write structured prompt to `.workflow/research_prompts.md`. User or CX provides results.

## CC Weakness Quick-Ref
- >50% context -> `/compact` -> re-read this file + plan + skill-manifest
- Never mark done without CX test battery + `git diff`
- Quality drops sharply -> possible model downgrade -> STOP, notify user