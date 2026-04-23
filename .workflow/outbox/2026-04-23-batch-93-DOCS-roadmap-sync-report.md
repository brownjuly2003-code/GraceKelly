# DOCS-roadmap-sync

Статус: success

Что сделано:
- В `docs/phased-roadmap.md` обновлён header `Last updated` на audit-sync формулировку для 2026-04-23.
- `Phase 2` переведён из `partial` в `complete`; добавлен блок `Delivered after Phase 2 closing` с `batch-91 HARNESS-expand-patterns` и SHA `a76b632`, `b965c3c`.
- `Phase 4` переведён из `partial` в `complete`; добавлен блок `Delivered after Phase 4 closing` с `batch-89`, `batch-90` и текущим `batch-93` core-коммитом `8803a0c`.
- Название env для per-IP rate limit синхронизировано с кодом: `GRACEKELLY_RATE_LIMIT_PER_MINUTE` -> `GRACEKELLY_RATE_LIMIT_RPM`.
- Ложный пункт `CORS support (configurable origins, credentials, CORS middleware)` удалён полностью.
- Оставшиеся пункты `Phase 17` про Cyrillic harness encoding и `AUTH3 persistent session reuse` не тронуты, как и требовал batch.

Проверка:
- `rg -n "Last updated|Status: complete|GRACEKELLY_RATE_LIMIT_RPM|batch-91 HARNESS-expand-patterns|batch-89 CORE-model-fallback-policy|batch-90 CORE-request-budget-browser|batch-93 CORE-inject-settings-into-router|Cyrillic prompts|AUTH3" docs/phased-roadmap.md` подтвердил все новые строки и то, что Phase 17 Remaining сохранён.
- `rg -n "GRACEKELLY_RATE_LIMIT_PER_MINUTE" docs/phased-roadmap.md` -> no matches.
- `rg -n "CORS support" docs/phased-roadmap.md` -> no matches.

Scope:
- `docs/phased-roadmap.md`
