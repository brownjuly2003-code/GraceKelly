from __future__ import annotations

from enum import Enum
import json
from typing import Any, Mapping


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


def trace_id_from_metadata(metadata: Mapping[str, Any] | None) -> str | None:
    if metadata is None:
        return None
    value = metadata.get("trace_id")
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value or None
