# 150: Wire Analytics Route into main.py — TODO

Wiring task. Dependency: analytics.py route exists.
Complexity: routine | Runs: 1

```
## GOAL
Wire the analytics route into main.py. EXACTLY 2 surgical line additions.

## CONTEXT
File to EDIT:
- `src/gracekelly/main.py` — add 1 import + 1 include_router

Files to READ (do NOT modify):
- `src/gracekelly/api/routes/analytics.py` — the router to include

## CONSTRAINTS
- Edit ONLY `src/gracekelly/main.py`. Do NOT modify any other files.
- Do NOT rewrite the file. EXACTLY 2 additions, 0 deletions.

### Exact changes

**Change 1**: Add import after the line `from gracekelly.api.routes.consensus import router as consensus_router`:
```python
from gracekelly.api.routes.analytics import router as analytics_router
```

**Change 2**: Add after `app.include_router(consensus_router)`:
```python
    app.include_router(analytics_router)
```

## DONE WHEN
- [ ] `git diff src/gracekelly/main.py` shows ONLY 2 `+` lines, 0 `-` lines
- [ ] `python -m pytest -q` → all tests pass (693+)
- [ ] No other files modified

## SELF-EVALUATION
Target: 9.8/10. Verify `git diff` shows exactly 2 additions.
```
