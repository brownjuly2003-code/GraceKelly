from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Any

from gracekelly import __version__
from gracekelly.core.contracts import AdapterHint, EventType, ExecutionMode, FailureCode, MergeStrategy, StepStatus, TaskStatus
from gracekelly.storage.base import TaskEventRecord, TaskRecord, TaskStepRecord
from gracekelly.storage.postgres import PostgresTaskRepository
from gracekelly.storage.schema import INITIAL_MIGRATION_NAME
from gracekelly.tools.snapshot_artifact import (
    artifact_metadata,
    checksum_status,
    exported_task_ids,
    manifest_count,
    manifest_status,
    validate_manifest,
)
from gracekelly.tools.snapshot_digest import SNAPSHOT_FORMAT_VERSION, compute_snapshot_sha256
from gracekelly.tools.snapshot_io import read_snapshot_text


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
        "--task-id",
        dest="task_ids",
        action="append",
        default=[],
        help="Specific task_id to restore from the snapshot. Repeat to restore multiple tasks.",
    )
    parser.add_argument(
        "--allow-degraded-schema",
        action="store_true",
        help="Allow import to continue even if repository health or schema report is degraded.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the snapshot and target repository without writing any task data.",
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
    return json.loads(read_snapshot_text(path))


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
    format_version = snapshot.get("snapshot_format_version")
    if format_version is not None and format_version != SNAPSHOT_FORMAT_VERSION:
        raise ValueError(
            f"Snapshot format version '{format_version}' does not match expected '{SNAPSHOT_FORMAT_VERSION}'."
        )
    source_migration = snapshot.get("migration")
    if source_migration is not None and source_migration != INITIAL_MIGRATION_NAME:
        raise ValueError(
            f"Snapshot migration '{source_migration}' does not match expected '{INITIAL_MIGRATION_NAME}'."
        )
    tasks = snapshot.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError("Snapshot must contain a top-level 'tasks' list.")
    task_ids = [item.get("task", {}).get("task_id") for item in tasks]
    duplicate_task_ids = sorted(
        task_id
        for task_id, count in Counter(task_ids).items()
        if task_id is not None and count > 1
    )
    if duplicate_task_ids:
        raise ValueError(f"Snapshot contains duplicate task_id values: {duplicate_task_ids}.")
    validate_manifest(snapshot)
    expected_digest = snapshot.get("snapshot_sha256")
    if expected_digest is not None:
        actual_digest = compute_snapshot_sha256(snapshot)
        if actual_digest != expected_digest:
            raise ValueError(
                f"Snapshot checksum mismatch: expected '{expected_digest}' but computed '{actual_digest}'."
            )


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
    step_indexes = [step.step_index for step in steps]
    duplicate_step_indexes = sorted(
        step_index
        for step_index, count in Counter(step_indexes).items()
        if count > 1
    )
    if duplicate_step_indexes:
        raise ValueError(
            f"Snapshot contains duplicate step_index values for task '{task.task_id}': {duplicate_step_indexes}."
        )
    sequence_nos = [event.sequence_no for event in events]
    duplicate_sequence_nos = sorted(
        sequence_no
        for sequence_no, count in Counter(sequence_nos).items()
        if count > 1
    )
    if duplicate_sequence_nos:
        raise ValueError(
            f"Snapshot contains duplicate event sequence_no values for task '{task.task_id}': {duplicate_sequence_nos}."
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
        repository.replace_task_snapshot(task, steps, events)
        imported_event_count += len(events)
        imported_task_count += 1
        imported_step_count += len(steps)
        replaced_task_ids.append(task.task_id)

    return {
        "imported_task_count": imported_task_count,
        "imported_step_count": imported_step_count,
        "imported_event_count": imported_event_count,
        "replaced_task_ids": replaced_task_ids,
    }


def summarize_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    task_ids: list[str] = []
    step_count = 0
    event_count = 0
    for item in snapshot.get("tasks", []):
        task_payload = item["task"]
        task = _task_from_snapshot(task_payload)
        steps = [_step_from_snapshot(step) for step in item.get("steps", [])]
        events = [_event_from_snapshot(event) for event in item.get("events", [])]
        _validate_task_bundle(task, steps, events)
        task_ids.append(task.task_id)
        step_count += len(steps)
        event_count += len(events)

    return {
        "imported_task_count": len(task_ids),
        "imported_step_count": step_count,
        "imported_event_count": event_count,
        "replaced_task_ids": task_ids,
    }


def select_snapshot_tasks(
    snapshot: dict[str, Any],
    *,
    task_ids: list[str] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    selected_task_ids = list(task_ids or [])
    if not selected_task_ids:
        return snapshot, []

    task_map = {
        item["task"]["task_id"]: item
        for item in snapshot.get("tasks", [])
    }
    selected_tasks: list[dict[str, Any]] = []
    missing_task_ids: list[str] = []
    for task_id in selected_task_ids:
        task_payload = task_map.get(task_id)
        if task_payload is None:
            missing_task_ids.append(task_id)
            continue
        selected_tasks.append(task_payload)

    selected_snapshot = dict(snapshot)
    selected_snapshot["tasks"] = selected_tasks
    return selected_snapshot, missing_task_ids

def main() -> int:
    args = parse_args()
    dsn = resolve_dsn(args.dsn)
    requested_task_ids = list(dict.fromkeys(getattr(args, "task_ids", [])))
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
        selected_snapshot, missing_task_ids = select_snapshot_tasks(snapshot, task_ids=requested_task_ids)
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
        if args.dry_run:
            summary = summarize_snapshot(selected_snapshot)
        else:
            summary = import_snapshot(repository, selected_snapshot)
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

    result_status = "partial" if missing_task_ids else "ok"
    source_checksum_status, source_snapshot_sha256, _ = checksum_status(snapshot)
    input_metadata = artifact_metadata(input_path)
    result = {
        "status": result_status,
        "snapshot_format_version": snapshot.get("snapshot_format_version", SNAPSHOT_FORMAT_VERSION),
        "gracekelly_version": __version__,
        "migration": INITIAL_MIGRATION_NAME,
        "input": str(input_path),
        "compressed_input": input_metadata["compressed"],
        "input_size_bytes": input_metadata["size_bytes"],
        "requested_task_ids": requested_task_ids,
        "missing_task_ids": missing_task_ids,
        "source_status": snapshot.get("status", "unknown"),
        "source_manifest_status": manifest_status(snapshot),
        "source_selection": snapshot.get("selection"),
        "source_task_count": manifest_count(snapshot, "task_count"),
        "source_step_count": manifest_count(snapshot, "step_count"),
        "source_event_count": manifest_count(snapshot, "event_count"),
        "source_exported_task_ids": exported_task_ids(snapshot),
        "source_missing_task_ids": list(snapshot.get("missing_task_ids", [])),
        "source_checksum_status": source_checksum_status,
        "source_snapshot_sha256": source_snapshot_sha256,
        "source_gracekelly_version": snapshot.get("gracekelly_version"),
        "source_migration": snapshot.get("migration"),
        "dry_run": args.dry_run,
        "repository_health": health,
        "repository_schema": schema,
        **summary,
    }
    print(json.dumps(result, indent=2, default=_json_default, sort_keys=True))
    return 0 if result_status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
