"""Mock-based tests for PostgresTaskRepository — no live DB required.

Covers: __init__ with pool, bootstrap, save/get/list/replace,
healthcheck, schema_report, _connect pool path, batch methods,
paginated events, and internal helpers.
"""

from __future__ import annotations

import json
import unittest
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

from gracekelly.core.contracts import (
    AdapterHint,
    EventType,
    ExecutionMode,
    FailureCode,
    MergeStrategy,
    StepStatus,
    TaskStatus,
)
from gracekelly.storage.base import TaskEventRecord, TaskRecord, TaskStepRecord
from gracekelly.storage.postgres import (
    PostgresTaskRepository,
    _PoolConnectionWithRowFactory,
)


def _make_repo(*, pool: object | None = None) -> PostgresTaskRepository:
    """Create a repo instance without calling __init__ (avoids real connect)."""
    repo = object.__new__(PostgresTaskRepository)
    repo._dsn = "postgresql://u:p@localhost/testdb"
    repo._connect_timeout_seconds = 5
    repo._pool = pool
    return repo


def _task_record(**overrides: object) -> TaskRecord:
    base: dict[str, Any] = dict(
        task_id="t-100",
        status=TaskStatus.COMPLETED,
        accepted_at=datetime(2026, 3, 29, tzinfo=UTC),
        completed_at=datetime(2026, 3, 29, 0, 1, tzinfo=UTC),
        duration_ms=450,
        prompt="test prompt",
        reasoning=False,
        execution_mode=ExecutionMode.API,
        dry_run=False,
        model_count=2,
        quorum=1,
        merge_strategy=MergeStrategy.FIRST_SUCCESS,
        adapter_hint=AdapterHint.AUTO,
        cancel_on_quorum=True,
    )
    base.update(overrides)
    return TaskRecord(**base)


def _step_record(**overrides: object) -> TaskStepRecord:
    base: dict[str, Any] = dict(
        task_id="t-100",
        step_index=0,
        model_id="mistral-small",
        model_display_name="Mistral Small",
        backend="api",
        provider="mistral",
        status=StepStatus.COMPLETED,
        output_text="result",
        duration_ms=200,
    )
    base.update(overrides)
    return TaskStepRecord(**base)


def _event_record(**overrides: object) -> TaskEventRecord:
    base: dict[str, Any] = dict(
        event_id="ev-1",
        task_id="t-100",
        sequence_no=1,
        event_type=EventType.TASK_ACCEPTED,
        created_at=datetime(2026, 3, 29, tzinfo=UTC),
        payload={"plan": "test"},
    )
    base.update(overrides)
    return TaskEventRecord(**base)


def _task_row(**overrides: object) -> dict[str, Any]:
    base = {
        "task_id": "t-100",
        "status": "completed",
        "accepted_at": datetime(2026, 3, 29, tzinfo=UTC),
        "completed_at": datetime(2026, 3, 29, 0, 1, tzinfo=UTC),
        "duration_ms": 450,
        "prompt": "test prompt",
        "reasoning": False,
        "execution_mode": "api",
        "dry_run": False,
        "model_count": 2,
        "quorum": 1,
        "merge_strategy": "first_success",
        "adapter_hint": "auto",
        "cancel_on_quorum": True,
        "failure_code": None,
        "failure_message": None,
        "output_text": "hello",
        "metadata": {},
        "retry_of_task_id": None,
    }
    base.update(overrides)
    return base


def _step_row(**overrides: object) -> dict[str, Any]:
    base = {
        "task_id": "t-100",
        "step_index": 0,
        "model_id": "mistral-small",
        "model_display_name": "Mistral Small",
        "backend": "api",
        "provider": "mistral",
        "status": "completed",
        "failure_code": None,
        "failure_message": None,
        "output_text": "ok",
        "duration_ms": 200,
    }
    base.update(overrides)
    return base


