# DOCS-readme-api-inventory

Status: success

What changed:
- Expanded the README API table from 16 entries to 23 entries so it matches the currently registered route surface.
- Added the missing endpoints cited by audit plus the additional registered endpoints missing from README: `/healthz/live`, `/healthz/ready`, `/api/v1/analytics`, `/api/v1/orchestrate/upload`, `/api/v1/tasks/{task_id}/export`, `/api/v1/tasks/{task_id}/retry`, `/api/v1/models/refresh`.
- Corrected the task detail path placeholder from `{id}` to `{task_id}` to match the real route.
- Double-checked the visible README env table against `src/gracekelly/config.py` and added `GRACEKELLY_RATE_LIMIT_RPM` / `GRACEKELLY_RATE_LIMIT_BURST`; no mismatch was found in the pre-existing rows that stayed in scope.

Route inventory source:
- Command used: `rg -n "@router\\.(get|post|put|delete|patch)" src/gracekelly/api/routes`
- Registered endpoint count from route decorators: 23

Registered endpoints captured for the report:
1. `GET /health`
2. `GET /healthz/live`
3. `GET /healthz/ready`
4. `GET /api/v1/readiness`
5. `GET /metrics`
6. `POST /api/v1/orchestrate`
7. `POST /api/v1/orchestrate/upload`
8. `GET /api/v1/tasks`
9. `GET /api/v1/tasks/{task_id}`
10. `GET /api/v1/tasks/{task_id}/export`
11. `POST /api/v1/tasks/{task_id}/retry`
12. `POST /api/v1/orchestrate/stream`
13. `GET /api/v1/models`
14. `POST /api/v1/models/refresh`
15. `GET /api/v1/analytics`
16. `POST /api/v1/consensus`
17. `POST /api/v1/smart`
18. `POST /api/v1/smart/v2`
19. `POST /api/v1/batch`
20. `POST /api/v1/pipeline`
21. `GET /api/v1/health/detailed`
22. `POST /api/v1/debate`
23. `POST /api/v1/compare`

Verification:
- README API table row count: before 16, after 23.
- No stale endpoint rows were left in the README API table after sync.
- Repo test verification was attempted with `D:\GraceKelly\.venv\Scripts\python.exe -m pytest -q` and timed out twice (124s, then 604s), so no green-test claim is made for this batch.

Scope:
- `README.md`
