# HARNESS-expand-patterns

Status: success

Summary:
- `scripts/live_smart_smoke.py` now accepts `--pattern` in `smart`, `debate`, `consensus`, `compare`, `upload`.
- Added `--attachment` for `upload`; `upload` without an attachment now fails through `argparse.error()`, and attachments on other patterns are warned and ignored.
- Added `PATTERN_DEFAULT_PROMPT` and `PATTERN_EVALUATION` so each pattern has its own answer fields, minimum length, and keyword checks.
- Added upload composer submission via `#file-input` with direct POST fallback, and direct POST fallback for `consensus` / `compare` because the exact UI labels are not surfaced in `static/js/model-menu.js`.
- Backward compatibility is preserved for `python scripts/live_smart_smoke.py` and for legacy `--pattern smart|debate` calls.

UI labels and fallback strategy:
- `smart` -> UI label `Умный выбор`
- `debate` -> UI label `Дебаты`
- `consensus` -> exact UI label not surfaced; harness records and uses direct POST fallback
- `compare` -> exact UI label not surfaced; harness records and uses direct POST fallback
- `upload` -> not a model-menu pattern; harness uses composer attachment flow and falls back to direct POST only if file input is unavailable

Attachment strategy:
- Primary path: `#file-input`, then submit the prompt through the composer
- Fallback path: multipart POST to `/api/v1/orchestrate/upload`
- No live smoke was executed in this batch; only code paths and evaluator logic were implemented and verified via unit tests

New tests in `tests/test_live_smoke_harness.py`:
- `test_evaluate_accepts_valid_smart_response`
- `test_evaluate_rejects_too_short_answer`
- `test_evaluate_rejects_forbidden_marker`
- `test_evaluate_rejects_missing_topic_keywords_for_smart`
- `test_evaluate_accepts_consensus_with_new_keywords`
- `test_evaluate_skips_topic_check_for_upload`
- `test_evaluate_rejects_when_answer_field_absent`
- `test_evaluate_rejects_non_200_status`
- `test_pattern_defaults_match_matrix`
- `test_argparse_upload_requires_attachment`

Red phase:
- Initial red run on `tests/test_live_smoke_harness.py` failed in five places: missing prompt/evaluation matrices, legacy smart-only evaluator logic, missing `answer field absent` rejection, and non-testable `parse_args()`.
- A later full-suite regression exposed a bad Playwright stub in the new test file; root cause was global `sys.modules` pollution, fixed by switching to `try import / except ModuleNotFoundError`.

Verification:
- `D:\GraceKelly\.venv\Scripts\python.exe -m pytest -q tests/test_live_smoke_harness.py` -> `10 passed`
- `D:\GraceKelly\.venv\Scripts\python.exe -m pytest -q tests/test_live_smoke_harness.py tests/test_playwright_ui_scenarios.py::test_ui_upload_flow_drives_orchestrate_upload tests/test_ui_auth_banner.py::test_sync_auth_banner_shows_server_message_and_trace_id` -> `12 passed`
- `D:\GraceKelly\.venv\Scripts\python.exe -m pytest -q` -> `2647 passed / 0 failed / 6 skipped / 11 subtests passed`
- `D:\GraceKelly\.venv\Scripts\python.exe -m ruff check D:\GraceKelly\src D:\GraceKelly\tests D:\GraceKelly\scripts\live_smart_smoke.py` -> clean
- `D:\GraceKelly\.venv\Scripts\python.exe -m mypy D:\GraceKelly\src` -> `Success: no issues found in 106 source files`

Scope:
- `scripts/live_smart_smoke.py`
- `tests/test_live_smoke_harness.py`

