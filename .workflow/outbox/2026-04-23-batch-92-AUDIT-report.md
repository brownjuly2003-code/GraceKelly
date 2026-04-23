# AUDIT-post-phase-2

Status: success

Primary deliverable:
- `docs/audits/2026-04-23-post-phase-2-audit.md`

Executive summary:
- Health score: `7.6/10`
- Verdict: `needs targeted hardening`
- Baseline gates confirmed on HEAD `7e50fb7`: `pytest -q` -> `2647 passed, 6 skipped`, `ruff` clean, `mypy --strict` clean, coverage `97%`

Top findings:
- `P1`: `ExecutionRouter` still reads module-global settings for budget/fallback, so `create_app(Settings(...))` does not propagate those values into runtime behavior.
- `P1`: baseline coverage omits `playwright_driver.py`; targeted coverage shows `_find_option_in_menu_scope` at only `71.4%` line coverage.
- `P1`: `docs/phased-roadmap.md` still marks Phase 2/4 as partial, references obsolete `GRACEKELLY_RATE_LIMIT_PER_MINUTE`, and claims delivered CORS support with no implementation match.

Other notable findings:
- `P2`: three files exceed 600 LOC and multiple route/adapter functions exceed 100 LOC.
- `P2`: stale `mypy` override block remains in `pyproject.toml`.
- `P2`: fallback flow has result metadata but no dedicated structured log event.
- `P2`: README API table and architecture doc lag the actual route/module surface.
- `P3`: likely dead-code candidates (`get_browser_catalog`, `ComponentStatus`) and very low public docstring density.

Security/dependency posture:
- `pip-audit` found no known vulnerabilities.
- No matches for `os.system`, `subprocess.call`, `eval`, `pickle.loads`, or `yaml.load` in `src/`.
- No hard-coded secrets detected outside normal env/key plumbing.
- No obvious unused direct runtime dependency found.

Verification:
- `.venv/Scripts/python.exe -m pytest -q`
- `.venv/Scripts/pytest.exe -q --durations=20`
- `.venv/Scripts/python.exe -m ruff check src tests`
- `.venv/Scripts/python.exe -m mypy src --strict`
- `.venv/Scripts/python.exe -m coverage report --show-missing --sort=cover`
- `uv pip list --python .venv/Scripts/python.exe --outdated`
- `pip-audit.exe --path .venv/Lib/site-packages`

Scope:
- `docs/audits/2026-04-23-post-phase-2-audit.md`
- `.workflow/outbox/2026-04-23-batch-92-AUDIT-report.md`
- `.workflow/outbox/2026-04-23-batch-92-AUDIT.result.json`
