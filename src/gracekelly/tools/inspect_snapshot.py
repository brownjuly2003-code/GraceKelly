from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from gracekelly.storage.schema import INITIAL_MIGRATION_NAME
from gracekelly.tools.snapshot_artifact import artifact_metadata, checksum_status
from gracekelly.tools.snapshot_digest import SNAPSHOT_FORMAT_VERSION
from gracekelly.tools.snapshot_io import read_snapshot_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect a GraceKelly snapshot artifact without requiring a database connection."
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to a snapshot created by gracekelly-export-postgres.",
    )
    return parser.parse_args()


def load_snapshot(path: Path) -> dict[str, Any]:
    return json.loads(read_snapshot_text(path))


def exported_task_ids(snapshot: dict[str, Any]) -> list[str]:
    explicit_ids = snapshot.get("exported_task_ids")
    if isinstance(explicit_ids, list):
        return [str(task_id) for task_id in explicit_ids]

    derived_ids: list[str] = []
    tasks = snapshot.get("tasks")
    if not isinstance(tasks, list):
        return derived_ids
    for item in tasks:
        if not isinstance(item, dict):
            continue
        task_payload = item.get("task")
        if not isinstance(task_payload, dict):
            continue
        task_id = task_payload.get("task_id")
        if task_id is not None:
            derived_ids.append(str(task_id))
    return derived_ids


def nested_record_count(snapshot: dict[str, Any], key: str) -> int:
    explicit_count = snapshot.get(key)
    if isinstance(explicit_count, int):
        return explicit_count

    total = 0
    tasks = snapshot.get("tasks")
    if not isinstance(tasks, list):
        return total
    nested_key = key.removesuffix("_count") + "s"
    for item in tasks:
        if not isinstance(item, dict):
            continue
        nested_records = item.get(nested_key)
        if isinstance(nested_records, list):
            total += len(nested_records)
    return total


def inspect_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    checksum_state, expected_digest, computed_digest = checksum_status(snapshot)

    format_version = snapshot.get("snapshot_format_version")
    if format_version is None:
        format_status = "unknown"
    elif format_version == SNAPSHOT_FORMAT_VERSION:
        format_status = "current"
    else:
        format_status = "mismatch"

    migration = snapshot.get("migration")
    if migration is None:
        migration_status = "unknown"
    elif migration == INITIAL_MIGRATION_NAME:
        migration_status = "current"
    else:
        migration_status = "mismatch"

    exported_ids = exported_task_ids(snapshot)
    import_ready = (
        checksum_state != "mismatch"
        and format_status != "mismatch"
        and migration_status != "mismatch"
    )
    result = {
        "status": "ok" if import_ready else "error",
        "snapshot_status": snapshot.get("status", "unknown"),
        "snapshot_format_version": snapshot.get("snapshot_format_version"),
        "supported_snapshot_format_version": SNAPSHOT_FORMAT_VERSION,
        "format_status": format_status,
        "gracekelly_version": snapshot.get("gracekelly_version"),
        "migration": snapshot.get("migration"),
        "supported_migration": INITIAL_MIGRATION_NAME,
        "migration_status": migration_status,
        "generated_at": snapshot.get("generated_at"),
        "backend": snapshot.get("backend"),
        "selection": snapshot.get("selection"),
        "task_count": snapshot.get("task_count", len(exported_ids)),
        "step_count": nested_record_count(snapshot, "step_count"),
        "event_count": nested_record_count(snapshot, "event_count"),
        "exported_task_ids": exported_ids,
        "missing_task_ids": list(snapshot.get("missing_task_ids", [])),
        "checksum_status": checksum_state,
        "snapshot_sha256": expected_digest,
        "computed_snapshot_sha256": computed_digest,
        "import_ready": import_ready,
    }
    return result


def main() -> int:
    args = parse_args()
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
        snapshot = load_snapshot(input_path)
        result = inspect_snapshot(snapshot)
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "input": str(input_path),
                    "error": str(exc),
                },
                indent=2,
            )
        )
        return 2

    input_metadata = artifact_metadata(input_path)
    result["input"] = str(input_path)
    result["compressed_input"] = input_metadata["compressed"]
    result["input_size_bytes"] = input_metadata["size_bytes"]
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
