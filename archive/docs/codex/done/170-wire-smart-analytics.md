# 170: Wire Smart + Analytics Routes — TODO

Wiring task. Dependency: 150 (analytics wired), 160 (smart route exists).
Complexity: routine | Runs: 1

```
## GOAL
Wire the smart route into main.py. EXACTLY 2 surgical line additions (analytics should already be wired by task 150).

## CONTEXT
File to EDIT:
- `src/gracekelly/main.py`

## CONSTRAINTS
- Edit ONLY `src/gracekelly/main.py`. EXACTLY 2 additions, 0 deletions.

### Exact changes

**Change 1**: Add import after the analytics import line:
```python
from gracekelly.api.routes.smart import router as smart_router
```

**Change 2**: Add after `app.include_router(analytics_router)`:
```python
    app.include_router(smart_router)
```

## DONE WHEN
- [ ] `git diff src/gracekelly/main.py` shows ONLY 2 new `+` lines
- [ ] `python -m pytest -q` → all tests pass
- [ ] No other files modified

## SELF-EVALUATION
Target: 9.8/10.
```
