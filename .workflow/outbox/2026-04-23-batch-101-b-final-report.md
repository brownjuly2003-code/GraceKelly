# Batch 101-b final report

Completed phases: A+B.

## Diff summary

- `src/gracekelly/api/routes/{smart,smart_v2,debate,consensus,batch,pipeline}.py`: default model changed from `mistral-small` to `claude-sonnet-4-6`.
- `src/gracekelly/api/routes/compare.py`: default model list changed from `["mistral-small"]` to `["claude-sonnet-4-6"]`.
- `src/gracekelly/api/routes/_helpers.py`: execution profile `dry-run` is treated as effective dry-run when selecting adapters.
- `src/gracekelly/core/models.py`: `mistral-small` removed from API model specs and pricing.
- `tests/test_dry_run_propagation.py`: demo model changed to `claude-sonnet-4-6`; added regression coverage for `execution_profile=dry-run` without request `dry_run:true`.

Note: the working tree had unrelated dirty changes before this run, including a pre-existing deletion of `src/gracekelly/adapters/api/mistral.py`. That deletion was not staged by this run.

## Grep verification

`rg '"mistral-small"' src/gracekelly/api`  
Exit code: 1, no matches.

`rg '"mistral-small"' src/gracekelly/core`  
Exit code: 1, no matches.

`rg 'mistral-small' tests/test_dry_run_propagation.py`  
Exit code: 1, no matches.

## Scoped pytest output

Initial spec command did not run on Windows because PowerShell did not expand globs:

```text
ERROR: file or directory not found: tests/test_smart_*.py
no tests ran
```

Equivalent explicit scoped command after the fix:

```text
258 passed, 7 subtests passed in 165.86s (0:02:45)
```

## Smoke curl output

Port `8011` was already occupied by an older Python server, so the verified smoke used `127.0.0.1:8013` with:

```text
GRACEKELLY_EXECUTION_PROFILE=dry-run
python -m uvicorn gracekelly.main:create_app --factory --host 127.0.0.1 --port 8013
```

Result:

```text
SMART_STATUS=200
SMART_PAYLOAD_FIRST_200={"answer":"[dry-run] Simulated response for: 2+2=","task_type":"general","complexity_level":"simple","pattern_used":"single","reliability_level":"quick","was_decomposed":false,"used_consensus":false,"
SMART_MODEL_ID=claude-sonnet-4-6
SMART_HAS_PROVIDER_UNAVAILABLE=False
SMART_HAS_MISTRAL=False
MODELS_STATUS=200
MODELS_HAS_MISTRAL_SMALL=False
```

## Ruff + mypy status

```text
.venv\Scripts\python -m ruff check src tests
All checks passed!

.venv\Scripts\python -m mypy src --strict
Success: no issues found in 105 source files
```

## Full pytest status

The exact root command failed during collection because pytest tried to collect ignored temporary directories:

```text
.venv\Scripts\python -m pytest -q
37 errors during collection
PermissionError: [WinError 5] Access is denied: 'D:\GraceKelly\.tmp\...'
```

Full project test suite under `tests/` passed:

```text
.venv\Scripts\python -m pytest tests -q
2633 passed, 6 skipped, 11 subtests passed in 309.21s (0:05:09)
```

## Escalation notes

An earlier escalation report was written because the batch's `rg '(?i)mistral' src tests docs scripts` rule found many legitimate Mistral references outside Phase A/B scope and the tree was already dirty. The user explicitly instructed to continue, so the final fix and verification proceeded without staging unrelated dirty changes.
