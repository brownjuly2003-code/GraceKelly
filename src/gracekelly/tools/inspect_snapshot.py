from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from gracekelly.storage.schema import INITIAL_MIGRATION_NAME
from gracekelly.tools.snapshot_artifact import (
    artifact_metadata,
    checksum_status,
    exported_task_ids,
    exported_task_ids_status,
    manifest_count,
    manifest_count_status,
    manifest_status,
    missing_task_ids,
    missing_task_ids_status,
    snapshot_status_consistency_status,
    selection_status,
)
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
    snapshot_manifest_status = manifest_status(snapshot)
    import_ready = (
        checksum_state != "mismatch"
        and format_status != "mismatch"
        and migration_status != "mismatch"
        and snapshot_manifest_status != "mismatch"
    )
    result = {
        "status": "ok" if import_ready else "error",
        "snapshot_status": snapshot.get("status", "unknown"),
        "snapshot_status_consistency_status": snapshot_status_consistency_status(snapshot),
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
        "manifest_status": snapshot_manifest_status,
        "selection_status": selection_status(snapshot),
        "task_count_status": manifest_count_status(snapshot, "task_count"),
        "step_count_status": manifest_count_status(snapshot, "step_count"),
        "event_count_status": manifest_count_status(snapshot, "event_count"),
        "exported_task_ids_status": exported_task_ids_status(snapshot),
        "missing_task_ids_status": missing_task_ids_status(snapshot),
        "task_count": manifest_count(snapshot, "task_count"),
        "step_count": manifest_count(snapshot, "step_count"),
        "event_count": manifest_count(snapshot, "event_count"),
        "exported_task_ids": exported_ids,
        "missing_task_ids": missing_task_ids(snapshot),
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
