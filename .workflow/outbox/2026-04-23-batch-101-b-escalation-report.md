# Batch 101-b escalation report

Completed phases: escalated before A.

## Diff summary

No code edits were made in this run.

Pre-existing working tree changes were detected before any edit, including Phase A/B target files and out-of-scope files. Notable scope conflict: `src/gracekelly/adapters/api/mistral.py` is already deleted in the working tree, while this batch explicitly says not to delete it.

## Grep verification

`rg 'mistral-small|Field\(default=.*mistral|default_factory=.*mistral' src/gracekelly/api tests src/gracekelly/core`

Exit code: 1, no matches printed.

`rg '(?i)mistral' src tests docs scripts`

Exit code: 0.

## Unexpected mistral references

The batch escalation ladder says to stop if `rg '(?i)mistral' src tests docs scripts` finds references in files outside Phase A/B scope. It found:

```text
tests\test_config.py
docs\architecture.md
docs\comparison\2026-04-23\04-patterns-consensus.md
tests\test_app_startup.py
tests\test_compare_route.py
docs\phased-roadmap.md
docs\comparison\2026-04-23\03-api-behaviour.md
tests\test_account_pool.py
src\gracekelly\app_state.py
src\gracekelly\config.py
src\gracekelly\main.py
docs\comparison\2026-04-23\01-inventory.md
tests\test_event_pagination.py
tests\test_error_schema.py
tests\test_embeddings.py
tests\test_debate_route.py
src\gracekelly\core\embeddings.py
tests\test_config_edge_cases.py
tests\test_config_startup_validation.py
tests\test_main.py
tests\test_file_attachments.py
tests\test_health_detailed.py
tests\test_http_api.py
tests\test_live_multi_model.py
tests\test_model_registry.py
tests\test_orchestrate_timeout.py
tests\test_request_metrics.py
tests\test_postgres_live.py
tests\test_route_inventory.py
tests\test_smart_route.py
tests\test_stream_browser_model.py
```

## Scoped pytest output

Not run because escalation rule triggered before Phase A implementation/verification.

## Smoke curl output

Not run because escalation rule triggered before Phase A implementation/verification.

## Ruff + mypy status

Not run because escalation rule triggered before Phase A implementation/verification.

## Escalation triggered

Reason: unexpected `mistral` references outside Phase A/B scope, plus pre-existing deletion of `src/gracekelly/adapters/api/mistral.py` conflicts with the batch hard rule.

Question: should I continue treating the current dirty working tree as intentional and verify/report it as-is, or should CX first restore/reconcile the out-of-scope Mistral adapter deletion and unrelated dirty files?
