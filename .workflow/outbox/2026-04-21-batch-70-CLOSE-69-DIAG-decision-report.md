# CLOSE-69-DIAG-decision

Date: 2026-04-21

Chosen
- Option B: split the remaining Perplexity login-overlay issue into a dedicated AUTH task.

Artifacts updated
- `.workflow/outbox/2026-04-20-batch-69-DIAG-orchestrate-500-report.md`
- `.workflow/decisions/2026-04-21-diag-orchestrate-500.md`
- `.workflow/inbox/2026-04-21-AUTH-perplexity-overlay.md`

Rationale
- The route-level unknown `500` handling and the auth overlay are different failure classes.
- Batch 69 keeps the structured `500` fallback and `PermissionError` handling; the remaining live issue is now explicitly tracked as auth/session follow-up work.