def _event_row(**overrides: object) -> dict[str, Any]:
    base = {
        "event_id": "ev-1",
        "task_id": "t-100",
        "sequence_no": 1,
        "event_type": "task.accepted",
        "created_at": datetime(2026, 3, 29, tzinfo=UTC),
        "payload": {"plan": "test"},
    }
    base.update(overrides)
    return base


def _mock_connect(cursor_mock: MagicMock) -> MagicMock:
    """Build a mock for psycopg.connect that yields cursor_mock."""
    conn = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor_mock)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    return conn


# ---------------------------------------------------------------------------
# __init__ with pool
# ---------------------------------------------------------------------------
class InitWithPoolTests(unittest.TestCase):
    @patch("gracekelly.storage.postgres.ConnectionPool")
    @patch("gracekelly.storage.postgres.psycopg")
    def test_init_creates_pool(self, mock_psycopg: MagicMock, mock_pool_cls: MagicMock) -> None:
        cursor = MagicMock()
        cursor.fetchall.return_value = [("0001_initial",)]
        conn = _mock_connect(cursor)
        mock_psycopg.connect.return_value = conn

        repo = PostgresTaskRepository(
            "postgresql://u:p@localhost/test",
            use_pool=True,
            pool_min_size=2,
            pool_max_size=10,
        )
        mock_pool_cls.assert_called_once_with(
            "postgresql://u:p@localhost/test",
            min_size=2,
            max_size=10,
            kwargs={"connect_timeout": 5},
        )
        self.assertIsNotNone(repo._pool)

    @patch("gracekelly.storage.postgres.psycopg")
    def test_init_no_pool_default(self, mock_psycopg: MagicMock) -> None:
        cursor = MagicMock()
        cursor.fetchall.return_value = [("0001_initial",)]
        conn = _mock_connect(cursor)
        mock_psycopg.connect.return_value = conn

        repo = PostgresTaskRepository("postgresql://u:p@localhost/test")
        self.assertIsNone(repo._pool)


# ---------------------------------------------------------------------------
# bootstrap
# ---------------------------------------------------------------------------
class BootstrapTests(unittest.TestCase):
    @patch("gracekelly.storage.postgres.discover_migrations", return_value=["0001_initial", "0002_add_retry"])
    @patch("gracekelly.storage.postgres.load_migration_sql")
    @patch("gracekelly.storage.postgres.split_sql_statements")
    @patch("gracekelly.storage.postgres.psycopg")
    def test_bootstrap_applies_pending_migrations(
        self,
        mock_psycopg: MagicMock,
        mock_split: MagicMock,
        mock_load: MagicMock,
        mock_discover: MagicMock,
    ) -> None:
        cursor = MagicMock()
        # _applied_migrations returns only 0001
        cursor.fetchall.return_value = [("0001_initial",)]
        conn = _mock_connect(cursor)
        mock_psycopg.connect.return_value = conn

        mock_load.return_value = "ALTER TABLE gk_tasks ADD COLUMN retry_of_task_id TEXT;"
        mock_split.return_value = ["ALTER TABLE gk_tasks ADD COLUMN retry_of_task_id TEXT"]

        PostgresTaskRepository("postgresql://u:p@localhost/test", bootstrap=True)

        # load_migration_sql called for the pending one only
        mock_load.assert_called_once_with("0002_add_retry")
        # split_sql_statements called for its SQL
        mock_split.assert_called_once()
        # INSERT INTO gk_schema_migrations for the new migration
        insert_calls = [
            c for c in cursor.execute.call_args_list
            if isinstance(c.args[0], str) and "gk_schema_migrations" in c.args[0] and "INSERT" in c.args[0]
        ]
        self.assertEqual(len(insert_calls), 1)
        self.assertIn("0002_add_retry", insert_calls[0].args[1])

    @patch("gracekelly.storage.postgres.discover_migrations", return_value=["0001_initial"])
    @patch("gracekelly.storage.postgres.psycopg")
    def test_bootstrap_no_pending(self, mock_psycopg: MagicMock, mock_discover: MagicMock) -> None:
        cursor = MagicMock()
        cursor.fetchall.return_value = [("0001_initial",)]
        conn = _mock_connect(cursor)
        mock_psycopg.connect.return_value = conn

        repo = PostgresTaskRepository("postgresql://u:p@localhost/test", bootstrap=True)
        # No load_migration_sql calls
        self.assertIsNotNone(repo)


