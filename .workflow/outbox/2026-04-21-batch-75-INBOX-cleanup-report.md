# INBOX-cleanup (batch-75 task-2)

Date: 2026-04-21
Status: **completed**.

## Moves
From `.workflow/inbox/` to `.workflow/inbox/Archive/`:

| File | Git state before | Move |
|------|------------------|------|
| `2026-04-21-AUTH-fix.md` | untracked | `mv` |
| `2026-04-21-AUTH-perplexity-overlay.md` | tracked, modified in worktree | `git mv` (preserves modified content) |
| `2026-04-21-batch-72.md` | untracked | `mv` |
| `2026-04-21-batch-73.md` | untracked | `mv` |
| `2026-04-21-batch-74.md` | untracked | `mv` |
| `2026-04-21-batch-76-rerun.md` | untracked | `mv` — batch-76 closed 2026-04-21 16:30 (see `.done`), re-run spec no longer active |

## After state
- `.workflow/inbox/` contains only: `2026-04-21-batch-75.md` (closed at end of batch), `Archive/`.
- `.workflow/inbox/.ready` → `2026-04-21-batch-75` during batch; cleared by closure commit.

## Done-when check
- [x] All 5 listed files moved to `Archive/`.
- [x] `git mv` used for the only tracked file (`AUTH-perplexity-overlay.md`); others are plain `mv`.
- [x] `.ready` repointed away from the stale `2026-04-21-batch-76-rerun`.
- [x] No deletions — all files preserved under `Archive/`.
