from __future__ import annotations

import argparse
import json
import os
import unittest
import unittest.mock
from datetime import UTC, datetime
from unittest.mock import patch

from gracekelly.tools import validate_postgres
from gracekelly.tools.validate_postgres import _json_default, resolve_dsn


class ResolveDsnTests(unittest.TestCase):
    def test_cli_dsn_returned_directly(self) -> None:
        self.assertEqual(resolve_dsn("postgresql://host/db"), "postgresql://host/db")

    def test_env_fallback_when_cli_none(self) -> None:
        with unittest.mock.patch.dict(os.environ, {"GRACEKELLY_POSTGRES_DSN": "env-dsn"}):
            self.assertEqual(resolve_dsn(None), "env-dsn")

    def test_both_missing_returns_none(self) -> None:
        clean = {k: v for k, v in os.environ.items() if k != "GRACEKELLY_POSTGRES_DSN"}
        with unittest.mock.patch.dict(os.environ, clean, clear=True):
            self.assertIsNone(resolve_dsn(None))

    def test_cli_takes_precedence_over_env(self) -> None:
        with unittest.mock.patch.dict(os.environ, {"GRACEKELLY_POSTGRES_DSN": "env-dsn"}):
            self.assertEqual(resolve_dsn("cli-dsn"), "cli-dsn")


class JsonDefaultTests(unittest.TestCase):
    def test_datetime_returns_isoformat(self) -> None:
        dt = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
        self.assertEqual(_json_default(dt), dt.isoformat())

    def test_non_serializable_raises_type_error(self) -> None:
        with self.assertRaises(TypeError) as ctx:
            _json_default(object())
        self.assertIn("object", str(ctx.exception))

    def test_integer_raises_type_error(self) -> None:
        with self.assertRaises(TypeError) as ctx:
            _json_default(42)
        self.assertIn("int", str(ctx.exception))

    def test_none_raises_type_error(self) -> None:
        with self.assertRaises(TypeError):
            _json_default(None)


class ValidatePostgresToolTests(unittest.TestCase):
    def test_main_returns_error_when_dsn_is_missing(self) -> None:
        with (
            patch.object(validate_postgres, "parse_args", return_value=argparse.Namespace(dsn=None, no_bootstrap=False)),
            patch.object(validate_postgres, "resolve_dsn", return_value=None),
            patch("builtins.print") as print_mock,
        ):
            code = validate_postgres.main()

        self.assertEqual(code, 2)
        payload = json.loads(print_mock.call_args.args[0])
        self.assertEqual(payload["status"], "error")
        self.assertIn("DSN is required", payload["error"])

    def test_main_returns_degraded_when_schema_report_is_degraded(self) -> None:
        class FakeRepository:
            def __init__(self, dsn: str, *, bootstrap: bool) -> None:
                self.dsn = dsn
                self.bootstrap_called = False

            def bootstrap(self) -> None:
                self.bootstrap_called = True

            def healthcheck(self) -> dict[str, object]:
                return {"status": "ok", "backend": "postgres"}

            def schema_report(self) -> dict[str, object]:
                return {"status": "degraded", "backend": "postgres", "missing_tables": ["gk_task_steps"]}

        with (
            patch.object(validate_postgres, "parse_args", return_value=argparse.Namespace(dsn="postgresql://example", no_bootstrap=True)),
            patch.object(validate_postgres, "resolve_dsn", return_value="postgresql://example"),
            patch.object(validate_postgres, "PostgresTaskRepository", FakeRepository),
            patch("builtins.print") as print_mock,
        ):
            code = validate_postgres.main()

        self.assertEqual(code, 1)
        payload = json.loads(print_mock.call_args.args[0])
        self.assertEqual(payload["status"], "degraded")
        self.assertFalse(payload["bootstrapped"])
        self.assertEqual(payload["schema"]["missing_tables"], ["gk_task_steps"])

    def test_main_bootstraps_and_returns_ok_when_health_and_schema_are_ok(self) -> None:
        fake_repository_instances: list[object] = []

        class FakeRepository:
            def __init__(self, dsn: str, *, bootstrap: bool) -> None:
                self.dsn = dsn
                self.bootstrap_called = False
                fake_repository_instances.append(self)

            def bootstrap(self) -> None:
                self.bootstrap_called = True

            def healthcheck(self) -> dict[str, object]:
                return {"status": "ok", "backend": "postgres"}

            def schema_report(self) -> dict[str, object]:
                return {"status": "ok", "backend": "postgres", "schema_version": "0001_initial"}

        with (
            patch.object(validate_postgres, "parse_args", return_value=argparse.Namespace(dsn="postgresql://example", no_bootstrap=False)),
            patch.object(validate_postgres, "resolve_dsn", return_value="postgresql://example"),
            patch.object(validate_postgres, "PostgresTaskRepository", FakeRepository),
            patch("builtins.print") as print_mock,
        ):
            code = validate_postgres.main()

        self.assertEqual(code, 0)
        self.assertEqual(len(fake_repository_instances), 1)
        self.assertTrue(fake_repository_instances[0].bootstrap_called)
        payload = json.loads(print_mock.call_args.args[0])
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["bootstrapped"])

    def test_main_returns_2_when_repository_raises_on_connect(self) -> None:
        with (
            patch.object(
                validate_postgres,
                "parse_args",
                return_value=argparse.Namespace(dsn="postgresql://example", no_bootstrap=False),
            ),
            patch.object(validate_postgres, "resolve_dsn", return_value="postgresql://example"),
            patch.object(
                validate_postgres,
                "PostgresTaskRepository",
                side_effect=RuntimeError("connection refused"),
            ),
            patch("builtins.print") as print_mock,
        ):
            code = validate_postgres.main()

        self.assertEqual(code, 2)
        payload = json.loads(print_mock.call_args.args[0])
        self.assertEqual(payload["status"], "error")
        self.assertIn("connection refused", payload["error"])

    def test_main_returns_1_when_health_degraded(self) -> None:
        class FakeRepository:
            def __init__(self, dsn: str, *, bootstrap: bool) -> None:
                pass

            def bootstrap(self) -> None:
                pass

            def healthcheck(self) -> dict[str, object]:
                return {"status": "degraded", "backend": "postgres"}

            def schema_report(self) -> dict[str, object]:
                return {"status": "ok", "backend": "postgres"}

        with (
            patch.object(
                validate_postgres,
                "parse_args",
                return_value=argparse.Namespace(dsn="postgresql://example", no_bootstrap=False),
            ),
            patch.object(validate_postgres, "resolve_dsn", return_value="postgresql://example"),
            patch.object(validate_postgres, "PostgresTaskRepository", FakeRepository),
            patch("builtins.print") as print_mock,
        ):
            code = validate_postgres.main()

        self.assertEqual(code, 1)
        payload = json.loads(print_mock.call_args.args[0])
        self.assertEqual(payload["status"], "degraded")


if __name__ == "__main__":
    unittest.main()
