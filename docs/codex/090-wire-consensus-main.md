# 090: Wire Consensus into main.py — TODO

Phase 6 integration (step 3/3). Dependency: 070, 080.
Complexity: routine | Runs: 1

```
## GOAL
Wire the consensus route and EmbeddingsClient into main.py. This task makes SURGICAL edits to ONE existing file — exactly 4 lines added.

## CONTEXT
File to EDIT:
- `src/gracekelly/main.py` — add 2 imports + 2 lines in create_app()

Files to READ (do NOT modify):
- `src/gracekelly/api/routes/consensus.py` — the router to include
- `src/gracekelly/core/embeddings.py` — EmbeddingsClient constructor

Architecture:
- The Mistral API key (`active_settings.mistral_api_key`) is already available in create_app()
- EmbeddingsClient uses the same Mistral key for embeddings
- The consensus router must be included after other routers

## CONSTRAINTS
- Edit ONLY `src/gracekelly/main.py`. Do NOT modify any other files.
- Do NOT rewrite the entire file. Make EXACTLY 4 surgical additions.
- Do NOT add: logging calls, comments, docstrings, error handling, new functions.
- Do NOT move, rename, or reformat any existing code.
- Preserve exact whitespace and style of the existing file.

### Exact changes required

**Change 1**: Add import after line 26 (`from gracekelly.api.routes.orchestrate import router as orchestrate_router`):
```python
from gracekelly.api.routes.consensus import router as consensus_router
```

**Change 2**: Add import after the existing `from gracekelly.core.orchestrator import OrchestratorService` (line 32):
```python
from gracekelly.core.embeddings import EmbeddingsClient
```

**Change 3**: Add after line `app.state.request_metrics = RequestMetrics()` (around line 182), BEFORE setup_api_key_auth:
```python
    app.state.embeddings_client = EmbeddingsClient(
        api_key=active_settings.mistral_api_key or "",
        base_url="https://api.mistral.ai/v1",
    )
```

**Change 4**: Add after line `app.include_router(orchestrate_router)` (around line 189):
```python
    app.include_router(consensus_router)
```

That is ALL. Four additions. No deletions. No modifications.

## DONE WHEN
- [ ] `src/gracekelly/main.py` has exactly 4 new lines (2 imports + 2 in create_app)
- [ ] `python -c "from gracekelly.main import create_app; app = create_app(); print('OK')"` succeeds
- [ ] `python -m pytest -q` → all existing tests still pass (619+)
- [ ] `git diff src/gracekelly/main.py` shows ONLY 4 additions, 0 deletions
- [ ] No other files modified

## SELF-EVALUATION
After completing, score yourself 1-10:
- Are there EXACTLY 4 new lines (no more)?
- Did you ADD lines or REPLACE lines? (must be ADD only)
- Does `git diff` show only `+` lines, no `-` lines?
- Did you preserve all existing whitespace and formatting?

If your self-score is below 9.8/10, fix issues before submitting. Target: 9.8/10.
```
