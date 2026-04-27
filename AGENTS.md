# Task Worker - CC+CX Role Rotation

## Workflow
1. Read `.workflow/docs/cx-roles.md` once per session.
2. Read `.workflow/inbox/*.md` sorted by name. For each task:
   - Read only `files_to_read` / `files_to_modify`
   - Execute roles 1-5 in order from `.workflow/docs/cx-roles.md`
   - Write `.workflow/outbox/{task_id}.result.json`
   - Save raw test output to `.workflow/outbox/{task_id}-test-output.log`
   - Move the task file to `.workflow/done/`
3. Read `.workflow/consult/pending/*.md`, write analyses to `.workflow/consult/done/`, then move originals to `.workflow/done/`.
4. After all tasks, execute role 6 (PRUNER) once per batch.
5. Write `.workflow/outbox/.done` with batch completion metadata: `{"completed_at":"...","exit_code":0}`.
6. Say `All tasks complete.`

## Roles
1. IMPLEMENTER
2. TEST AUTHOR
3. RUNNER
4. ADVERSARY
5. AUDITOR
6. PRUNER (after all tasks)

Full role details, result schema, R1-R5 battery, and PRUNER rules live in `.workflow/docs/cx-roles.md`.

## Rules
- Surgical edits only. No full rewrites unless the task explicitly requires one.
- No files outside task scope. If scope is unclear, return `blocked` instead of guessing.
- Follow task constraints exactly. Do not modify `CLAUDE.md` unless explicitly requested.
- Self-score must be >= 9 or iterate up to 3 times.
- Keep workflow docs concise; if you add a line, remove a line elsewhere.

## Project
- Language: Python 3.11+
- Framework: FastAPI + Uvicorn
- Tests: `python -m pytest -p no:schemathesis --tb=short -q` (run from `D:/GraceKelly`)
- Lint: `ruff check src/ tests/` with 0 errors
- Types: `mypy src/ tests/` in strict mode with 0 errors
- Source files start with `from __future__ import annotations`
- Imports: stdlib -> third-party -> local, alphabetized within each group
- Style: 4-space indent, 120-char lines
- Contracts: `@dataclass(frozen=True, slots=True)` for immutable contracts; `StrEnum` for all enums
- Tests: `unittest.TestCase` classes named `FooBarTests`; methods named `test_something_specific`
- No extra try/catch, logging, comments, or abstractions unless the task asks for them