# ---------------------------------------------------------------------------
# applied_migrations
# ---------------------------------------------------------------------------
class AppliedMigrationsTests(unittest.TestCase):
    @patch("gracekelly.storage.postgres.psycopg")
    def test_applied_migrations_returns_list(self, mock_psycopg: MagicMock) -> None:
        cursor = MagicMock()
        cursor.fetchall.return_value = [("0001_initial",), ("0002_retry",)]
        conn = _mock_connect(cursor)
        mock_psycopg.connect.return_value = conn

        repo = _make_repo()
        result = repo.applied_migrations()
        self.assertEqual(result, ["0001_initial", "0002_retry"])

    @patch("gracekelly.storage.postgres.psycopg")
    def test_applied_migrations_psycopg_error_returns_empty_and_logs_debug(self, mock_psycopg: MagicMock) -> None:
        cursor = MagicMock()
        error = RuntimeError("table does not exist")
        mock_psycopg.Error = RuntimeError
        cursor.execute.side_effect = error

        with self.assertLogs("gracekelly.storage.postgres", level="DEBUG") as logs:
            result = PostgresTaskRepository._applied_migrations(cursor)

        self.assertEqual(result, [])
        self.assertEqual(logs.output, ["DEBUG:gracekelly.storage.postgres:postgres.applied_migrations.unavailable error=RuntimeError('table does not exist')"])


# ---------------------------------------------------------------------------
# save_task_with_steps
# ---------------------------------------------------------------------------
class SaveTaskWithStepsTests(unittest.TestCase):
    @patch("gracekelly.storage.postgres.psycopg")
    def test_save_task_with_steps(self, mock_psycopg: MagicMock) -> None:
        cursor = MagicMock()
        conn = _mock_connect(cursor)
        mock_psycopg.connect.return_value = conn

        repo = _make_repo()
        task = _task_record()
        steps = [_step_record(step_index=0), _step_record(step_index=1)]

        repo.save_task_with_steps(task, steps)

        # 1 task upsert + 2 step upserts
        self.assertEqual(cursor.execute.call_count, 3)
        conn.commit.assert_called_once()


# ---------------------------------------------------------------------------
# replace_task_snapshot
# ---------------------------------------------------------------------------
class ReplaceTaskSnapshotTests(unittest.TestCase):
    @patch("gracekelly.storage.postgres.psycopg")
    def test_replace_snapshot_deletes_and_reinserts(self, mock_psycopg: MagicMock) -> None:
        cursor = MagicMock()
        conn = _mock_connect(cursor)
        mock_psycopg.connect.return_value = conn

        repo = _make_repo()
        task = _task_record()
        steps = [_step_record()]
        events = [_event_record(), _event_record(event_id="ev-2", sequence_no=2)]

        repo.replace_task_snapshot(task, steps, events)

        # DELETE + task upsert + step upsert + 2 event inserts = 5
        self.assertEqual(cursor.execute.call_count, 5)
        first_call_sql = cursor.execute.call_args_list[0].args[0]
        self.assertIn("DELETE FROM gk_tasks", first_call_sql)
        conn.commit.assert_called_once()


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------
class GetTests(unittest.TestCase):
    @patch("gracekelly.storage.postgres.psycopg")
    def test_get_returns_task(self, mock_psycopg: MagicMock) -> None:
        cursor = MagicMock()
        cursor.fetchone.return_value = _task_row()
        conn = _mock_connect(cursor)
        mock_psycopg.connect.return_value = conn

        repo = _make_repo()
        task = repo.get("t-100")
        self.assertIsNotNone(task)
        assert task is not None
        self.assertEqual(task.task_id, "t-100")
        self.assertEqual(task.status, TaskStatus.COMPLETED)

    @patch("gracekelly.storage.postgres.psycopg")
    def test_get_returns_none_when_not_found(self, mock_psycopg: MagicMock) -> None:
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        conn = _mock_connect(cursor)
        mock_psycopg.connect.return_value = conn

        repo = _make_repo()
        self.assertIsNone(repo.get("nonexistent"))


