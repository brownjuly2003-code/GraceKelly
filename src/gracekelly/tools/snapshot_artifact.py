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
