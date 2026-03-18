from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Any

from gracekelly.core.contracts import AdapterHint, EventType, ExecutionMode, FailureCode, MergeStrategy, StepStatus, TaskStatus
from gracekelly.storage.base import TaskEventRecord, TaskRecord, TaskStepRecord
from gracekelly.storage.postgres import PostgresTaskRepository
from gracekelly.storage.schema import INITIAL_MIGRATION_NAME


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import a GraceKelly PostgreSQL JSON snapshot into the active PostgreSQL backend."
    )
    parser.add_argument(
        "--dsn",
        help="PostgreSQL DSN. Falls back to GRACEKELLY_POSTGRES_DSN.",
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to a snapshot created by gracekelly-export-postgres.",
    )
    parser.add_argument(
        "--allow-degraded-schema",
        action="store_true",
        help="Allow import to continue even if repository health or schema report is degraded.",
    )
    return parser.parse_args()


def resolve_dsn(cli_dsn: str | None) -> str | None:
    return cli_dsn or os.getenv("GRACEKELLY_POSTGRES_DSN")


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _load_snapshot(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _task_from_snapshot(payload: dict[str, Any]) -> TaskRecord:
    return TaskRecord(
        task_id=payload["task_id"],
        status=TaskStatus(payload["status"]),
        accepted_at=_parse_datetime(payload["accepted_at"]),
        completed_at=_parse_datetime(payload.get("completed_at")),
        duration_ms=payload.get("duration_ms"),
        prompt=payload["prompt"],
        reasoning=payload["reasoning"],
        execution_mode=ExecutionMode(payload["execution_mode"]),
        dry_run=payload["dry_run"],
        model_count=payload["model_count"],
        quorum=payload["quorum"],
        merge_strategy=MergeStrategy(payload["merge_strategy"]),
        adapter_hint=AdapterHint(payload["adapter_hint"]),
        cancel_on_quorum=payload["cancel_on_quorum"],
        failure_code=FailureCode(payload["failure_code"]) if payload.get("failure_code") is not None else None,
        failure_message=payload.get("failure_message"),
        output_text=payload.get("output_text"),
        metadata=dict(payload.get("metadata", {})),
    )


def _step_from_snapshot(payload: dict[str, Any]) -> TaskStepRecord:
    return TaskStepRecord(
        task_id=payload["task_id"],
        step_index=payload["step_index"],
        model_id=payload["model_id"],
        model_display_name=payload["model_display_name"],
        backend=payload["backend"],
        provider=payload["provider"],
        status=StepStatus(payload["status"]),
        failure_code=FailureCode(payload["failure_code"]) if payload.get("failure_code") is not None else None,
        failure_message=payload.get("failure_message"),
        output_text=payload.get("output_text"),
        duration_ms=payload.get("duration_ms"),
    )


def _event_from_snapshot(payload: dict[str, Any]) -> TaskEventRecord:
    return TaskEventRecord(
        event_id=payload["event_id"],
        task_id=payload["task_id"],
        sequence_no=payload["sequence_no"],
        event_type=EventType(payload["event_type"]),
        created_at=_parse_datetime(payload["created_at"]),
        payload=dict(payload.get("payload", {})),
    )


def _validate_snapshot(snapshot: dict[str, Any]) -> None:
    if snapshot.get("status") == "error":
        raise ValueError("Snapshot status is 'error'; refusing to import a failed export artifact.")
    source_migration = snapshot.get("migration")
    if source_migration is not None and source_migration != INITIAL_MIGRATION_NAME:
        raise ValueError(
            f"Snapshot migration '{source_migration}' does not match expected '{INITIAL_MIGRATION_NAME}'."
        )
    tasks = snapshot.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError("Snapshot must contain a top-level 'tasks' list.")


def _validate_task_bundle(
    task: TaskRecord,
    steps: list[TaskStepRecord],
    events: list[TaskEventRecord],
) -> None:
    invalid_step_indexes = [step.step_index for step in steps if step.task_id != task.task_id]
    if invalid_step_indexes:
        raise ValueError(
            f"Snapshot contains steps for task_id values that do not match '{task.task_id}': {invalid_step_indexes}."
        )
    invalid_event_sequences = [event.sequence_no for event in events if event.task_id != task.task_id]
    if invalid_event_sequences:
        raise ValueError(
            f"Snapshot contains events for task_id values that do not match '{task.task_id}': {invalid_event_sequences}."
        )


def import_snapshot(repository, snapshot: dict[str, Any]) -> dict[str, Any]:
    imported_task_count = 0
    imported_step_count = 0
    imported_event_count = 0
    replaced_task_ids: list[str] = []

    for item in snapshot.get("tasks", []):
        task = _task_from_snapshot(item["task"])
        steps = [_step_from_snapshot(step) for step in item.get("steps", [])]
        events = [_event_from_snapshot(event) for event in item.get("events", [])]
        _validate_task_bundle(task, steps, events)
        if hasattr(repository, "replace_task_snapshot"):
            repository.replace_task_snapshot(task, steps, events)
            imported_event_count += len(events)
        else:
            repository.save_task_with_steps(task, steps)
            existing_sequence_nos = {
                event.sequence_no
                for event in repository.list_events(task.task_id)
            }
            for event in events:
                if event.sequence_no in existing_sequence_nos:
                    continue
                repository.append_event(event)
                imported_event_count += 1
        imported_task_count += 1
        imported_step_count += len(steps)
        replaced_task_ids.append(task.task_id)

    return {
        "imported_task_count": imported_task_count,
        "imported_step_count": imported_step_count,
        "imported_event_count": imported_event_count,
        "replaced_task_ids": replaced_task_ids,
    }


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

    input_path = Path(args.input)
    if not input_path.exists():
        print(
            json.dumps(
                {
                    "status": "error",
                    "error": f"Snapshot file '{input_path}' does not exist.",
                },
                indent=2,
            )
        )
        return 2

    try:
        snapshot = _load_snapshot(input_path)
        _validate_snapshot(snapshot)
        repository = PostgresTaskRepository(dsn, bootstrap=False)
        health = repository.healthcheck()
        schema = repository.schema_report()
        if not args.allow_degraded_schema and (health["status"] != "ok" or schema["status"] != "ok"):
            print(
                json.dumps(
                    {
                        "status": "error",
                        "migration": INITIAL_MIGRATION_NAME,
                        "error": "Repository health or schema report is degraded; rerun with --allow-degraded-schema to override.",
                        "health": health,
                        "schema": schema,
                    },
                    indent=2,
                    default=str,
                    sort_keys=True,
                )
            )
            return 2
        summary = import_snapshot(repository, snapshot)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "migration": INITIAL_MIGRATION_NAME,
                    "input": str(input_path),
                    "error": str(exc),
                },
                indent=2,
            )
        )
        return 2

    result = {
        "status": "ok",
        "migration": INITIAL_MIGRATION_NAME,
        "input": str(input_path),
        "source_status": snapshot.get("status", "unknown"),
        "source_migration": snapshot.get("migration"),
        **summary,
    }
    print(json.dumps(result, indent=2, default=_json_default, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
