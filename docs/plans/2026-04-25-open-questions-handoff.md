# Open questions handoff — 2026-04-25 EOD

This document is intentionally untracked (`docs/plans/` is gitignored by design).
It captures state that is not in git yet, so the next session can resume cleanly.

## What landed today (committed)

GraceKelly (`D:\GraceKelly`):
- HEAD `014839a` — full integration closure series: batches 101-b/c + 102 + 103 + 104 + 105 + 106 + 107.
- Mistral-as-LLM ripped out, dry-run profile-gate uniform across 8 sync routes, `scripts/ecosystem_smoke.py`, `scripts/win-autostart/`, `mypy --strict src tests` clean (264 files), full docs sync (README/architecture/runbook/roadmap).

Perplexity_Orchestrator2 (`D:\Perplexity_Orchestrator2`):
- HEAD `6c17e93` — V1 formally deprecated. `DEPRECATED.md`, `SERVERS.md`, `CLAUDE.md` banner, `juhub/CLAUDE.md` V2 note. juhub client migration earlier today (HEAD `8ff3886`).

agent_toolkit (`D:\agent_toolkit`):
- HEAD `1276a06` — V1→V2 migration + initial repo + lint cleanup. 11 commits chain.

## What is sitting unstaged (NOT committed)

GraceKelly worktree:
```
M src/gracekelly/adapters/browser/perplexity.py
?? CLAUDE.md
?? docs/plans/
```

The single `M` file is **not from any of the batches landed today**. It is the GraceKelly-side half of `RAG_Support_Assistant` task-177 — a threadpool fix that lives across two repos. RAG side has 3 unstaged on top of HEAD `f0fc81b` (per memory). The fix has been live-verified end-to-end against a real Perplexity session, but the commit decision is open (see below).

## Open question (carried into next session)

**Context.** RAG_Support_Assistant ran a 20-case smoke series after task-177 (routing fix + GK threadpool fix). Initial cases passed and live-verified the fix. Mid-series the run blocked on **two new GK UI flakiness modes**:

1. **Sonar auto-route flakiness** — Perplexity UI sometimes auto-selects Sonar instead of the requested model. Reproducible but intermittent.
2. **Locator.click timeout** — Playwright `Locator.click` 5s timeout on model selection under sustained load (different from the dry-run-profile timeout fixed in batch-102; this is a real Perplexity click, not adapter resolution).

Both are upstream of the RAG smoke harness — they originate in the Perplexity browser layer of GK. Neither is yet diagnosed beyond the symptom.

**The decision:**

- **Option A — Commit partial closure now.** Stage and commit the existing GK threadpool fix from worktree + RAG side's 3 unstaged. Move on. Sonar auto-route + Locator.click timeout are tracked as a separate follow-up batch.
  - *Pro:* Today's work is locked in. Worktree clean. Threadpool fix benefits everyone immediately.
  - *Con:* The 20-case RAG smoke does not pass end-to-end yet. Partial closure means RAG side has visible "task-177 done but smoke still red".

- **Option B — Push through to clean 20-case green first.** Diagnose Sonar auto-route + Locator.click timeout in GK browser layer, fix, then single atomic closure across both repos.
  - *Pro:* Single clean closure narrative; 20-case smoke green at the moment of commit.
  - *Con:* Unknown depth. UI flakiness can be days of triage. Threadpool fix sits unstaged that whole time, vulnerable to drift.

**Recommendation (CC's read):** Option A is lower risk — the threadpool fix is independently valuable, the new flakiness modes are orthogonal, and "partial closure with explicit follow-up" is healthier than letting fixes age in worktree. Option B is right only if Sonar auto-route looks shallow on first inspection.

**Human decision required.** Do not commit `src/gracekelly/adapters/browser/perplexity.py` blindly without Юлия's explicit choice.

## How to resume next session

1. `cd D:\GraceKelly && git status --short` — confirm `M src/gracekelly/adapters/browser/perplexity.py` is still there. If clean, someone already committed; check `git log` for the new commit.
2. `git diff src/gracekelly/adapters/browser/perplexity.py | head -120` — read the threadpool fix to understand what's pending.
3. `cd D:\RAG_Support_Assistant && git status --short` — confirm 3 unstaged still present. Read project memory (`project_rag_support_assistant.md`) for full task-177 context.
4. Ask Юлия: Option A or Option B?
5. If A — split staging by repo, atomic commits with cross-references, update memory.
6. If B — start triage on Sonar auto-route. Smallest reproducer first; do not boil the ocean.

## Pointers

- This doc: `D:\GraceKelly\docs\plans\2026-04-25-open-questions-handoff.md` (untracked).
- Memory updated: `project_gracekelly.md` (carries the open question into description).
- RAG memory: `project_rag_support_assistant.md` (has matching task-177 context from RAG side).
- Latest landed integration story: `D:\GraceKelly\docs\phased-roadmap.md` `## 2026-04-25 Integration closure`.
