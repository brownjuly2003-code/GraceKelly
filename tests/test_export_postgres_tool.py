from __future__ import annotations

import argparse
import gzip
import json
import os
import unittest
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from gracekelly import __version__
from gracekelly.storage.base import TaskEventRecord, TaskRecord, TaskStepRecord
from gracekelly.tools import export_postgres
from gracekelly.tools.snapshot_digest import SNAPSHOT_FORMAT_VERSION, compute_snapshot_sha256


class NormalizeTests(unittest.TestCase):
    def test_datetime_converted_to_iso_z(self) -> None:
        dt = datetime(2026, 3, 18, 17, 0, 0, tzinfo=UTC)
        self.assertEqual(export_postgres._normalize(dt), "2026-03-18T17:00:00Z")

    def test_datetime_utcoffset_replaced_with_z(self) -> None:
        result = export_postgres._normalize(datetime(2026, 1, 1, tzinfo=UTC))
        self.assertTrue(result.endswith("Z"))
        self.assertNotIn("+00:00", result)

    def test_dict_values_normalized_recursively(self) -> None:
        dt = datetime(2026, 3, 18, tzinfo=UTC)
        result = export_postgres._normalize({"ts": dt, "x": 1})
        self.assertTrue(result["ts"].endswith("Z"))
        self.assertEqual(result["x"], 1)

    def test_list_items_normalized(self) -> None:
        dt = datetime(2026, 3, 18, tzinfo=UTC)
        result = export_postgres._normalize([dt, "hello"])
        self.assertTrue(result[0].endswith("Z"))
        self.assertEqual(result[1], "hello")

    def test_tuple_items_normalized(self) -> None:
        result = export_postgres._normalize(("a", "b"))
        self.assertEqual(result, ["a", "b"])

    def test_str_enum_returns_value(self) -> None:
        class Status(StrEnum):
            OK = "ok"

        self.assertEqual(export_postgres._normalize(Status.OK), "ok")

    def test_plain_string_unchanged(self) -> None:
        self.assertEqual(export_postgres._normalize("hello"), "hello")

    def test_integer_unchanged(self) -> None:
        self.assertEqual(export_postgres._normalize(42), 42)

    def test_none_unchanged(self) -> None:
        self.assertIsNone(export_postgres._normalize(None))


class SerializeRecordTests(unittest.TestCase):
    def test_dataclass_serialized(self) -> None:
        @dataclass
        class Rec:
            name: str
            count: int

        result = export_postgres.serialize_record(Rec(name="test", count=3))
        self.assertEqual(result, {"name": "test", "count": 3})

    def test_non_dataclass_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            export_postgres.serialize_record({"not": "a dataclass"})

    def test_datetime_field_normalized(self) -> None:
        @dataclass
        class Rec:
            ts: datetime

        result = export_postgres.serialize_record(Rec(ts=datetime(2026, 3, 18, tzinfo=UTC)))
        self.assertTrue(result["ts"].endswith("Z"))


class ResolveDsnTests(unittest.TestCase):
    def test_cli_dsn_takes_precedence(self) -> None:
        with patch.dict(os.environ, {"GRACEKELLY_POSTGRES_DSN": "env-dsn"}, clear=False):
            self.assertEqual(export_postgres.resolve_dsn("cli-dsn"), "cli-dsn")

    def test_falls_back_to_env_var(self) -> None:
        with patch.dict(os.environ, {"GRACEKELLY_POSTGRES_DSN": "env-dsn"}, clear=False):
            self.assertEqual(export_postgres.resolve_dsn(None), "env-dsn")

    def test_returns_none_when_both_missing(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "GRACEKELLY_POSTGRES_DSN"}
        with patch.dict(os.environ, env, clear=True):
            self.assertIsNone(export_postgres.resolve_dsn(None))


