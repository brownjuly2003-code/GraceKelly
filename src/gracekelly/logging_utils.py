from __future__ import annotations

from enum import Enum
import json


def _normalize_log_value(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    return value


def format_log_kv(**context: object) -> str:
    parts: list[str] = []
    for key, raw_value in sorted(context.items()):
        if raw_value is None:
            continue
        value = _normalize_log_value(raw_value)
        if isinstance(value, str):
            rendered = json.dumps(value)
        elif isinstance(value, bool):
            rendered = "true" if value else "false"
        else:
            rendered = str(value)
        parts.append(f"{key}={rendered}")
    return " ".join(parts)


def log_message(event: str, **context: object) -> str:
    details = format_log_kv(**context)
    if not details:
        return event
    return f"{event} {details}"
