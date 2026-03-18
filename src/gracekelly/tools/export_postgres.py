from __future__ import annotations

import argparse
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from typing import Any

from gracekelly.storage.postgres import PostgresTaskRepository
from gracekelly.storage.schema import INITIAL_MIGRATION_NAME
from gracekelly.tools.snapshot_digest import compute_snapshot_sha256


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export GraceKelly PostgreSQL tasks, steps, and events into a JSON snapshot."
    )
    parser.add_argument(
        "--dsn",
        help="PostgreSQL DSN. Falls back to GRACEKELLY_POSTGRES_DSN.",
    )
    parser.add_argument(
        "--output",
        help="Output file path. Defaults to tmp/postgres-export/gracekelly-export-<timestamp>.json.",
    )
    parser.add_argument(
        "--task-id",
        dest="task_ids",
        action="append",
        default=[],
        help="Specific task_id to export. Repeat to export multiple tasks.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Recent-task export limit when --task-id is not provided. Defaults to 100.",
    )
    return parser.parse_args()


def resolve_dsn(cli_dsn: str | None) -> str | None:
    return cli_dsn or os.getenv("GRACEKELLY_POSTGRES_DSN")


def default_output_path(now: datetime | None = None) -> Path:
    timestamp = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    return Path("tmp") / "postgres-export" / f"gracekelly-export-{timestamp}.json"


def _normalize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, str):
        return enum_value
    return value


def serialize_record(record: Any) -> dict[str, Any]:
    if is_dataclass(record):
        return _normalize(asdict(record))
    raise TypeError(f"Expected dataclass record, got {type(record).__name__}")


def collect_export_snapshot(
    repository,
    *,
    task_ids: list[str] | None = None,
    limit: int = 100,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    selected_task_ids = list(task_ids or [])
    exported_tasks: list[dict[str, Any]] = []
    missing_task_ids: list[str] = []

    if selected_task_ids:
        for task_id in selected_task_ids:
            task = repository.get(task_id)
            if task is None:
                missing_task_ids.append(task_id)
                continue
            exported_tasks.append(
                {
                    "task": serialize_record(task),
                    "steps": [serialize_record(item) for item in repository.list_steps(task_id)],
                    "events": [serialize_record(item) for item in repository.list_events(task_id)],
                }
            )
    else:
        for task in repository.list_recent(limit):
            exported_tasks.append(
                {
                    "task": serialize_record(task),
                    "steps": [serialize_record(item) for item in repository.list_steps(task.task_id)],
                    "events": [serialize_record(item) for item in repository.list_events(task.task_id)],
                }
            )

    health = repository.healthcheck()
    schema = repository.schema_report()
    status = "partial" if missing_task_ids else "ok"
    snapshot = {
        "status": status,
        "migration": INITIAL_MIGRATION_NAME,
        "generated_at": _normalize(generated_at or datetime.now(UTC)),
        "backend": repository.backend_name,
        "selection": {
            "task_ids": selected_task_ids,
            "limit": None if selected_task_ids else limit,
        },
        "health": _normalize(health),
        "schema": _normalize(schema),
        "task_count": len(exported_tasks),
        "missing_task_ids": missing_task_ids,
        "tasks": exported_tasks,
    }
    snapshot["snapshot_sha256"] = compute_snapshot_sha256(snapshot)
    return snapshot


def write_snapshot(path: Path, snapshot: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    args = parse_args()
    dsn = resolve_dsn(args.dsn)
    if not dsn:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": "A PostgreSQL DSN is required via --dsn or GRACEKELLY_POSTGRES_DSN.",
                },
                indent=2,
            )
        )
        return 2
    if args.limit < 1:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": "--limit must be at least 1.",
                },
                indent=2,
            )
        )
        return 2

    output_path = Path(args.output) if args.output else default_output_path()

    try:
        repository = PostgresTaskRepository(dsn, bootstrap=False)
        snapshot = collect_export_snapshot(
            repository,
            task_ids=args.task_ids,
            limit=args.limit,
        )
        write_snapshot(output_path, snapshot)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "migration": INITIAL_MIGRATION_NAME,
                    "error": str(exc),
                    "output": str(output_path),
                },
                indent=2,
            )
        )
        return 2

    result = {
        "status": snapshot["status"],
        "migration": INITIAL_MIGRATION_NAME,
        "output": str(output_path),
        "task_count": snapshot["task_count"],
        "missing_task_ids": snapshot["missing_task_ids"],
        "snapshot_sha256": snapshot["snapshot_sha256"],
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if snapshot["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
