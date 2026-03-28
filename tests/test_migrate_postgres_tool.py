from __future__ import annotations

import argparse
import json
import os
import unittest
import unittest.mock
from datetime import UTC, datetime
from unittest.mock import patch

from gracekelly.tools import migrate_postgres
from gracekelly.tools.migrate_postgres import _json_default


class MigratePostgresMainTests(unittest.TestCase):
    def test_main_returns_2_when_dsn_missing(self) -> None:
        clean_env = {k: v for k, v in os.environ.items() if k != "GRACEKELLY_POSTGRES_DSN"}
        with (
            patch.object(migrate_postgres, "parse_args", return_value=argparse.Namespace(dsn=None, dry_run=False)),
            unittest.mock.patch.dict(os.environ, clean_env, clear=True),
            patch("builtins.print") as print_mock,
        ):
            code = migrate_postgres.main()

        self.assertEqual(code, 2)
        payload = json.loads(print_mock.call_args.args[0])
        self.assertEqual(payload["status"], "error")

    def test_main_returns_0_for_dry_run(self) -> None:
        class FakeRepo:
            def __init__(self, dsn: str, *, bootstrap: bool) -> None:
                pass

            def applied_migrations(self) -> list[str]:
                return ["0001_initial"]

        with (
            patch.object(
                migrate_postgres,
                "parse_args",
                return_value=argparse.Namespace(dsn="postgresql://example", dry_run=True),
            ),
            patch.object(migrate_postgres, "PostgresTaskRepository", FakeRepo),
            patch.object(migrate_postgres, "discover_migrations", return_value=["0001_initial", "0002_add_retry"]),
            patch("builtins.print") as print_mock,
        ):
            code = migrate_postgres.main()

        self.assertEqual(code, 0)
        payload = json.loads(print_mock.call_args.args[0])
        self.assertEqual(payload["status"], "dry_run")
        self.assertEqual(payload["migrations_pending"], ["0002_add_retry"])

    def test_main_dry_run_handles_repo_exception(self) -> None:
        with (
            patch.object(
                migrate_postgres,
                "parse_args",
                return_value=argparse.Namespace(dsn="postgresql://example", dry_run=True),
            ),
            patch.object(migrate_postgres, "PostgresTaskRepository", side_effect=RuntimeError("db down")),
            patch.object(migrate_postgres, "discover_migrations", return_value=["0001_initial"]),
            patch("builtins.print") as print_mock,
        ):
            code = migrate_postgres.main()

        self.assertEqual(code, 0)
        payload = json.loads(print_mock.call_args.args[0])
        self.assertEqual(payload["migrations_applied"], [])

    def test_main_returns_2_when_bootstrap_raises(self) -> None:
        with (
            patch.object(
                migrate_postgres,
                "parse_args",
                return_value=argparse.Namespace(dsn="postgresql://example", dry_run=False),
            ),
            patch.object(migrate_postgres, "PostgresTaskRepository", side_effect=RuntimeError("cannot connect")),
            patch.object(migrate_postgres, "discover_migrations", return_value=[]),
            patch("builtins.print") as print_mock,
        ):
            code = migrate_postgres.main()

        self.assertEqual(code, 2)
        payload = json.loads(print_mock.call_args.args[0])
        self.assertEqual(payload["status"], "error")

    def test_main_returns_0_when_schema_ok(self) -> None:
        class FakeRepo:
            def __init__(self, dsn: str, *, bootstrap: bool) -> None:
                pass

            def schema_report(self) -> dict[str, object]:
                return {
                    "status": "ok",
                    "migrations_available": ["0001_initial"],
                    "migrations_applied": ["0001_initial"],
                    "migrations_pending": [],
                }

        with (
            patch.object(
                migrate_postgres,
                "parse_args",
                return_value=argparse.Namespace(dsn="postgresql://example", dry_run=False),
            ),
            patch.object(migrate_postgres, "PostgresTaskRepository", FakeRepo),
            patch.object(migrate_postgres, "discover_migrations", return_value=["0001_initial"]),
            patch("builtins.print"),
        ):
            code = migrate_postgres.main()

        self.assertEqual(code, 0)

    def test_main_returns_1_when_schema_degraded(self) -> None:
        class FakeRepo:
            def __init__(self, dsn: str, *, bootstrap: bool) -> None:
                pass

            def schema_report(self) -> dict[str, object]:
                return {
                    "status": "degraded",
                    "missing_tables": ["gk_task_steps"],
                }

        with (
            patch.object(
                migrate_postgres,
                "parse_args",
                return_value=argparse.Namespace(dsn="postgresql://example", dry_run=False),
            ),
            patch.object(migrate_postgres, "PostgresTaskRepository", FakeRepo),
            patch.object(migrate_postgres, "discover_migrations", return_value=[]),
            patch("builtins.print"),
        ):
            code = migrate_postgres.main()

        self.assertEqual(code, 1)


class JsonDefaultTests(unittest.TestCase):
    def test_datetime_serialized_as_isoformat(self) -> None:
        dt = datetime(2026, 3, 27, 12, 0, 0, tzinfo=UTC)
        result = _json_default(dt)
        self.assertIn("2026-03-27", result)
        self.assertIn("12:00:00", result)

    def test_naive_datetime_serialized(self) -> None:
        dt = datetime(2025, 1, 15, 8, 30, 0)
        result = _json_default(dt)
        self.assertIsInstance(result, str)
        self.assertIn("2025-01-15", result)

    def test_non_datetime_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            _json_default({"key": "value"})

    def test_integer_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            _json_default(42)

    def test_none_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            _json_default(None)

    def test_type_error_message_contains_type_name(self) -> None:
        with self.assertRaises(TypeError) as ctx:
            _json_default([1, 2, 3])
        self.assertIn("list", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