class DefaultOutputPathTests(unittest.TestCase):
    def test_path_includes_timestamp(self) -> None:
        dt = datetime(2026, 3, 18, 17, 5, 30, tzinfo=UTC)
        path = export_postgres.default_output_path(dt)
        self.assertIn("20260318T170530Z", str(path))

    def test_path_is_under_tmp_postgres_export(self) -> None:
        dt = datetime(2026, 3, 18, tzinfo=UTC)
        path = export_postgres.default_output_path(dt)
        self.assertTrue(str(path).startswith(str(Path("tmp") / "postgres-export")))

    def test_path_has_json_extension(self) -> None:
        dt = datetime(2026, 3, 18, tzinfo=UTC)
        self.assertTrue(export_postgres.default_output_path(dt).suffix == ".json")

    def test_no_datetime_uses_current_time(self) -> None:
        path = export_postgres.default_output_path()
        self.assertIn("gracekelly-export-", path.name)


class ExportPostgresToolTests(unittest.TestCase):
    def test_main_returns_error_when_dsn_is_missing(self) -> None:
        with (
            patch.object(
                export_postgres,
                "parse_args",
                return_value=argparse.Namespace(dsn=None, output=None, task_ids=[], limit=100),
            ),
            patch.object(export_postgres, "resolve_dsn", return_value=None),
            patch("builtins.print") as print_mock,
        ):
            code = export_postgres.main()

        self.assertEqual(code, 2)
        payload = json.loads(print_mock.call_args.args[0])
        self.assertEqual(payload["status"], "error")
        self.assertIn("DSN is required", payload["error"])

    def test_main_returns_error_when_limit_is_invalid(self) -> None:
        with (
            patch.object(
                export_postgres,
                "parse_args",
                return_value=argparse.Namespace(dsn="postgresql://example", output=None, task_ids=[], limit=0),
            ),
            patch.object(export_postgres, "resolve_dsn", return_value="postgresql://example"),
            patch("builtins.print") as print_mock,
        ):
            code = export_postgres.main()

        self.assertEqual(code, 2)
        payload = json.loads(print_mock.call_args.args[0])
        self.assertEqual(payload["status"], "error")
        self.assertIn("--limit must be at least 1", payload["error"])

    def test_collect_export_snapshot_includes_nested_steps_and_events(self) -> None:
        from gracekelly.core.contracts import (
            AdapterHint,
            EventType,
            ExecutionMode,
            MergeStrategy,
            StepStatus,
            TaskStatus,
        )
        from gracekelly.storage.base import TaskEventRecord, TaskRecord, TaskStepRecord
        from gracekelly.storage.memory import InMemoryTaskRepository

        repository = InMemoryTaskRepository()
        accepted_at = datetime(2026, 3, 18, 17, 0, tzinfo=UTC)
        task = TaskRecord(
            task_id="task-1",
            status=TaskStatus.COMPLETED,
            accepted_at=accepted_at,
            completed_at=accepted_at,
            duration_ms=12,
            prompt="export me",
            reasoning=False,
            execution_mode=ExecutionMode.DRY_RUN,
            dry_run=True,
            model_count=1,
            quorum=1,
            merge_strategy=MergeStrategy.FIRST_SUCCESS,
            adapter_hint=AdapterHint.AUTO,
            cancel_on_quorum=True,
            metadata={"trace_id": "exp-1"},
        )
        repository.save_task_with_steps(
            task,
            [
                TaskStepRecord(
                    task_id="task-1",
                    step_index=1,
                    model_id="kimi-k2-5",
                    model_display_name="Kimi K2.5",
                    backend="browser",
                    provider="perplexity",
                    status=StepStatus.COMPLETED,
                    output_text="ok",
                    duration_ms=12,
                )
            ],
        )
        repository.append_event(
            TaskEventRecord(
                event_id="event-1",
                task_id="task-1",
                sequence_no=1,
                event_type=EventType.TASK_ACCEPTED,
                created_at=accepted_at,
                payload={"dry_run": True},
            )
        )

        snapshot = export_postgres.collect_export_snapshot(
            repository,
            limit=10,
            generated_at=datetime(2026, 3, 18, 17, 5, tzinfo=UTC),
        )

        self.assertEqual(snapshot["status"], "ok")
        self.assertEqual(snapshot["snapshot_format_version"], SNAPSHOT_FORMAT_VERSION)
        self.assertEqual(snapshot["gracekelly_version"], __version__)
        self.assertEqual(snapshot["task_count"], 1)
        self.assertEqual(snapshot["step_count"], 1)
        self.assertEqual(snapshot["event_count"], 1)
        self.assertEqual(snapshot["exported_task_ids"], ["task-1"])
        self.assertEqual(snapshot["generated_at"], "2026-03-18T17:05:00Z")
        self.assertEqual(snapshot["tasks"][0]["task"]["task_id"], "task-1")
        self.assertEqual(snapshot["tasks"][0]["steps"][0]["model_id"], "kimi-k2-5")
        self.assertEqual(snapshot["tasks"][0]["events"][0]["event_type"], "task.accepted")
        self.assertEqual(snapshot["snapshot_sha256"], compute_snapshot_sha256(snapshot))

    def test_main_writes_snapshot_and_returns_partial_for_missing_task_ids(self) -> None:
        fake_instances: list[object] = []

        class FakeRepository:
            backend_name = "postgres"

            def __init__(self, dsn: str, *, bootstrap: bool) -> None:
                self.dsn = dsn
                fake_instances.append(self)

            def get(self, task_id: str) -> TaskRecord | None:
                from gracekelly.core.contracts import (
                    AdapterHint,
                    ExecutionMode,
                    MergeStrategy,
                    TaskStatus,
                )
                from gracekelly.storage.base import TaskRecord

                if task_id != "task-1":
                    return None
                now = datetime(2026, 3, 18, 17, 10, tzinfo=UTC)
                return TaskRecord(
                    task_id="task-1",
                    status=TaskStatus.COMPLETED,
                    accepted_at=now,
                    completed_at=now,
                    duration_ms=10,
                    prompt="hello",
                    reasoning=False,
                    execution_mode=ExecutionMode.DRY_RUN,
                    dry_run=True,
                    model_count=1,
                    quorum=1,
                    merge_strategy=MergeStrategy.FIRST_SUCCESS,
                    adapter_hint=AdapterHint.AUTO,
                    cancel_on_quorum=True,
                    metadata={},
                )

            def list_recent(self, limit: int) -> list[TaskRecord]:
                raise AssertionError("list_recent should not be used when explicit task_ids are provided")

            def list_steps(self, task_id: str) -> list[TaskStepRecord]:
                return []

            def list_events(self, task_id: str) -> list[TaskEventRecord]:
                return []

            def healthcheck(self) -> dict[str, object]:
                return {"status": "ok", "backend": "postgres"}

            def schema_report(self) -> dict[str, object]:
                return {"status": "ok", "backend": "postgres", "schema_version": "0001_initial"}

        output_path = Path("tmp") / "test-export-tool" / f"{uuid4()}.json"
        try:
            with (
                patch.object(
                    export_postgres,
                    "parse_args",
                    return_value=argparse.Namespace(
                        dsn="postgresql://example",
                        output=str(output_path),
                        task_ids=["task-1", "task-1", "task-missing"],
                        limit=100,
                    ),
                ),
                patch.object(export_postgres, "resolve_dsn", return_value="postgresql://example"),
                patch.object(export_postgres, "PostgresTaskRepository", FakeRepository),
                patch("builtins.print") as print_mock,
            ):
                code = export_postgres.main()

            self.assertEqual(code, 1)
            self.assertEqual(len(fake_instances), 1)
            result = json.loads(print_mock.call_args.args[0])
            snapshot = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "partial")
            self.assertEqual(result["snapshot_format_version"], SNAPSHOT_FORMAT_VERSION)
            self.assertEqual(result["gracekelly_version"], __version__)
            self.assertEqual(result["generated_at"], snapshot["generated_at"])
            self.assertFalse(result["compressed_output"])
            self.assertTrue(result["output_exists"])
            self.assertGreater(result["output_size_bytes"], 0)
            self.assertEqual(result["manifest_status"], "verified")
            self.assertEqual(result["snapshot_status_consistency_status"], "verified")
            self.assertEqual(result["selection_status"], "verified")
            self.assertEqual(result["task_count_status"], "verified")
            self.assertEqual(result["step_count_status"], "verified")
            self.assertEqual(result["event_count_status"], "verified")
            self.assertEqual(result["exported_task_ids_status"], "verified")
            self.assertEqual(result["missing_task_ids_status"], "verified")
            self.assertEqual(result["requested_task_ids"], ["task-1", "task-missing"])
            self.assertEqual(result["exported_task_ids"], ["task-1"])
            self.assertEqual(result["repository_health"]["status"], "ok")
            self.assertEqual(result["repository_schema"]["schema_version"], "0001_initial")
            self.assertEqual(result["task_count"], 1)
            self.assertEqual(result["step_count"], 0)
            self.assertEqual(result["event_count"], 0)
            self.assertEqual(result["missing_task_ids"], ["task-missing"])
            self.assertIn("snapshot_sha256", result)
            self.assertEqual(snapshot["snapshot_format_version"], SNAPSHOT_FORMAT_VERSION)
            self.assertEqual(snapshot["gracekelly_version"], __version__)
            self.assertEqual(snapshot["selection"]["task_ids"], ["task-1", "task-missing"])
            self.assertEqual(snapshot["step_count"], 0)
            self.assertEqual(snapshot["event_count"], 0)
            self.assertEqual(snapshot["exported_task_ids"], ["task-1"])
            self.assertEqual(snapshot["tasks"][0]["task"]["task_id"], "task-1")
            self.assertEqual(snapshot["missing_task_ids"], ["task-missing"])
            self.assertEqual(snapshot["snapshot_sha256"], compute_snapshot_sha256(snapshot))
        finally:
            if output_path.exists():
                output_path.unlink()

    def test_write_snapshot_supports_gzip_output(self) -> None:
        output_path = Path("tmp") / "test-export-tool" / f"{uuid4()}.json.gz"
        snapshot = {
            "status": "ok",
            "snapshot_format_version": SNAPSHOT_FORMAT_VERSION,
            "gracekelly_version": __version__,
            "migration": "0001_initial",
            "task_count": 0,
            "missing_task_ids": [],
            "tasks": [],
            "snapshot_sha256": "abc",
        }
        try:
            export_postgres.write_snapshot(output_path, snapshot)

            with gzip.open(output_path, "rt", encoding="utf-8") as handle:
                payload = json.load(handle)

            self.assertEqual(payload["status"], "ok")
            self.assertEqual(payload["snapshot_format_version"], SNAPSHOT_FORMAT_VERSION)
        finally:
            if output_path.exists():
                output_path.unlink()

    def test_main_reports_compressed_output_metadata_for_gzip_snapshot(self) -> None:
        class FakeRepository:
            backend_name = "postgres"

            def __init__(self, dsn: str, *, bootstrap: bool) -> None:
                pass

            def get(self, task_id: str) -> TaskRecord | None:
                raise AssertionError("get should not be used without explicit task_ids")

            def list_recent(self, limit: int) -> list[TaskRecord]:
                return []

            def list_steps(self, task_id: str) -> list[TaskStepRecord]:
                return []

            def list_events(self, task_id: str) -> list[TaskEventRecord]:
                return []

            def healthcheck(self) -> dict[str, object]:
                return {"status": "ok", "backend": "postgres"}

            def schema_report(self) -> dict[str, object]:
                return {"status": "ok", "backend": "postgres", "schema_version": "0001_initial"}

        output_path = Path("tmp") / "test-export-tool" / f"{uuid4()}.json.gz"
        try:
            with (
                patch.object(
                    export_postgres,
                    "parse_args",
                    return_value=argparse.Namespace(
                        dsn="postgresql://example",
                        output=str(output_path),
                        task_ids=[],
                        limit=100,
                    ),
                ),
                patch.object(export_postgres, "resolve_dsn", return_value="postgresql://example"),
                patch.object(export_postgres, "PostgresTaskRepository", FakeRepository),
                patch("builtins.print") as print_mock,
            ):
                code = export_postgres.main()

            self.assertEqual(code, 0)
            result = json.loads(print_mock.call_args.args[0])
            self.assertTrue(result["compressed_output"])
            self.assertTrue(result["output_exists"])
            self.assertGreater(result["output_size_bytes"], 0)
            self.assertEqual(result["manifest_status"], "verified")
            self.assertEqual(result["selection_status"], "verified")
        finally:
            if output_path.exists():
                output_path.unlink()

    def test_main_returns_error_when_generated_manifest_fails_self_validation(self) -> None:
        class FakeRepository:
            backend_name = "postgres"

            def __init__(self, dsn: str, *, bootstrap: bool) -> None:
                pass

            def get(self, task_id: str) -> TaskRecord | None:
                raise AssertionError("get should not be used without explicit task_ids")

            def list_recent(self, limit: int) -> list[TaskRecord]:
                return []

            def list_steps(self, task_id: str) -> list[TaskStepRecord]:
                return []

            def list_events(self, task_id: str) -> list[TaskEventRecord]:
                return []

            def healthcheck(self) -> dict[str, object]:
                return {"status": "ok", "backend": "postgres"}

            def schema_report(self) -> dict[str, object]:
                return {"status": "ok", "backend": "postgres", "schema_version": "0001_initial"}

        output_path = Path("tmp") / "test-export-tool" / f"{uuid4()}.json"
        try:
            with (
                patch.object(
                    export_postgres,
                    "parse_args",
                    return_value=argparse.Namespace(
                        dsn="postgresql://example",
                        output=str(output_path),
                        task_ids=[],
                        limit=100,
                    ),
                ),
                patch.object(export_postgres, "resolve_dsn", return_value="postgresql://example"),
                patch.object(export_postgres, "PostgresTaskRepository", FakeRepository),
                patch.object(export_postgres, "validate_manifest", side_effect=ValueError("manifest self-check failed")),
                patch("builtins.print") as print_mock,
            ):
                code = export_postgres.main()

            self.assertEqual(code, 2)
            payload = json.loads(print_mock.call_args.args[0])
            self.assertEqual(payload["status"], "error")
            self.assertFalse(payload["compressed_output"])
            self.assertFalse(payload["output_exists"])
            self.assertIsNone(payload["output_size_bytes"])
            self.assertIn("manifest self-check failed", payload["error"])
        finally:
            if output_path.exists():
                output_path.unlink()

    def test_main_error_payload_includes_snapshot_context_when_write_fails(self) -> None:
        class FakeRepository:
            backend_name = "postgres"

            def __init__(self, dsn: str, *, bootstrap: bool) -> None:
                pass

            def get(self, task_id: str) -> TaskRecord | None:
                raise AssertionError("get should not be used without explicit task_ids")

            def list_recent(self, limit: int) -> list[TaskRecord]:
                return []

            def list_steps(self, task_id: str) -> list[TaskStepRecord]:
                return []

            def list_events(self, task_id: str) -> list[TaskEventRecord]:
                return []

            def healthcheck(self) -> dict[str, object]:
                return {"status": "ok", "backend": "postgres"}

            def schema_report(self) -> dict[str, object]:
                return {"status": "ok", "backend": "postgres", "schema_version": "0001_initial"}

        output_path = Path("tmp") / "test-export-tool" / f"{uuid4()}.json"
        try:
            with (
                patch.object(
                    export_postgres,
                    "parse_args",
                    return_value=argparse.Namespace(
                        dsn="postgresql://example",
                        output=str(output_path),
                        task_ids=[],
                        limit=100,
                    ),
                ),
                patch.object(export_postgres, "resolve_dsn", return_value="postgresql://example"),
                patch.object(export_postgres, "PostgresTaskRepository", FakeRepository),
                patch.object(export_postgres, "write_snapshot", side_effect=OSError("disk full")),
                patch("builtins.print") as print_mock,
            ):
                code = export_postgres.main()

            self.assertEqual(code, 2)
            payload = json.loads(print_mock.call_args.args[0])
            self.assertEqual(payload["status"], "error")
            self.assertFalse(payload["compressed_output"])
            self.assertFalse(payload["output_exists"])
            self.assertIsNone(payload["output_size_bytes"])
            self.assertEqual(payload["manifest_status"], "verified")
            self.assertEqual(payload["selection_status"], "verified")
            self.assertEqual(payload["task_count"], 0)
            self.assertEqual(payload["exported_task_ids"], [])
            self.assertIn("disk full", payload["error"])
        finally:
            if output_path.exists():
                output_path.unlink()


if __name__ == "__main__":
    unittest.main()
