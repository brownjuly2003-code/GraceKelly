# Dry-Run Profile Gate Audit

Date: 2026-04-25
Scope: 8 sync routes from batch-103 at HEAD `7d187fe861698422e9d62c00a53a18cd152ff5ee`

## Static audit

Static grep covered:

- `payload.dry_run`
- `resolve_effective_dry_run`
- submit/adapter resolution paths using `resolve_execution_adapter`, `ExecutionRequest`, or `service.submit_snapshot`

| route | resolve_effective_dry_run usages | raw payload.dry_run in submit paths | classification |
| --- | --- | --- | --- |
| `POST /api/v1/smart` | 1: `src/gracekelly/api/routes/smart.py:82`; adapter resolution uses `effective_dry_run` at `src/gracekelly/api/routes/smart.py:84`; `ExecutionRequest.dry_run` uses `effective_dry_run` at `src/gracekelly/api/routes/smart.py:121` | 0; only gate input at `src/gracekelly/api/routes/smart.py:82` | clean |
| `POST /api/v1/smart_v2` | 1: `src/gracekelly/api/routes/smart_v2.py:91`; adapter resolution uses `effective_dry_run` at `src/gracekelly/api/routes/smart_v2.py:93`; `ExecutionRequest.dry_run` uses `effective_dry_run` at `src/gracekelly/api/routes/smart_v2.py:139` | 0; only gate input at `src/gracekelly/api/routes/smart_v2.py:91` | clean |
| `POST /api/v1/orchestrate` | 2 in route file: JSON submit uses `resolve_effective_dry_run(state, payload.dry_run)` at `src/gracekelly/api/routes/orchestrate.py:256`; upload submit uses `resolve_effective_dry_run(state, dry_run)` at `src/gracekelly/api/routes/orchestrate.py:415` | 0 in submit path; JSON submit copies `dry_run=effective_dry_run` into `payload_for_submission` at `src/gracekelly/api/routes/orchestrate.py:257` and submits that payload at `src/gracekelly/api/routes/orchestrate.py:278` | clean |
| `POST /api/v1/consensus` | 1: `src/gracekelly/api/routes/consensus.py:75`; adapter resolution uses `effective_dry_run` at `src/gracekelly/api/routes/consensus.py:77`; `ExecutionRequest.dry_run` uses `effective_dry_run` at `src/gracekelly/api/routes/consensus.py:92` | 0; only gate input at `src/gracekelly/api/routes/consensus.py:75` | clean |
| `POST /api/v1/debate` | 1: `src/gracekelly/api/routes/debate.py:68`; adapter resolution uses `effective_dry_run` at `src/gracekelly/api/routes/debate.py:70`; `ExecutionRequest.dry_run` uses `effective_dry_run` at `src/gracekelly/api/routes/debate.py:85` | 0; only gate input at `src/gracekelly/api/routes/debate.py:68` | clean |
| `POST /api/v1/compare` | 1: `src/gracekelly/api/routes/compare.py:65`; primary adapter resolution uses `effective_dry_run` at `src/gracekelly/api/routes/compare.py:80`; analysis adapter resolution also uses `effective_dry_run` at `src/gracekelly/api/routes/compare.py:150` | 0; only gate input at `src/gracekelly/api/routes/compare.py:65`; primary `ExecutionRequest.dry_run` uses `effective_dry_run` at `src/gracekelly/api/routes/compare.py:97`; analysis request uses it at `src/gracekelly/api/routes/compare.py:170` | clean |
| `POST /api/v1/batch` | 1: `src/gracekelly/api/routes/batch.py:72`; adapter resolution uses `effective_dry_run` at `src/gracekelly/api/routes/batch.py:74`; `ExecutionRequest.dry_run` uses `effective_dry_run` at `src/gracekelly/api/routes/batch.py:89` | 0; only gate input at `src/gracekelly/api/routes/batch.py:72` | clean |
| `POST /api/v1/pipeline` | 1: `src/gracekelly/api/routes/pipeline.py:74`; adapter resolution uses `effective_dry_run` at `src/gracekelly/api/routes/pipeline.py:76`; `ExecutionRequest.dry_run` uses `effective_dry_run` at `src/gracekelly/api/routes/pipeline.py:106` | 0; only gate input at `src/gracekelly/api/routes/pipeline.py:74` | clean |

Commentary:

- No `broken` or `suspect` sync route was found by static grep.
- `payload.dry_run` is used only as an input to `resolve_effective_dry_run(...)` in the audited JSON route handlers.
- Submit paths either pass `effective_dry_run` into `resolve_execution_adapter(...)` and `ExecutionRequest.dry_run`, or in `/orchestrate` copy it into `payload_for_submission` before calling `service.submit_snapshot(...)`.

## Smoke results

Command profile:

- `GRACEKELLY_EXECUTION_PROFILE=dry-run`
- `uvicorn gracekelly.main:create_app --factory --host 127.0.0.1 --port 8011`
- readiness check: `GET /healthz/ready` returned `200 {"status":"ok"}`

Note: the batch spec labels smart v2 as `POST /api/v1/smart_v2`, but the registered route is `POST /api/v1/smart/v2` at `src/gracekelly/api/routes/smart_v2.py:69`. A direct `POST /api/v1/smart_v2` returned `405 Method Not Allowed`; the smoke verdict below uses the registered route for `smart_v2.py`.

| path | http_status | dry-run marker observed | verdict |
| --- | --- | --- | --- |
| `POST /api/v1/smart` | 200 | yes: response answer contained `[dry-run]` | PASS |
| `POST /api/v1/smart/v2` | 200 | yes: response answer contained `[dry-run]` | PASS |
| `POST /api/v1/orchestrate` | 200 | yes: response contained `execution_mode:"dry-run"` and `adapter_name:"dry-run"` | PASS |
| `POST /api/v1/consensus` | 200 | yes: `best_response` contained `[dry-run]` | PASS |
| `POST /api/v1/debate` | 200 | yes: debate fields contained `[dry-run]` | PASS |
| `POST /api/v1/compare` | 200 | yes: model answers and analysis contained `[dry-run]` | PASS |
| `POST /api/v1/batch` | 200 | yes: batch item answer contained `[dry-run]` | PASS |
| `POST /api/v1/pipeline` | 200 | yes: response answer contained `[dry-run]` | PASS |

No smoke response contained `failure_code:"unknown_error"`. No hotfix was required.
