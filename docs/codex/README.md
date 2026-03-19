# Codex Tasks

Задачи для OpenAI Codex agent. Каждый файл — одна задача.

## Формат

Файлы именуются: `NNN-short-name.md` (например `010-embeddings-client.md`).
Нумерация с шагом 10 для вставки промежуточных задач.

## Статусы

- `TODO` — не начата
- `IN_PROGRESS` — Codex работает
- `DONE` — выполнена, проверена, закоммичена
- `BLOCKED` — ждёт зависимость

## Стиль проекта (для всех задач)

- Python >=3.11, `from __future__ import annotations`
- `@dataclass(frozen=True, slots=True)` для immutable data
- `StrEnum` для перечислений
- `unittest.TestCase` для тестов
- 4 пробела, snake_case, без docstrings/комментариев
- Тесты: `python -m pytest -q`
- Платформа: Windows 11
