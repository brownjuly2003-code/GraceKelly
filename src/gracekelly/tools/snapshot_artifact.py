from __future__ import annotations

from pathlib import Path
from typing import Any

from gracekelly.tools.snapshot_digest import compute_snapshot_sha256


def artifact_metadata(path: Path) -> dict[str, object]:
    return {
        "compressed": path.suffix == ".gz",
        "size_bytes": path.stat().st_size,
    }


def checksum_status(snapshot: dict[str, Any]) -> tuple[str, str | None, str]:
    expected_digest = snapshot.get("snapshot_sha256")
    computed_digest = compute_snapshot_sha256(snapshot)
    if expected_digest is None:
        return "missing", None, computed_digest
    if expected_digest == computed_digest:
        return "verified", expected_digest, computed_digest
    return "mismatch", str(expected_digest), computed_digest


def has_task_list(snapshot: dict[str, Any]) -> bool:
    return isinstance(snapshot.get("tasks"), list)


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


def derived_task_count(snapshot: dict[str, Any]) -> int:
    tasks = snapshot.get("tasks")
    if not isinstance(tasks, list):
        return 0
    return len(tasks)


def derived_nested_count(snapshot: dict[str, Any], key: str) -> int:
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


def manifest_count(snapshot: dict[str, Any], key: str) -> int:
    explicit_count = snapshot.get(key)
    if isinstance(explicit_count, int):
        return explicit_count
    if key == "task_count":
        return derived_task_count(snapshot)
    return derived_nested_count(snapshot, key)


def manifest_count_status(snapshot: dict[str, Any], key: str) -> str:
    if not has_task_list(snapshot):
        return "mismatch"
    explicit_count = snapshot.get(key)
    derived_count = manifest_count({"tasks": snapshot.get("tasks")}, key)
    if explicit_count is None:
        return "derived"
    if not isinstance(explicit_count, int):
        return "mismatch"
    if explicit_count == derived_count:
        return "verified"
    return "mismatch"


def exported_task_ids_status(snapshot: dict[str, Any]) -> str:
    if not has_task_list(snapshot):
        return "mismatch"
    explicit_ids = snapshot.get("exported_task_ids")
    derived_ids = exported_task_ids({"tasks": snapshot.get("tasks")})
    if explicit_ids is None:
        return "derived"
    if not isinstance(explicit_ids, list):
        return "mismatch"
    normalized_ids = [str(task_id) for task_id in explicit_ids]
    if normalized_ids == derived_ids:
        return "verified"
    return "mismatch"


def manifest_status(snapshot: dict[str, Any]) -> str:
    statuses = [
        manifest_count_status(snapshot, "task_count"),
        manifest_count_status(snapshot, "step_count"),
        manifest_count_status(snapshot, "event_count"),
        exported_task_ids_status(snapshot),
    ]
    return "mismatch" if "mismatch" in statuses else "verified"


def validate_manifest(snapshot: dict[str, Any]) -> None:
    for key in ("task_count", "step_count", "event_count"):
        if manifest_count_status(snapshot, key) == "mismatch":
            expected = snapshot.get(key)
            derived = manifest_count({"tasks": snapshot.get("tasks")}, key)
            raise ValueError(f"Snapshot {key} value '{expected}' does not match derived '{derived}'.")
    if exported_task_ids_status(snapshot) == "mismatch":
        raise ValueError(
            "Snapshot exported_task_ids do not match task bundles in the artifact."
        )
