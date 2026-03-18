from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from uuid import uuid4

from gracekelly import __version__
from gracekelly.tools import import_postgres
from gracekelly.tools.snapshot_digest import SNAPSHOT_FORMAT_VERSION, compute_snapshot_sha256


class ImportPostgresToolTests(unittest.TestCase):
    def write_snapshot(self, payload: dict[str, object]) -> Path:
        path = Path("tmp") / "test-import-tool" / f"{uuid4()}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
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

    def test_main_returns_error_when_dsn_is_missing(self) -> None:
        with (
            patch.object(
                import_postgres,
                "parse_args",
                return_value=argparse.Namespace(dsn=None, input="snapshot.json", allow_degraded_schema=False, dry_run=False),
            ),
            patch.object(import_postgres, "resolve_dsn", return_value=None),
            patch("builtins.print") as print_mock,
        ):
            code = import_postgres.main()

        self.assertEqual(code, 2)
        payload = json.loads(print_mock.call_args.args[0])
        self.assertEqual(payload["status"], "error")
        self.assertIn("DSN is required", payload["error"])

    def test_main_returns_error_when_snapshot_is_missing(self) -> None:
        with (
            patch.object(
                import_postgres,
                "parse_args",
                return_value=argparse.Namespace(
                    dsn="postgresql://example",
                    input="tmp/test-import-tool/missing.json",
                    allow_degraded_schema=False,
                    dry_run=False,
                ),
            ),
            patch.object(import_postgres, "resolve_dsn", return_value="postgresql://example"),
            patch("builtins.print") as print_mock,
        ):
            code = import_postgres.main()

        self.assertEqual(code, 2)
        payload = json.loads(print_mock.call_args.args[0])
        self.assertEqual(payload["status"], "error")
        self.assertIn("does not exist", payload["error"])

    def test_main_replaces_snapshot_task_bundle(self) -> None:
        accepted_at = datetime(2026, 3, 18, 18, 0, tzinfo=UTC).isoformat().replace("+00:00", "Z")
        snapshot_payload = self.build_snapshot_payload({
            "migration": "0001_initial",
            "tasks": [
                {
                    "task": {
                        "task_id": "task-1",
                        "status": "completed",
                        "accepted_at": accepted_at,
                        "completed_at": accepted_at,
                        "duration_ms": 11,
                        "prompt": "import me",
                        "reasoning": False,
                        "execution_mode": "dry-run",
                        "dry_run": True,
                        "model_count": 1,
                        "quorum": 1,
                        "merge_strategy": "first_success",
                        "adapter_hint": "auto",
                        "cancel_on_quorum": True,
                        "failure_code": None,
                        "failure_message": None,
                        "output_text": None,
                        "metadata": {"trace_id": "imp-1"},
                    },
                    "steps": [
                        {
                            "task_id": "task-1",
                            "step_index": 1,
                            "model_id": "kimi-k2-5",
                            "model_display_name": "Kimi K2.5",
                            "backend": "browser",
                            "provider": "perplexity",
                            "status": "completed",
                            "failure_code": None,
                            "failure_message": None,
                            "output_text": "OK",
                            "duration_ms": 11,
                        }
                    ],
                    "events": [
                        {
                            "event_id": "event-1",
                            "task_id": "task-1",
                            "sequence_no": 1,
                            "event_type": "task.accepted",
                            "created_at": accepted_at,
                            "payload": {"dry_run": True},
                        },
                        {
                            "event_id": "event-2",
                            "task_id": "task-1",
                            "sequence_no": 2,
                            "event_type": "task.completed",
                            "created_at": accepted_at,
                            "payload": {"winning_step_index": 1},
                        },
                    ],
                }
            ],
        })
        snapshot_path = self.write_snapshot(snapshot_payload)

        class FakeRepository:
            def __init__(self, dsn: str, *, bootstrap: bool) -> None:
                self.replaced = []

            def healthcheck(self) -> dict[str, object]:
                return {"status": "ok", "backend": "postgres"}

            def schema_report(self) -> dict[str, object]:
                return {"status": "ok", "backend": "postgres", "schema_version": "0001_initial"}

            def replace_task_snapshot(self, task, steps, events) -> None:
                self.replaced.append((task, steps, events))

        fake_instances: list[FakeRepository] = []

        def build_fake_repository(dsn: str, *, bootstrap: bool):
            repo = FakeRepository(dsn, bootstrap=bootstrap)
            fake_instances.append(repo)
            return repo

        try:
            with (
                patch.object(
                    import_postgres,
                    "parse_args",
                    return_value=argparse.Namespace(
                        dsn="postgresql://example",
                        input=str(snapshot_path),
                        allow_degraded_schema=False,
                        dry_run=False,
                    ),
                ),
                patch.object(import_postgres, "resolve_dsn", return_value="postgresql://example"),
                patch.object(import_postgres, "PostgresTaskRepository", side_effect=build_fake_repository),
                patch("builtins.print") as print_mock,
            ):
                code = import_postgres.main()

            self.assertEqual(code, 0)
            repo = fake_instances[0]
            self.assertEqual(len(repo.replaced), 1)
            task, steps, events = repo.replaced[0]
            self.assertEqual(task.task_id, "task-1")
            self.assertEqual(len(steps), 1)
            self.assertEqual(len(events), 2)
            payload = json.loads(print_mock.call_args.args[0])
            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["snapshot_format_version"], SNAPSHOT_FORMAT_VERSION)
            self.assertEqual(payload["gracekelly_version"], __version__)
            self.assertEqual(payload["source_status"], "ok")
            self.assertEqual(payload["source_gracekelly_version"], __version__)
            self.assertEqual(payload["repository_health"]["status"], "ok")
            self.assertEqual(payload["repository_schema"]["schema_version"], "0001_initial")
            self.assertEqual(payload["imported_task_count"], 1)
            self.assertEqual(payload["imported_step_count"], 1)
            self.assertEqual(payload["imported_event_count"], 2)
            self.assertEqual(payload["replaced_task_ids"], ["task-1"])
        finally:
            if snapshot_path.exists():
                snapshot_path.unlink()

    def test_main_supports_dry_run_without_writing(self) -> None:
        accepted_at = datetime(2026, 3, 18, 18, 0, tzinfo=UTC).isoformat().replace("+00:00", "Z")
        snapshot_payload = self.build_snapshot_payload({
            "migration": "0001_initial",
            "tasks": [
                {
                    "task": {
                        "task_id": "task-1",
                        "status": "completed",
                        "accepted_at": accepted_at,
                        "completed_at": accepted_at,
                        "duration_ms": 11,
                        "prompt": "import me",
                        "reasoning": False,
                        "execution_mode": "dry-run",
                        "dry_run": True,
                        "model_count": 1,
                        "quorum": 1,
                        "merge_strategy": "first_success",
                        "adapter_hint": "auto",
                        "cancel_on_quorum": True,
                        "failure_code": None,
                        "failure_message": None,
                        "output_text": None,
                        "metadata": {},
                    },
                    "steps": [],
                    "events": [
                        {
                            "event_id": "event-1",
                            "task_id": "task-1",
                            "sequence_no": 1,
                            "event_type": "task.accepted",
                            "created_at": accepted_at,
                            "payload": {},
                        }
                    ],
                }
            ],
        })
        snapshot_path = self.write_snapshot(snapshot_payload)

        class FakeRepository:
            def __init__(self, dsn: str, *, bootstrap: bool) -> None:
                self.replace_called = False

            def healthcheck(self) -> dict[str, object]:
                return {"status": "ok", "backend": "postgres"}

            def schema_report(self) -> dict[str, object]:
                return {"status": "ok", "backend": "postgres", "schema_version": "0001_initial"}

            def replace_task_snapshot(self, task, steps, events) -> None:
                self.replace_called = True

        fake_instances: list[FakeRepository] = []

        def build_fake_repository(dsn: str, *, bootstrap: bool):
            repo = FakeRepository(dsn, bootstrap=bootstrap)
            fake_instances.append(repo)
            return repo

        try:
            with (
                patch.object(
                    import_postgres,
                    "parse_args",
                    return_value=argparse.Namespace(
                        dsn="postgresql://example",
                        input=str(snapshot_path),
                        allow_degraded_schema=False,
                        dry_run=True,
                    ),
                ),
                patch.object(import_postgres, "resolve_dsn", return_value="postgresql://example"),
                patch.object(import_postgres, "PostgresTaskRepository", side_effect=build_fake_repository),
                patch("builtins.print") as print_mock,
            ):
                code = import_postgres.main()

            self.assertEqual(code, 0)
            self.assertEqual(len(fake_instances), 1)
            self.assertFalse(fake_instances[0].replace_called)
            payload = json.loads(print_mock.call_args.args[0])
            self.assertEqual(payload["status"], "ok")
            self.assertTrue(payload["dry_run"])
            self.assertEqual(payload["repository_health"]["status"], "ok")
            self.assertEqual(payload["repository_schema"]["schema_version"], "0001_initial")
            self.assertEqual(payload["imported_task_count"], 1)
            self.assertEqual(payload["imported_event_count"], 1)
            self.assertEqual(payload["replaced_task_ids"], ["task-1"])
        finally:
            if snapshot_path.exists():
                snapshot_path.unlink()

    def test_main_blocks_on_degraded_schema_without_override(self) -> None:
        snapshot_path = self.write_snapshot(
            self.build_snapshot_payload(
                {
                    "migration": "0001_initial",
                    "tasks": [],
                }
            )
        )

        class FakeRepository:
            def __init__(self, dsn: str, *, bootstrap: bool) -> None:
                pass

            def healthcheck(self) -> dict[str, object]:
                return {"status": "degraded", "backend": "postgres"}

            def schema_report(self) -> dict[str, object]:
                return {"status": "degraded", "backend": "postgres", "missing_tables": ["gk_task_steps"]}

        try:
            with (
                patch.object(
                    import_postgres,
                    "parse_args",
                    return_value=argparse.Namespace(
                        dsn="postgresql://example",
                        input=str(snapshot_path),
                        allow_degraded_schema=False,
                        dry_run=False,
                    ),
                ),
                patch.object(import_postgres, "resolve_dsn", return_value="postgresql://example"),
                patch.object(import_postgres, "PostgresTaskRepository", FakeRepository),
                patch("builtins.print") as print_mock,
            ):
                code = import_postgres.main()

            self.assertEqual(code, 2)
            payload = json.loads(print_mock.call_args.args[0])
            self.assertEqual(payload["status"], "error")
            self.assertIn("allow-degraded-schema", payload["error"])
        finally:
            if snapshot_path.exists():
                snapshot_path.unlink()

    def test_main_rejects_migration_mismatch(self) -> None:
        snapshot_path = self.write_snapshot(
            self.build_snapshot_payload(
                {
                    "migration": "9999_future",
                    "tasks": [],
                }
            )
        )
        try:
            with (
                patch.object(
                    import_postgres,
                    "parse_args",
                    return_value=argparse.Namespace(
                        dsn="postgresql://example",
                        input=str(snapshot_path),
                        allow_degraded_schema=False,
                        dry_run=False,
                    ),
                ),
                patch.object(import_postgres, "resolve_dsn", return_value="postgresql://example"),
                patch("builtins.print") as print_mock,
            ):
                code = import_postgres.main()

            self.assertEqual(code, 2)
            payload = json.loads(print_mock.call_args.args[0])
            self.assertEqual(payload["status"], "error")
            self.assertIn("does not match expected", payload["error"])
        finally:
            if snapshot_path.exists():
                snapshot_path.unlink()

    def test_main_rejects_checksum_mismatch(self) -> None:
        snapshot_path = self.write_snapshot(
            {
                "status": "ok",
                "snapshot_format_version": SNAPSHOT_FORMAT_VERSION,
                "gracekelly_version": __version__,
                "migration": "0001_initial",
                "snapshot_sha256": "deadbeef",
                "tasks": [],
            }
        )
        try:
            with (
                patch.object(
                    import_postgres,
                    "parse_args",
                    return_value=argparse.Namespace(
                        dsn="postgresql://example",
                        input=str(snapshot_path),
                        allow_degraded_schema=False,
                        dry_run=False,
                    ),
                ),
                patch.object(import_postgres, "resolve_dsn", return_value="postgresql://example"),
                patch("builtins.print") as print_mock,
            ):
                code = import_postgres.main()

            self.assertEqual(code, 2)
            payload = json.loads(print_mock.call_args.args[0])
            self.assertEqual(payload["status"], "error")
            self.assertIn("checksum mismatch", payload["error"])
        finally:
            if snapshot_path.exists():
                snapshot_path.unlink()

    def test_main_rejects_duplicate_task_ids(self) -> None:
        snapshot_payload = self.build_snapshot_payload({
            "migration": "0001_initial",
            "tasks": [
                {"task": {"task_id": "task-1"}, "steps": [], "events": []},
                {"task": {"task_id": "task-1"}, "steps": [], "events": []},
            ],
        })
        snapshot_path = self.write_snapshot(snapshot_payload)
        try:
            with (
                patch.object(
                    import_postgres,
                    "parse_args",
                    return_value=argparse.Namespace(
                        dsn="postgresql://example",
                        input=str(snapshot_path),
                        allow_degraded_schema=False,
                        dry_run=False,
                    ),
                ),
                patch.object(import_postgres, "resolve_dsn", return_value="postgresql://example"),
                patch("builtins.print") as print_mock,
            ):
                code = import_postgres.main()

            self.assertEqual(code, 2)
            payload = json.loads(print_mock.call_args.args[0])
            self.assertEqual(payload["status"], "error")
            self.assertIn("duplicate task_id", payload["error"])
        finally:
            if snapshot_path.exists():
                snapshot_path.unlink()

    def test_main_rejects_duplicate_step_indexes_for_task(self) -> None:
        accepted_at = datetime(2026, 3, 18, 18, 0, tzinfo=UTC).isoformat().replace("+00:00", "Z")
        snapshot_payload = self.build_snapshot_payload({
            "migration": "0001_initial",
            "tasks": [
                {
                    "task": {
                        "task_id": "task-1",
                        "status": "completed",
                        "accepted_at": accepted_at,
                        "completed_at": accepted_at,
                        "duration_ms": 11,
                        "prompt": "import me",
                        "reasoning": False,
                        "execution_mode": "dry-run",
                        "dry_run": True,
                        "model_count": 1,
                        "quorum": 1,
                        "merge_strategy": "first_success",
                        "adapter_hint": "auto",
                        "cancel_on_quorum": True,
                        "failure_code": None,
                        "failure_message": None,
                        "output_text": None,
                        "metadata": {},
                    },
                    "steps": [
                        {
                            "task_id": "task-1",
                            "step_index": 1,
                            "model_id": "kimi-k2-5",
                            "model_display_name": "Kimi K2.5",
                            "backend": "browser",
                            "provider": "perplexity",
                            "status": "completed",
                        },
                        {
                            "task_id": "task-1",
                            "step_index": 1,
                            "model_id": "mistral-small",
                            "model_display_name": "Mistral Small",
                            "backend": "api",
                            "provider": "mistral",
                            "status": "failed",
                        },
                    ],
                    "events": [],
                }
            ],
        })
        snapshot_path = self.write_snapshot(snapshot_payload)

        class FakeRepository:
            def __init__(self, dsn: str, *, bootstrap: bool) -> None:
                pass

            def healthcheck(self) -> dict[str, object]:
                return {"status": "ok", "backend": "postgres"}

            def schema_report(self) -> dict[str, object]:
                return {"status": "ok", "backend": "postgres", "schema_version": "0001_initial"}

            def replace_task_snapshot(self, task, steps, events) -> None:
                raise AssertionError("replace_task_snapshot should not run on invalid input")

        try:
            with (
                patch.object(
                    import_postgres,
                    "parse_args",
                    return_value=argparse.Namespace(
                        dsn="postgresql://example",
                        input=str(snapshot_path),
                        allow_degraded_schema=False,
                        dry_run=False,
                    ),
                ),
                patch.object(import_postgres, "resolve_dsn", return_value="postgresql://example"),
                patch.object(import_postgres, "PostgresTaskRepository", FakeRepository),
                patch("builtins.print") as print_mock,
            ):
                code = import_postgres.main()

            self.assertEqual(code, 2)
            payload = json.loads(print_mock.call_args.args[0])
            self.assertEqual(payload["status"], "error")
            self.assertIn("duplicate step_index", payload["error"])
        finally:
            if snapshot_path.exists():
                snapshot_path.unlink()

    def test_main_rejects_duplicate_event_sequence_numbers_for_task(self) -> None:
        accepted_at = datetime(2026, 3, 18, 18, 0, tzinfo=UTC).isoformat().replace("+00:00", "Z")
        snapshot_payload = self.build_snapshot_payload({
            "migration": "0001_initial",
            "tasks": [
                {
                    "task": {
                        "task_id": "task-1",
                        "status": "completed",
                        "accepted_at": accepted_at,
                        "completed_at": accepted_at,
                        "duration_ms": 11,
                        "prompt": "import me",
                        "reasoning": False,
                        "execution_mode": "dry-run",
                        "dry_run": True,
                        "model_count": 1,
                        "quorum": 1,
                        "merge_strategy": "first_success",
                        "adapter_hint": "auto",
                        "cancel_on_quorum": True,
                        "failure_code": None,
                        "failure_message": None,
                        "output_text": None,
                        "metadata": {},
                    },
                    "steps": [],
                    "events": [
                        {
                            "event_id": "event-1",
                            "task_id": "task-1",
                            "sequence_no": 1,
                            "event_type": "task.accepted",
                            "created_at": accepted_at,
                            "payload": {},
                        },
                        {
                            "event_id": "event-2",
                            "task_id": "task-1",
                            "sequence_no": 1,
                            "event_type": "task.completed",
                            "created_at": accepted_at,
                            "payload": {},
                        },
                    ],
                }
            ],
        })
        snapshot_path = self.write_snapshot(snapshot_payload)

        class FakeRepository:
            def __init__(self, dsn: str, *, bootstrap: bool) -> None:
                pass

            def healthcheck(self) -> dict[str, object]:
                return {"status": "ok", "backend": "postgres"}

            def schema_report(self) -> dict[str, object]:
                return {"status": "ok", "backend": "postgres", "schema_version": "0001_initial"}

            def replace_task_snapshot(self, task, steps, events) -> None:
                raise AssertionError("replace_task_snapshot should not run on invalid input")

        try:
            with (
                patch.object(
                    import_postgres,
                    "parse_args",
                    return_value=argparse.Namespace(
                        dsn="postgresql://example",
                        input=str(snapshot_path),
                        allow_degraded_schema=False,
                        dry_run=False,
                    ),
                ),
                patch.object(import_postgres, "resolve_dsn", return_value="postgresql://example"),
                patch.object(import_postgres, "PostgresTaskRepository", FakeRepository),
                patch("builtins.print") as print_mock,
            ):
                code = import_postgres.main()

            self.assertEqual(code, 2)
            payload = json.loads(print_mock.call_args.args[0])
            self.assertEqual(payload["status"], "error")
            self.assertIn("duplicate event sequence_no", payload["error"])
        finally:
            if snapshot_path.exists():
                snapshot_path.unlink()

    def test_main_rejects_snapshot_format_version_mismatch(self) -> None:
        snapshot_path = self.write_snapshot(
            {
                "status": "ok",
                "snapshot_format_version": SNAPSHOT_FORMAT_VERSION + 1,
                "gracekelly_version": __version__,
                "migration": "0001_initial",
                "tasks": [],
            }
        )
        try:
            with (
                patch.object(
                    import_postgres,
                    "parse_args",
                    return_value=argparse.Namespace(
                        dsn="postgresql://example",
                        input=str(snapshot_path),
                        allow_degraded_schema=False,
                        dry_run=False,
                    ),
                ),
                patch.object(import_postgres, "resolve_dsn", return_value="postgresql://example"),
                patch("builtins.print") as print_mock,
            ):
                code = import_postgres.main()

            self.assertEqual(code, 2)
            payload = json.loads(print_mock.call_args.args[0])
            self.assertEqual(payload["status"], "error")
            self.assertIn("format version", payload["error"])
        finally:
            if snapshot_path.exists():
                snapshot_path.unlink()


if __name__ == "__main__":
    unittest.main()
