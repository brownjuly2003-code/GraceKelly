from __future__ import annotations

import re
from importlib.resources import files
from typing import Iterable, Mapping


INITIAL_MIGRATION_NAME = "0001_initial"

MIGRATION_TRACKING_DDL = """\
CREATE TABLE IF NOT EXISTS gk_schema_migrations (
    name        TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

EXPECTED_SCHEMA_COLUMNS: dict[str, tuple[str, ...]] = {
    "gk_tasks": (
        "task_id",
        "status",
        "accepted_at",
        "completed_at",
        "duration_ms",
        "prompt",
        "reasoning",
        "execution_mode",
        "dry_run",
        "model_count",
        "quorum",
        "merge_strategy",
        "adapter_hint",
        "cancel_on_quorum",
        "failure_code",
        "failure_message",
        "output_text",
        "metadata",
        "retry_of_task_id",
    ),
    "gk_task_steps": (
        "task_id",
        "step_index",
        "model_id",
        "model_display_name",
        "backend",
        "provider",
        "status",
        "failure_code",
        "failure_message",
        "output_text",
        "duration_ms",
    ),
    "gk_task_events": (
        "event_id",
        "task_id",
        "sequence_no",
        "event_type",
        "created_at",
        "payload",
    ),
}


def load_migration_sql(name: str = INITIAL_MIGRATION_NAME) -> str:
    return (
        files("gracekelly.storage")
        .joinpath("migrations", f"{name}.sql")
        .read_text(encoding="ascii")
    )


def discover_migrations() -> list[str]:
    migrations_dir = files("gracekelly.storage").joinpath("migrations")
    names: list[str] = []
    for item in migrations_dir.iterdir():
        item_name = getattr(item, "name", str(item))
        if item_name.endswith(".sql") and re.match(r"^\d{4}_", item_name):
            names.append(item_name.removesuffix(".sql"))
    return sorted(names)


def split_sql_statements(sql: str) -> list[str]:
    return [statement.strip() for statement in sql.split(";") if statement.strip()]


def compute_schema_diff(
    actual_columns: Mapping[str, Iterable[str]],
) -> dict[str, object]:
    normalized_actual = {table: set(columns) for table, columns in actual_columns.items()}
    missing_tables = sorted(
        table for table in EXPECTED_SCHEMA_COLUMNS if table not in normalized_actual
    )
    missing_columns: dict[str, list[str]] = {}

    for table, expected_columns in EXPECTED_SCHEMA_COLUMNS.items():
        if table not in normalized_actual:
            continue
        missing = [
            column for column in expected_columns if column not in normalized_actual[table]
        ]
        if missing:
            missing_columns[table] = missing

    return {
        "missing_tables": missing_tables,
        "missing_columns": missing_columns,
    }