# ---------------------------------------------------------------------------
# list_recent
# ---------------------------------------------------------------------------
class ListRecentTests(unittest.TestCase):
    @patch("gracekelly.storage.postgres.psycopg")
    def test_list_recent_no_filters(self, mock_psycopg: MagicMock) -> None:
        cursor = MagicMock()
        cursor.fetchall.return_value = [_task_row(), _task_row(task_id="t-101")]
        conn = _mock_connect(cursor)
        mock_psycopg.connect.return_value = conn

        repo = _make_repo()
        tasks = repo.list_recent(10)
        self.assertEqual(len(tasks), 2)

    @patch("gracekelly.storage.postgres.psycopg")
    def test_list_recent_with_all_filters(self, mock_psycopg: MagicMock) -> None:
        cursor = MagicMock()
        cursor.fetchall.return_value = [_task_row()]
        conn = _mock_connect(cursor)
        mock_psycopg.connect.return_value = conn

        repo = _make_repo()
        before = datetime(2026, 3, 30, tzinfo=UTC)
        tasks = repo.list_recent(
            5,
            status=TaskStatus.COMPLETED,
            execution_mode=ExecutionMode.API,
            dry_run=False,
            failure_code=FailureCode.TIMEOUT,
            before=before,
        )
        self.assertEqual(len(tasks), 1)
        # Verify WHERE clause was built with parameters
        sql = cursor.execute.call_args.args[0]
        self.assertIn("WHERE", sql)
        params = cursor.execute.call_args.args[1]
        # 5 filter params + 1 limit = tuple length 6
        self.assertEqual(len(params), 6)

    @patch("gracekelly.storage.postgres.psycopg")
    def test_list_recent_empty(self, mock_psycopg: MagicMock) -> None:
        cursor = MagicMock()
        cursor.fetchall.return_value = []
        conn = _mock_connect(cursor)
        mock_psycopg.connect.return_value = conn

        repo = _make_repo()
        tasks = repo.list_recent(10)
        self.assertEqual(tasks, [])


# ---------------------------------------------------------------------------
# list_steps
# ---------------------------------------------------------------------------
class ListStepsTests(unittest.TestCase):
    @patch("gracekelly.storage.postgres.psycopg")
    def test_list_steps(self, mock_psycopg: MagicMock) -> None:
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            _step_row(step_index=0),
            _step_row(step_index=1, model_id="kimi-k2-5"),
        ]
        conn = _mock_connect(cursor)
        mock_psycopg.connect.return_value = conn

        repo = _make_repo()
        steps = repo.list_steps("t-100")
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0].step_index, 0)
        self.assertEqual(steps[1].model_id, "kimi-k2-5")


# ---------------------------------------------------------------------------
# list_steps_batch
# ---------------------------------------------------------------------------
class ListStepsBatchTests(unittest.TestCase):
    @patch("gracekelly.storage.postgres.psycopg")
    def test_batch_returns_grouped_steps(self, mock_psycopg: MagicMock) -> None:
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            _step_row(task_id="t-1", step_index=0),
            _step_row(task_id="t-2", step_index=0),
        ]
        conn = _mock_connect(cursor)
        mock_psycopg.connect.return_value = conn

        repo = _make_repo()
        result = repo.list_steps_batch(["t-1", "t-2"])
        self.assertIn("t-1", result)
        self.assertIn("t-2", result)
        self.assertEqual(len(result["t-1"]), 1)

    def test_batch_empty_returns_empty_dict(self) -> None:
        repo = _make_repo()
        result = repo.list_steps_batch([])
        self.assertEqual(result, {})


