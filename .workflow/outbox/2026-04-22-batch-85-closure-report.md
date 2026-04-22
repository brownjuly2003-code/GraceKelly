# Batch 85 Closure Report

Дата: 2026-04-22
Task: closure
Статус: success

## Workflow

- `.workflow/outbox/.done` обновлён на завершение batch-85 с `exit_code=1`, потому что SMART smoke не прошёл acceptance.
- `.workflow/inbox/.ready` очищен.
- `2026-04-22-batch-85.md` перемещён из `.workflow/inbox/` в `.workflow/done/`.

## Batch outcome

- `ADAPTER-raise-call-timeout` выполнен успешно: adapter-level timeout поднят до `120s`, full suite зелёный (`2594 passed / 6 skipped`).
- `SMOKE-smart-live-rerun` завершился diagnostic failure: timeout regression снят, но smart flow вернул `[auth_failed]` вместо осмысленного результата.
- `DOCS-phase-17-remaining-update` пропущен по hard rule batch-а.
