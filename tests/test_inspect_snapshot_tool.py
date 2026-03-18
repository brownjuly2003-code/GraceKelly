from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import uuid4

from gracekelly import __version__
from gracekelly.tools import inspect_snapshot
from gracekelly.tools.snapshot_digest import SNAPSHOT_FORMAT_VERSION, compute_snapshot_sha256


class InspectSnapshotToolTests(unittest.TestCase):
    def write_snapshot(self, payload: dict[str, object]) -> Path:
        path = Path("tmp") / "test-inspect-snapshot-tool" / f"{uuid4()}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def write_gzip_snapshot(self, payload: dict[str, object]) -> Path:
        path = Path("tmp") / "test-inspect-snapshot-tool" / f"{uuid4()}.json.gz"
        path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        return path

    def build_snapshot_payload(self, payload: dict[str, object]) -> dict[str, object]:
        snapshot = {
            "status": "ok",
            "snapshot_format_version": SNAPSHOT_FORMAT_VERSION,
            "gracekelly_version": __version__,
            **payload,
        }
        snapshot["snapshot_sha256"] = compute_snapshot_sha256(snapshot)
        return snapshot

    def test_main_returns_error_when_snapshot_is_missing(self) -> None:
        with (
            patch.object(
                inspect_snapshot,
                "parse_args",
                return_value=argparse.Namespace(input="tmp/test-inspect-snapshot-tool/missing.json"),
            ),
            patch("builtins.print") as print_mock,
        ):
            code = inspect_snapshot.main()

        self.assertEqual(code, 2)
        payload = json.loads(print_mock.call_args.args[0])
        self.assertEqual(payload["status"], "error")
        self.assertIn("does not exist", payload["error"])

    def test_main_inspects_snapshot_and_verifies_checksum(self) -> None:
        snapshot_path = self.write_snapshot(
            self.build_snapshot_payload(
                {
                    "migration": "0001_initial",
                    "generated_at": "2026-03-18T18:00:00Z",
                    "backend": "postgres",
                    "selection": {"task_ids": ["task-1"], "limit": None},
                    "task_count": 1,
                    "exported_task_ids": ["task-1"],
                    "missing_task_ids": [],
                    "tasks": [{"task": {"task_id": "task-1"}, "steps": [], "events": []}],
                }
            )
        )
        try:
            with (
                patch.object(inspect_snapshot, "parse_args", return_value=argparse.Namespace(input=str(snapshot_path))),
                patch("builtins.print") as print_mock,
            ):
                code = inspect_snapshot.main()

            self.assertEqual(code, 0)
            payload = json.loads(print_mock.call_args.args[0])
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["snapshot_status"], "ok")
            self.assertEqual(payload["checksum_status"], "verified")
            self.assertEqual(payload["format_status"], "current")
            self.assertEqual(payload["migration_status"], "current")
            self.assertTrue(payload["import_ready"])
            self.assertEqual(payload["exported_task_ids"], ["task-1"])
            self.assertEqual(payload["task_count"], 1)
            self.assertFalse(payload["compressed_input"])
        finally:
            if snapshot_path.exists():
                snapshot_path.unlink()

    def test_main_derives_task_ids_when_manifest_field_is_missing(self) -> None:
        snapshot_path = self.write_gzip_snapshot(
            self.build_snapshot_payload(
                {
                    "migration": "0001_initial",
                    "tasks": [
                        {"task": {"task_id": "task-1"}, "steps": [], "events": []},
                        {"task": {"task_id": "task-2"}, "steps": [], "events": []},
                    ],
                }
            )
        )
        try:
            with (
                patch.object(inspect_snapshot, "parse_args", return_value=argparse.Namespace(input=str(snapshot_path))),
                patch("builtins.print") as print_mock,
            ):
                code = inspect_snapshot.main()

            self.assertEqual(code, 0)
            payload = json.loads(print_mock.call_args.args[0])
            self.assertEqual(payload["exported_task_ids"], ["task-1", "task-2"])
            self.assertEqual(payload["task_count"], 2)
            self.assertEqual(payload["format_status"], "current")
            self.assertTrue(payload["compressed_input"])
        finally:
            if snapshot_path.exists():
                snapshot_path.unlink()

    def test_main_reports_checksum_mismatch(self) -> None:
        snapshot_path = self.write_snapshot(
            {
                "status": "ok",
                "snapshot_format_version": SNAPSHOT_FORMAT_VERSION,
                "gracekelly_version": __version__,
                "migration": "0001_initial",
                "tasks": [],
                "snapshot_sha256": "deadbeef",
            }
        )
        try:
            with (
                patch.object(inspect_snapshot, "parse_args", return_value=argparse.Namespace(input=str(snapshot_path))),
                patch("builtins.print") as print_mock,
            ):
                code = inspect_snapshot.main()

            self.assertEqual(code, 1)
            payload = json.loads(print_mock.call_args.args[0])
            self.assertEqual(payload["status"], "error")
            self.assertEqual(payload["checksum_status"], "mismatch")
            self.assertFalse(payload["import_ready"])
            self.assertEqual(payload["snapshot_sha256"], "deadbeef")
            self.assertNotEqual(payload["computed_snapshot_sha256"], "deadbeef")
        finally:
            if snapshot_path.exists():
                snapshot_path.unlink()

    def test_main_reports_format_and_migration_mismatch(self) -> None:
        snapshot_path = self.write_snapshot(
            self.build_snapshot_payload(
                {
                    "snapshot_format_version": SNAPSHOT_FORMAT_VERSION + 1,
                    "migration": "9999_future",
                    "tasks": [],
                }
            )
        )
        try:
            with (
                patch.object(inspect_snapshot, "parse_args", return_value=argparse.Namespace(input=str(snapshot_path))),
                patch("builtins.print") as print_mock,
            ):
                code = inspect_snapshot.main()

            self.assertEqual(code, 1)
            payload = json.loads(print_mock.call_args.args[0])
            self.assertEqual(payload["status"], "error")
            self.assertEqual(payload["format_status"], "mismatch")
            self.assertEqual(payload["migration_status"], "mismatch")
            self.assertFalse(payload["import_ready"])
        finally:
            if snapshot_path.exists():
                snapshot_path.unlink()


if __name__ == "__main__":
    unittest.main()