# ---------------------------------------------------------------------------
# list_events_batch
# ---------------------------------------------------------------------------
class ListEventsBatchTests(unittest.TestCase):
    @patch("gracekelly.storage.postgres.psycopg")
    def test_batch_returns_grouped_events(self, mock_psycopg: MagicMock) -> None:
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            _event_row(task_id="t-1", event_id="e1"),
            _event_row(task_id="t-2", event_id="e2"),
        ]
        conn = _mock_connect(cursor)
        mock_psycopg.connect.return_value = conn

        repo = _make_repo()
        result = repo.list_events_batch(["t-1", "t-2"])
        self.assertIn("t-1", result)
        self.assertIn("t-2", result)

    def test_batch_empty_returns_empty_dict(self) -> None:
        repo = _make_repo()
        result = repo.list_events_batch([])
        self.assertEqual(result, {})


# ---------------------------------------------------------------------------
# append_event
# ---------------------------------------------------------------------------
class AppendEventTests(unittest.TestCase):
    @patch("gracekelly.storage.postgres.psycopg")
    def test_append_event(self, mock_psycopg: MagicMock) -> None:
        cursor = MagicMock()
        conn = _mock_connect(cursor)
        mock_psycopg.connect.return_value = conn

        repo = _make_repo()
        event = _event_record()
        repo.append_event(event)

        self.assertEqual(cursor.execute.call_count, 1)
        params = cursor.execute.call_args.args[1]
        self.assertEqual(params["event_id"], "ev-1")
        self.assertEqual(params["payload"], json.dumps({"plan": "test"}))
        conn.commit.assert_called_once()


# ---------------------------------------------------------------------------
# list_events
# ---------------------------------------------------------------------------
class ListEventsTests(unittest.TestCase):
    @patch("gracekelly.storage.postgres.psycopg")
    def test_list_events(self, mock_psycopg: MagicMock) -> None:
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            _event_row(sequence_no=1),
            _event_row(event_id="ev-2", sequence_no=2, event_type="task.completed"),
        ]
        conn = _mock_connect(cursor)
        mock_psycopg.connect.return_value = conn

        repo = _make_repo()
        events = repo.list_events("t-100")
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].event_type, EventType.TASK_ACCEPTED)
        self.assertEqual(events[1].event_type, EventType.TASK_COMPLETED)


# ---------------------------------------------------------------------------
# list_events_paginated
# ---------------------------------------------------------------------------
class ListEventsPaginatedTests(unittest.TestCase):
    @patch("gracekelly.storage.postgres.psycopg")
    def test_paginated_with_limit(self, mock_psycopg: MagicMock) -> None:
        cursor = MagicMock()
        # First fetchone for COUNT(*), then fetchall for data
        cursor.fetchone.return_value = {"0": 5}
        # Make fetchone return a subscriptable result
        count_result = MagicMock()
        count_result.__getitem__ = MagicMock(return_value=5)
        cursor.fetchone.return_value = count_result
        cursor.fetchall.return_value = [_event_row()]
        conn = _mock_connect(cursor)
        mock_psycopg.connect.return_value = conn

        repo = _make_repo()
        events, total = repo.list_events_paginated("t-100", limit=10, offset=0)
        self.assertEqual(total, 5)
        self.assertEqual(len(events), 1)
        # 2 execute calls: COUNT + SELECT
        self.assertEqual(cursor.execute.call_count, 2)

    @patch("gracekelly.storage.postgres.psycopg")
    def test_paginated_without_limit(self, mock_psycopg: MagicMock) -> None:
        cursor = MagicMock()
        count_result = MagicMock()
        count_result.__getitem__ = MagicMock(return_value=3)
        cursor.fetchone.return_value = count_result
        cursor.fetchall.return_value = [
            _event_row(sequence_no=1),
            _event_row(event_id="ev-2", sequence_no=2),
            _event_row(event_id="ev-3", sequence_no=3),
        ]
        conn = _mock_connect(cursor)
        mock_psycopg.connect.return_value = conn

        repo = _make_repo()
        events, total = repo.list_events_paginated("t-100", limit=None, offset=0)
        self.assertEqual(total, 3)
        self.assertEqual(len(events), 3)
        # Check that the query does NOT contain LIMIT
        data_sql = cursor.execute.call_args_list[1].args[0]
        self.assertNotIn("LIMIT", data_sql)


