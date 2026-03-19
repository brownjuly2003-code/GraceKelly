# 070: Move Consensus Execution to src — TODO

Phase 6 integration (step 1/3). Dependency: 060 (sandbox draft).
Complexity: routine | Runs: 1

```
## GOAL
Copy `docs/codex/drafts/consensus_execution.py` to `src/gracekelly/core/consensus_execution.py` (identical content). Create one new file, modify nothing.

## CONTEXT
Files to CREATE:
- `src/gracekelly/core/consensus_execution.py` — production copy

Files to READ (do NOT modify):
- `docs/codex/drafts/consensus_execution.py` — source to copy

Architecture:
- The file is already tested and imports all resolve correctly (modules exist in `src/gracekelly/core/`)
- Test runner: `python -m pytest -q`

## CONSTRAINTS
- Create ONLY the one file listed above. Do NOT modify any existing files.
- Copy the content EXACTLY from `docs/codex/drafts/consensus_execution.py`. Do NOT change anything.
- Do NOT create a test file — the existing sandbox test covers it, and integration tests come in task 080.

## DONE WHEN
- [ ] `src/gracekelly/core/consensus_execution.py` exists with identical content to `docs/codex/drafts/consensus_execution.py`
- [ ] `python -c "from gracekelly.core.consensus_execution import ConsensusExecutor"` succeeds
- [ ] `python -m pytest -q` → all existing tests still pass (619+)
- [ ] No other files created or modified

## SELF-EVALUATION
Target: 9.8/10. Verify the file is byte-for-byte identical to the source.
```
