# Batch 85 DOCS Report

Дата: 2026-04-22
Task: DOCS-phase-17-remaining-update
Статус: blocked

## Причина блокировки

- Task зависит от `SMOKE-smart-live-rerun`.
- Live SMART в batch-85 завершился route-level `200`, но acceptance не выполнен: итоговый payload деградировал в `[auth_failed] ...`, `was_decomposed=false`.
- По hard rule batch-а после такого SMART docs не обновляются.

## Итог

- `docs/phased-roadmap.md` не трогался.
- Batch закрывается с diagnostic report вместо roadmap refresh.
