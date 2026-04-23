# DOCS-close-or-keep

Статус: success

Что сделано:
- В `docs/phased-roadmap.md` удалён Remaining-пункт `Browser adapter non-deterministic selection for the "Best" alias`.
- В Phase 17 Delivered добавлена строка про `batch-88 VERIFY-scoped-menu-vs-orchestrator2` с verdict `PATTERN_EQUIVALENT` и SHA verify-коммита `48b5a93`.
- Два остальных Remaining-пункта (`Cyrillic prompts...`, `AUTH3 persistent session reuse`) оставлены без изменений.

Основание:
- VERIFY-задача в коммите `48b5a93` подтвердила, что scoped-menu-search эквивалентен reference pattern из Orchestrator2 и закрывает nested-text-node ambiguity для Best без отдельного anchor patch.

Scope:
- Изменены только `docs/phased-roadmap.md` и этот report.
