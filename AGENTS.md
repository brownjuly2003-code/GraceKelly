# Project Agent Instructions

You are a task worker for GraceKelly — a Python FastAPI multi-model LLM orchestrator.

## Workflow
1. Read all .md in .workflow/inbox/ (sorted by name). For each:
   - Read ONLY files listed in files_to_read / files_to_modify
   - Follow CONSTRAINTS exactly
   - Run verification from done_when
   - Write result to .workflow/outbox/{filename}.result.json
   - Move task to .workflow/done/
2. Read all .md in .workflow/consult/pending/. For each:
   - Analyze deeply, write to .workflow/consult/done/{filename}
   - Move original to .workflow/done/
3. Say "All tasks complete."

## Result format
{"task_id":"...","status":"success|failure|blocked","files_modified":[...],"tests_passed":bool,"error":null|"...","self_score":"1-10","notes":"..."}

## Project specifics
- Language: Python 3.11+
- Framework: FastAPI + Uvicorn
- Tests: `python -m pytest --tb=short -q` (from D:/GraceKelly)
- Lint: `ruff check src/ tests/` (must be 0 errors)
- Types: `mypy src/gracekelly/` (must be 0 errors, strict mode)
- All source files start with `from __future__ import annotations`
- Imports: stdlib → third-party → local, alphabetically sorted within groups
- 4-space indent, 120-char lines
- `@dataclass(frozen=True, slots=True)` for immutable contracts
- `StrEnum` for all enums
- Test classes: `class FooBarTests(unittest.TestCase):`
- Test methods: `def test_something_specific(self) -> None:`

## Rules
- Surgical edits only. No full rewrites. No extra try/catch, logging, comments, abstractions.
- No files outside scope. If unclear — write error, don't guess.
- Every new test file needs `from __future__ import annotations` + `import unittest`
- After edits: run ruff + mypy on changed files. Fix all issues before reporting success.
- Tests must pass: run `python -m pytest {changed_test_files} --tb=short` to verify.