# ---------------------------------------------------------------------------
# healthcheck
# ---------------------------------------------------------------------------
class HealthcheckTests(unittest.TestCase):
    @patch("gracekelly.storage.postgres.psycopg")
    def test_healthcheck_ok(self, mock_psycopg: MagicMock) -> None:
        cursor = MagicMock()
        # _load_health_ping
        cursor.fetchone.side_effect = [
            {"ok": 1},
            {"task_count": 10, "step_count": 25, "event_count": 50},
        ]
        conn = _mock_connect(cursor)
        mock_psycopg.connect.return_value = conn

        repo = _make_repo()
        result = repo.healthcheck()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["backend"], "postgres")
        self.assertEqual(result["task_count"], 10)

    @patch("gracekelly.storage.postgres.psycopg")
    def test_healthcheck_degraded_on_exception(self, mock_psycopg: MagicMock) -> None:
        mock_psycopg.connect.side_effect = Exception("connection refused")

        repo = _make_repo()
        result = repo.healthcheck()
        self.assertEqual(result["status"], "degraded")
        self.assertIn("error", result)

    @patch("gracekelly.storage.postgres.psycopg")
    def test_load_health_ping_none_row(self, mock_psycopg: MagicMock) -> None:
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        conn = _mock_connect(cursor)
        mock_psycopg.connect.return_value = conn

        repo = _make_repo()
        result = repo._load_health_ping()
        self.assertEqual(result, {"ok": 1})

    @patch("gracekelly.storage.postgres.psycopg")
    def test_load_storage_counts_none_row(self, mock_psycopg: MagicMock) -> None:
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        conn = _mock_connect(cursor)
        mock_psycopg.connect.return_value = conn

        repo = _make_repo()
        result = repo._load_storage_counts()
        self.assertEqual(result, {"task_count": 0, "step_count": 0, "event_count": 0})

    @patch("gracekelly.storage.postgres.psycopg")
    def test_load_storage_counts_normal(self, mock_psycopg: MagicMock) -> None:
        cursor = MagicMock()
        cursor.fetchone.return_value = {
            "task_count": 5,
            "step_count": 12,
            "event_count": 30,
        }
        conn = _mock_connect(cursor)
        mock_psycopg.connect.return_value = conn

        repo = _make_repo()
        result = repo._load_storage_counts()
        self.assertEqual(result["task_count"], 5)
        self.assertEqual(result["step_count"], 12)
        self.assertEqual(result["event_count"], 30)


