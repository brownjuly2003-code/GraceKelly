from __future__ import annotations

import unittest

from gracekelly.core.contracts import AdapterHint, EventType, ExecutionMode, FailureCode, MergeStrategy, StepStatus, TaskStatus
from gracekelly.storage.postgres import PostgresTaskRepository
from gracekelly.storage.schema import (
    EXPECTED_SCHEMA_COLUMNS,
    INITIAL_MIGRATION_NAME,
    compute_schema_diff,
    load_migration_sql,
    split_sql_statements,
)


class PostgresSchemaTests(unittest.TestCase):
    def test_initial_migration_contains_expected_tables(self) -> None:
        sql = load_migration_sql(INITIAL_MIGRATION_NAME)

        for table_name in EXPECTED_SCHEMA_COLUMNS:
            self.assertIn(table_name, sql)

    def test_split_sql_statements_returns_bootstrap_units(self) -> None:
        statements = split_sql_statements(load_migration_sql())

        self.assertGreaterEqual(len(statements), 6)
        self.assertTrue(statements[0].startswith("CREATE TABLE IF NOT EXISTS gk_tasks"))
        self.assertTrue(
            any(
                statement.startswith("CREATE TABLE IF NOT EXISTS gk_task_events")
                for statement in statements
            )
        )

    def test_compute_schema_diff_reports_missing_tables_and_columns(self) -> None:
        diff = compute_schema_diff(
            {
                "gk_tasks": {"task_id", "status"},
                "gk_task_steps": {"task_id", "step_index"},
            }
        )

        self.assertEqual(diff["missing_tables"], ["gk_task_events"])
        self.assertEqual(
            diff["missing_columns"]["gk_tasks"][:2],
            ["accepted_at", "completed_at"],
        )
        self.assertIn("model_id", diff["missing_columns"]["gk_task_steps"])

    def test_task_row_is_normalized_back_to_merge_strategy_enum(self) -> None:
        repository = PostgresTaskRepository.__new__(PostgresTaskRepository)

        record = repository._task_from_row(
            {
                "task_id": "task-1",
                "status": "completed",
                "accepted_at": None,
                "completed_at": None,
                "duration_ms": 1,
                "prompt": "hello",
                "reasoning": False,
                "execution_mode": "api",
                "dry_run": False,
                "model_count": 1,
                "quorum": 1,
                "merge_strategy": "first_success",
                "adapter_hint": "auto",
                "cancel_on_quorum": True,
                "failure_code": "timeout",
                "failure_message": None,
                "output_text": "ok",
                "metadata": {},
            }
        )

        self.assertEqual(record.status, TaskStatus.COMPLETED)
        self.assertEqual(record.execution_mode, ExecutionMode.API)
        self.assertEqual(record.merge_strategy, MergeStrategy.FIRST_SUCCESS)
        self.assertEqual(record.adapter_hint, AdapterHint.AUTO)
        self.assertEqual(record.failure_code, FailureCode.TIMEOUT)

    def test_step_and_event_rows_are_normalized_back_to_enums(self) -> None:
        repository = PostgresTaskRepository.__new__(PostgresTaskRepository)

        step = repository._step_from_row(
            {
                "task_id": "task-1",
                "step_index": 1,
                "model_id": "mistral-small",
                "model_display_name": "Mistral Small",
                "backend": "api",
                "provider": "mistral",
                "status": "failed",
                "failure_code": "provider_unavailable",
                "failure_message": "offline",
                "output_text": None,
                "duration_ms": 10,
            }
        )
        event = repository._event_from_row(
            {
                "event_id": "event-1",
                "task_id": "task-1",
                "sequence_no": 1,
                "event_type": "task.accepted",
                "created_at": None,
                "payload": {},
            }
        )

        self.assertEqual(step.status, StepStatus.FAILED)
        self.assertEqual(step.failure_code, FailureCode.PROVIDER_UNAVAILABLE)
        self.assertEqual(event.event_type, EventType.TASK_ACCEPTED)

    def test_connect_uses_default_connect_timeout(self) -> None:
        repository = PostgresTaskRepository.__new__(PostgresTaskRepository)
        repository._dsn = "postgresql://example"
        repository._connect_timeout_seconds = 7

        class FakePsycopg:
            called_with: tuple[object, dict[str, object]] | None = None

            @staticmethod
            def connect(dsn: str, **kwargs):
                FakePsycopg.called_with = (dsn, kwargs)
                return object()

        from gracekelly.storage import postgres as postgres_module

        original = postgres_module.psycopg
        postgres_module.psycopg = FakePsycopg
        try:
            repository._connect(row_factory="dict")
        finally:
            postgres_module.psycopg = original

        self.assertIsNotNone(FakePsycopg.called_with)
        dsn, kwargs = FakePsycopg.called_with
        self.assertEqual(dsn, "postgresql://example")
        self.assertEqual(kwargs["connect_timeout"], 7)
        self.assertEqual(kwargs["row_factory"], "dict")


if __name__ == "__main__":
    unittest.main()
