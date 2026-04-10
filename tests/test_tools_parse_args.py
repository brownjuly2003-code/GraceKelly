"""Tests for parse_args() and __main__ entry points across all tools.

Covers uncovered lines: parse_args functions + if __name__ == '__main__' blocks.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch


class ValidatePostgresParseArgsTests(unittest.TestCase):
    @patch("sys.argv", ["prog", "--dsn", "postgresql://host/db", "--no-bootstrap"])
    def test_all_flags(self) -> None:
        from gracekelly.tools.validate_postgres import parse_args

        args = parse_args()
        self.assertEqual(args.dsn, "postgresql://host/db")
        self.assertTrue(args.no_bootstrap)

    @patch("sys.argv", ["prog"])
    def test_defaults(self) -> None:
        from gracekelly.tools.validate_postgres import parse_args

        args = parse_args()
        self.assertIsNone(args.dsn)
        self.assertFalse(args.no_bootstrap)


class MigratePostgresParseArgsTests(unittest.TestCase):
    @patch("sys.argv", ["prog", "--dsn", "postgresql://host/db", "--dry-run"])
    def test_all_flags(self) -> None:
        from gracekelly.tools.migrate_postgres import parse_args

        args = parse_args()
        self.assertEqual(args.dsn, "postgresql://host/db")
        self.assertTrue(args.dry_run)

    @patch("sys.argv", ["prog"])
    def test_defaults(self) -> None:
        from gracekelly.tools.migrate_postgres import parse_args

        args = parse_args()
        self.assertIsNone(args.dsn)
        self.assertFalse(args.dry_run)


class InspectSnapshotParseArgsTests(unittest.TestCase):
    @patch("sys.argv", ["prog", "--input", "/tmp/snap.json"])
    def test_required_input(self) -> None:
        from gracekelly.tools.inspect_snapshot import parse_args

        args = parse_args()
        self.assertEqual(args.input, "/tmp/snap.json")

    @patch("sys.argv", ["prog"])
    def test_missing_input_exits(self) -> None:
        from gracekelly.tools.inspect_snapshot import parse_args

        with self.assertRaises(SystemExit):
            parse_args()


class ExportPostgresParseArgsTests(unittest.TestCase):
    @patch("sys.argv", [
        "prog", "--dsn", "postgresql://host/db",
        "--output", "/tmp/out.json",
        "--task-id", "t1", "--task-id", "t2",
        "--limit", "50",
    ])
    def test_all_flags(self) -> None:
        from gracekelly.tools.export_postgres import parse_args

        args = parse_args()
        self.assertEqual(args.dsn, "postgresql://host/db")
        self.assertEqual(args.output, "/tmp/out.json")
        self.assertEqual(args.task_ids, ["t1", "t2"])
        self.assertEqual(args.limit, 50)

    @patch("sys.argv", ["prog"])
    def test_defaults(self) -> None:
        from gracekelly.tools.export_postgres import parse_args

        args = parse_args()
        self.assertIsNone(args.dsn)
        self.assertIsNone(args.output)
        self.assertEqual(args.task_ids, [])
        self.assertEqual(args.limit, 100)


class ImportPostgresParseArgsTests(unittest.TestCase):
    @patch("sys.argv", [
        "prog", "--dsn", "postgresql://host/db",
        "--input", "/tmp/snap.json",
        "--task-id", "t1",
        "--allow-degraded-schema",
        "--dry-run",
    ])
    def test_all_flags(self) -> None:
        from gracekelly.tools.import_postgres import parse_args

        args = parse_args()
        self.assertEqual(args.dsn, "postgresql://host/db")
        self.assertEqual(args.input, "/tmp/snap.json")
        self.assertEqual(args.task_ids, ["t1"])
        self.assertTrue(args.allow_degraded_schema)
        self.assertTrue(args.dry_run)

    @patch("sys.argv", ["prog", "--input", "/tmp/snap.json"])
    def test_defaults(self) -> None:
        from gracekelly.tools.import_postgres import parse_args

        args = parse_args()
        self.assertIsNone(args.dsn)
        self.assertEqual(args.task_ids, [])
        self.assertFalse(args.allow_degraded_schema)
        self.assertFalse(args.dry_run)


class CreatePerplexityProfileParseArgsTests(unittest.TestCase):
    @patch("sys.argv", ["prog", "--profile-dir", "/tmp/profile", "--base-url", "https://example.com", "--channel", "firefox"])
    def test_all_flags(self) -> None:
        from gracekelly.tools.create_perplexity_profile import parse_args

        args = parse_args()
        self.assertEqual(args.profile_dir, "/tmp/profile")
        self.assertEqual(args.base_url, "https://example.com")
        self.assertEqual(args.channel, "firefox")

    @patch("sys.argv", ["prog"])
    def test_defaults(self) -> None:
        from gracekelly.tools.create_perplexity_profile import parse_args

        args = parse_args()
        self.assertIsNone(args.profile_dir)


class CapturePerplexityReconParseArgsTests(unittest.TestCase):
    @patch("sys.argv", [
        "prog",
        "--profile-dir", "/tmp/profile",
        "--output-dir", "/tmp/out",
        "--base-url", "https://example.com",
        "--channel", "firefox",
        "--interactive-pause",
        "--prompt", "test question",
        "--timeout-seconds", "30",
    ])
    def test_all_flags(self) -> None:
        from gracekelly.tools.capture_perplexity_recon import parse_args

        args = parse_args()
        self.assertEqual(args.profile_dir, "/tmp/profile")
        self.assertEqual(args.output_dir, "/tmp/out")
        self.assertEqual(args.base_url, "https://example.com")
        self.assertEqual(args.channel, "firefox")
        self.assertTrue(args.interactive_pause)
        self.assertEqual(args.prompt, "test question")
        self.assertEqual(args.timeout_seconds, 30)

    @patch("sys.argv", ["prog"])
    def test_defaults(self) -> None:
        from gracekelly.tools.capture_perplexity_recon import parse_args

        args = parse_args()
        self.assertIsNone(args.profile_dir)
        self.assertIsNone(args.output_dir)
        self.assertFalse(args.interactive_pause)
        self.assertIsNone(args.prompt)
        self.assertEqual(args.timeout_seconds, 60)


class CreatePerplexityProfileMainTests(unittest.TestCase):
    @patch("gracekelly.tools.create_perplexity_profile.create_profile", side_effect=RuntimeError("no playwright"))
    @patch("sys.argv", ["prog"])
    def test_main_returns_2_on_exception(self, mock_create: MagicMock) -> None:
        from gracekelly.tools.create_perplexity_profile import main

        result = main()
        self.assertEqual(result, 2)

    @patch("gracekelly.tools.create_perplexity_profile.create_profile")
    @patch("sys.argv", ["prog", "--profile-dir", "/tmp/profile"])
    def test_main_returns_0_on_success(self, mock_create: MagicMock) -> None:
        from gracekelly.tools.create_perplexity_profile import main

        result = main()
        self.assertEqual(result, 0)
        mock_create.assert_called_once()


class CapturePerplexityReconMainTests(unittest.TestCase):
    @patch("gracekelly.tools.capture_perplexity_recon.capture_recon", side_effect=RuntimeError("fail"))
    @patch("sys.argv", ["prog"])
    def test_main_returns_2_on_exception(self, mock_capture: MagicMock) -> None:
        from gracekelly.tools.capture_perplexity_recon import main

        result = main()
        self.assertEqual(result, 2)

    @patch("gracekelly.tools.capture_perplexity_recon.capture_recon")
    @patch("sys.argv", ["prog", "--profile-dir", "/tmp/p"])
    def test_main_returns_0_on_success(self, mock_capture: MagicMock) -> None:
        from gracekelly.tools.capture_perplexity_recon import main

        result = main()
        self.assertEqual(result, 0)
        mock_capture.assert_called_once()


class MigratePostgresMainEntryTests(unittest.TestCase):
    @patch("sys.argv", ["prog", "--dsn", "postgresql://h/db", "--dry-run"])
    def test_main_dry_run_no_pending(self) -> None:
        from gracekelly.tools.migrate_postgres import main

        with patch("gracekelly.tools.migrate_postgres.PostgresTaskRepository") as mock_cls:
            mock_repo = MagicMock()
            mock_cls.return_value = mock_repo
            mock_repo.applied_migrations.return_value = ["0001_initial"]
            result = main()
            self.assertEqual(result, 0)
            mock_cls.assert_called_once_with("postgresql://h/db", bootstrap=False)