# ---------------------------------------------------------------------------
# schema_report
# ---------------------------------------------------------------------------
class SchemaReportTests(unittest.TestCase):
    @patch("gracekelly.storage.postgres.psycopg")
    def test_schema_report_ok(self, mock_psycopg: MagicMock) -> None:
        cursor = MagicMock()
        # _load_schema_columns returns rows for all expected tables
        cursor.fetchall.side_effect = [
            # schema columns query
            [
                {"table_name": "gk_tasks", "column_name": col}
                for col in (
                    "task_id", "status", "accepted_at", "completed_at",
                    "duration_ms", "prompt", "reasoning", "execution_mode",
                    "dry_run", "model_count", "quorum", "merge_strategy",
                    "adapter_hint", "cancel_on_quorum", "failure_code",
                    "failure_message", "output_text", "metadata", "retry_of_task_id",
                )
            ] + [
                {"table_name": "gk_task_steps", "column_name": col}
                for col in (
                    "task_id", "step_index", "model_id", "model_display_name",
                    "backend", "provider", "status", "failure_code",
                    "failure_message", "output_text", "duration_ms",
                    "input_tokens", "output_tokens",
                )
            ] + [
                {"table_name": "gk_task_events", "column_name": col}
                for col in ("event_id", "task_id", "sequence_no", "event_type", "created_at", "payload")
            ],
            # applied_migrations query
            [("0001_initial",)],
        ]
        conn = _mock_connect(cursor)
        mock_psycopg.connect.return_value = conn

        repo = _make_repo()
        result = repo.schema_report()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["missing_tables"], [])
        self.assertEqual(result["missing_columns"], {})

    @patch("gracekelly.storage.postgres.psycopg")
    def test_schema_report_degraded_missing_table(self, mock_psycopg: MagicMock) -> None:
        cursor = MagicMock()
        # Return only gk_tasks columns — missing gk_task_steps and gk_task_events
        cursor.fetchall.side_effect = [
            [{"table_name": "gk_tasks", "column_name": "task_id"}],
            [("0001_initial",)],
        ]
        conn = _mock_connect(cursor)
        mock_psycopg.connect.return_value = conn

        repo = _make_repo()
        result = repo.schema_report()
        self.assertEqual(result["status"], "degraded")
        self.assertIn("gk_task_steps", result["missing_tables"])
        self.assertIn("gk_task_events", result["missing_tables"])

    @patch("gracekelly.storage.postgres.psycopg")
    def test_schema_report_exception(self, mock_psycopg: MagicMock) -> None:
        mock_psycopg.connect.side_effect = Exception("conn failed")

        repo = _make_repo()
        result = repo.schema_report()
        self.assertEqual(result["status"], "degraded")
        self.assertIn("error", result)
        self.assertEqual(result["backend"], "postgres")

    @patch("gracekelly.storage.postgres.psycopg")
    def test_schema_report_applied_migrations_exception(self, mock_psycopg: MagicMock) -> None:
        """When applied_migrations() fails, report still returns with pending = all available."""
        cursor = MagicMock()
        call_count = 0
        mock_psycopg.Error = RuntimeError

        def fetchall_side_effect() -> list[dict[str, str]]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # _load_schema_columns — return all columns for all tables
                return [
                    {"table_name": "gk_tasks", "column_name": col}
                    for col in (
                        "task_id", "status", "accepted_at", "completed_at",
                        "duration_ms", "prompt", "reasoning", "execution_mode",
                        "dry_run", "model_count", "quorum", "merge_strategy",
                        "adapter_hint", "cancel_on_quorum", "failure_code",
                        "failure_message", "output_text", "metadata", "retry_of_task_id",
                    )
                ] + [
                    {"table_name": "gk_task_steps", "column_name": col}
                    for col in (
                        "task_id", "step_index", "model_id", "model_display_name",
                        "backend", "provider", "status", "failure_code",
                        "failure_message", "output_text", "duration_ms",
                        "input_tokens", "output_tokens",
                    )
                ] + [
                    {"table_name": "gk_task_events", "column_name": col}
                    for col in ("event_id", "task_id", "sequence_no", "event_type", "created_at", "payload")
                ]
            # Second call — applied_migrations — fails
            raise RuntimeError("table not found")

        cursor.fetchall.side_effect = fetchall_side_effect
        conn = _mock_connect(cursor)
        mock_psycopg.connect.return_value = conn

        repo = _make_repo()
        result = repo.schema_report()
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["migrations_applied"], [])


