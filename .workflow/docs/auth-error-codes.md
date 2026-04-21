# Auth Error Codes

## Context

Browser auth failures currently surface through two layers:

- Sync HTTP responses return `model_auth_required`.
- Persisted task records keep `failure_code="auth_failed"`.

## Why Two Codes

`auth_failed` is the existing stored failure code in task snapshots and database-backed flows.
`model_auth_required` is the HTTP-facing code used by sync endpoints to tell clients that operator action is required.

## Mapping

| Surface | Code | Meaning |
| --- | --- | --- |
| Sync HTTP 503 detail/code | `model_auth_required` | Browser session expired or missing login |
| Async task `failure_code` | `auth_failed` | Same auth problem after polling task state |

## Client Handling Guide

- Treat both codes as one auth-required state in the UI.
- Prefer server-provided `message` and `trace_id` when present.
- Keep retry behavior on the client side; no schema expansion is required.

## Migration Note

This mapping is intentional compatibility glue. Do not rename `FailureCode.AUTH_FAILED` without a storage migration.
