from __future__ import annotations

import hashlib
import json
from typing import Any

SNAPSHOT_FORMAT_VERSION = 1


def snapshot_without_digest(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in snapshot.items()
        if key != "snapshot_sha256"
    }


def compute_snapshot_sha256(snapshot: dict[str, Any]) -> str:
    encoded = json.dumps(
        snapshot_without_digest(snapshot),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