# ---------------------------------------------------------------------------
# _connect with pool
# ---------------------------------------------------------------------------
class ConnectPoolTests(unittest.TestCase):
    def test_connect_with_pool_no_row_factory(self) -> None:
        pool = MagicMock()
        pool_conn = MagicMock()
        pool.connection.return_value = pool_conn

        repo = _make_repo(pool=pool)
        repo_any: Any = repo
        result = repo_any._connect()
        self.assertIs(result, pool_conn)

    def test_connect_with_pool_row_factory(self) -> None:
        pool = MagicMock()
        pool_conn = MagicMock()
        pool.connection.return_value = pool_conn

        repo = _make_repo(pool=pool)
        repo_any: Any = repo
        result = repo_any._connect(row_factory="dict_row_sentinel")
        self.assertIsInstance(result, _PoolConnectionWithRowFactory)

    @patch("gracekelly.storage.postgres.psycopg")
    def test_connect_without_pool(self, mock_psycopg: MagicMock) -> None:
        conn = MagicMock()
        mock_psycopg.connect.return_value = conn

        repo = _make_repo()
        repo_any: Any = repo
        repo_any._connect()
        mock_psycopg.connect.assert_called_once_with(
            "postgresql://u:p@localhost/testdb",
            connect_timeout=5,
        )

    @patch("gracekelly.storage.postgres.psycopg")
    def test_connect_without_pool_with_row_factory(self, mock_psycopg: MagicMock) -> None:
        conn = MagicMock()
        mock_psycopg.connect.return_value = conn

        repo = _make_repo()
        repo_any: Any = repo
        repo_any._connect(row_factory="dict_row_sentinel")
        mock_psycopg.connect.assert_called_once_with(
            "postgresql://u:p@localhost/testdb",
            connect_timeout=5,
            row_factory="dict_row_sentinel",
        )


# ---------------------------------------------------------------------------
# _load_schema_columns
# ---------------------------------------------------------------------------
class LoadSchemaColumnsTests(unittest.TestCase):
    @patch("gracekelly.storage.postgres.psycopg")
    def test_filters_non_gk_tables(self, mock_psycopg: MagicMock) -> None:
        cursor = MagicMock()
        cursor.fetchall.return_value = [
            {"table_name": "gk_tasks", "column_name": "task_id"},
            {"table_name": "some_other_table", "column_name": "id"},
            {"table_name": "gk_task_steps", "column_name": "task_id"},
        ]
        conn = _mock_connect(cursor)
        mock_psycopg.connect.return_value = conn

        repo = _make_repo()
        result = repo._load_schema_columns()
        self.assertIn("gk_tasks", result)
        self.assertIn("gk_task_steps", result)
        self.assertNotIn("some_other_table", result)


# ---------------------------------------------------------------------------
# _PoolConnectionWithRowFactory
# ---------------------------------------------------------------------------
class PoolConnectionWithRowFactoryTests(unittest.TestCase):
    def test_enter_sets_row_factory(self) -> None:
        inner_conn = MagicMock()
        pool_ctx = MagicMock()
        pool_ctx.__enter__ = MagicMock(return_value=inner_conn)
        pool_ctx.__exit__ = MagicMock(return_value=False)

        wrapper = _PoolConnectionWithRowFactory(pool_ctx, "dict_row_sentinel")
        with wrapper as conn:
            self.assertIs(conn, inner_conn)
            self.assertEqual(conn.row_factory, "dict_row_sentinel")

    def test_exit_delegates(self) -> None:
        pool_ctx = MagicMock()
        pool_ctx.__enter__ = MagicMock(return_value=MagicMock())
        pool_ctx.__exit__ = MagicMock(return_value=True)

        wrapper = _PoolConnectionWithRowFactory(pool_ctx, None)
        wrapper.__enter__()
        result = wrapper.__exit__(None, None, None)
        self.assertTrue(result)
