# Final Closure Plan — 2026-04-23

Goal: close every remaining open item in `docs/phased-roadmap.md` and produce a polished documentation surface, so GraceKelly can move into maintenance-only mode without ambiguity.

HEAD entering plan: `3cdea66` (batch-97 final closure landed).

## Context

After today's run (batches 86→97), three classes of open items remain:

1. **Gate 2 conditioned pass** — `/healthz/ready` is storage-only shallow probe; full semantic readiness only on `/api/v1/readiness`. Noted as "PASS with conditions" in `docs/gates/2026-04-23-gate-2-operational-review.md`. Trivial code fix lifts the condition.

2. **Phase 13 Remaining** (5 items) + **Phase 14 Remaining deferred** (1 item, overlap) — all are production/multi-user scope:
   - async adapters (sync blocks event loop — currently wrapped in `asyncio.to_thread`)
   - Redis-backed rate limiting (multi-process)
   - OpenTelemetry distributed tracing
   - Sentry error tracking
   - Load testing framework

   None of these are required for single-user local deploy. They need explicit relabel as trigger-reactive, analogous to batch-97's handling of the API hedge `Next:` item.

3. **Documentation polish** — after the code/docs mutations of 86→99, the README, architecture.md, operator-runbook.md, and phased-roadmap.md need a pass to ensure:
   - no stale cross-references between docs;
   - consistent terminology (batches, audit findings, gate outcomes);
   - clean reading order for a new contributor;
   - `CHANGELOG`-style summary at the head of the roadmap (session timeline).

## Batches

### batch-98 — Gate 2 shallow-probe fix (real code, tiny)

Scope: `src/gracekelly/api/routes/health.py`, `tests/test_http_api.py` (or whichever test file already covers `/healthz/ready`), `docs/gates/2026-04-23-gate-2-operational-review.md`.

Approach: keep `/healthz/ready` fast (Kubernetes convention for readiness probes). Add a lightweight browser-readiness check that does not require I/O beyond reading `app.state.execution_router`'s already-populated state. Concretely: 503 when `execution_router` is missing, or when the browser adapter is declared enabled in settings but not initialized. This matches `/api/v1/readiness`'s decisions without running the expensive readiness report.

Gate 2 criterion 2 in the self-review doc upgrades from "PASS with conditions" to "PASS".

Gate verification: ruff/mypy/scoped pytest all clean.

### batch-99 — Roadmap relabel + gate sync (docs only)

Scope: `docs/phased-roadmap.md`, `docs/gates/2026-04-23-gate-2-operational-review.md` (touched again for the post-fix update), `docs/architecture.md` if any of the relabeled items are mentioned there.

Approach (relabel, not delete):
- Phase 13 "Remaining" heading renamed to `Trigger-reactive follow-up (production/multi-user scope):` with per-item one-line rationale ("async adapters — activate if event-loop stalls are observed under real load", etc.).
- Phase 14 "Remaining (deferred)" aligned to the same label; async adapters item merged with Phase 13's (not duplicated).
- Gate 2 self-review doc updated to PASS (no conditions) with post-fix evidence.

No code in this batch.

### batch-100 — Documentation polish pass (docs only)

Scope: `README.md`, `docs/architecture.md`, `docs/operator-runbook.md`, `docs/phased-roadmap.md`. Read-and-revise, not rewrite.

Approach:
- Add a short `## Session timeline` or `## Roadmap closure` section at the top of `docs/phased-roadmap.md` with dates of phase completions and links to today's audit + gate reviews.
- Cross-reference sanity pass: every `docs/…` mentioned in README/architecture/runbook exists and points to the right section anchor.
- Terminology sweep: "batch" numbering consistent, failure codes quoted the same way, env variable names match `config.py`.
- Remove any "TODO" / "TBD" / "pending" markers that are stale after 86→99.
- README should open with a 3-paragraph overview that a new contributor can read in under 2 minutes before diving in.
- Operator runbook should have a clear "Quickstart" flow at the top (boot → auth → first smoke) that links into the deeper sections.

Gate verification: markdown renders cleanly (spot-check by reading rendered preview), no broken anchors, no orphan files.

## Sequencing

Strict sequential through `.ready` self-chain, same pattern as batches 94-96:

1. `batch-98` lands code fix + its own gate-doc update for criterion 2, commits, re-touches `.ready`.
2. `batch-99` relabels roadmap Phase 13/14 and sweeps gate doc to final PASS, commits, re-touches `.ready`.
3. `batch-100` performs the polish pass, commits, **deletes** `.ready` (last in series).

After batch-100 closure, user triggers `/clear` to start a fresh session; memory should carry the final state (`HEAD <new>`, all phases complete, every gate PASS unconditional, docs polished) so the next session orients directly from memory.

## Explicit non-goals

- No production code touched beyond batch-98's health.py edit. Async adapters / Redis / OTel / Sentry / load testing remain unimplemented and trigger-reactive.
- No rewrite of existing doc sections. Polish pass is additive and corrective only.
- No new test coverage beyond the one test batch-98 adds for the readiness endpoint.
- No release/tag action (this plan does not ship a new version bump).
