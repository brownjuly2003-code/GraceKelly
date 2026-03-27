from __future__ import annotations

import unittest

from gracekelly.storage.schema import (
    EXPECTED_SCHEMA_COLUMNS,
    INITIAL_MIGRATION_NAME,
    compute_schema_diff,
    discover_migrations,
    load_migration_sql,
    split_sql_statements,
)


class SplitSqlStatementsTests(unittest.TestCase):
    def test_single_statement(self) -> None:
        sql = "CREATE TABLE foo (id INT)"
        result = split_sql_statements(sql + ";")
        self.assertEqual(result, ["CREATE TABLE foo (id INT)"])

    def test_multiple_statements(self) -> None:
        sql = "CREATE TABLE a (id INT); CREATE TABLE b (id INT);"
        result = split_sql_statements(sql)
        self.assertEqual(len(result), 2)
        self.assertIn("CREATE TABLE a (id INT)", result)

    def test_filters_empty_statements(self) -> None:
        sql = "SELECT 1;;; SELECT 2"
        result = split_sql_statements(sql)
        self.assertEqual(len(result), 2)

    def test_strips_whitespace(self) -> None:
        sql = "  CREATE TABLE x (id INT)  ;  CREATE TABLE y (id INT)  ;"
        result = split_sql_statements(sql)
        self.assertTrue(all(s == s.strip() for s in result))

    def test_empty_sql_returns_empty(self) -> None:
        self.assertEqual(split_sql_statements(""), [])

    def test_only_semicolons_returns_empty(self) -> None:
        self.assertEqual(split_sql_statements(";;;"), [])

    def test_no_trailing_semicolon(self) -> None:
        sql = "SELECT 1"
        result = split_sql_statements(sql)
        self.assertEqual(result, ["SELECT 1"])


class ComputeSchemaDiffTests(unittest.TestCase):
    def test_no_diff_when_all_columns_present(self) -> None:
        actual = {
            table: list(columns)
            for table, columns in EXPECTED_SCHEMA_COLUMNS.items()
        }
        diff = compute_schema_diff(actual)
        self.assertEqual(diff["missing_tables"], [])
        self.assertEqual(diff["missing_columns"], {})

    def test_detects_missing_table(self) -> None:
        diff = compute_schema_diff({})
        missing = diff["missing_tables"]
        assert isinstance(missing, list)
        self.assertIn("gk_tasks", missing)
        self.assertIn("gk_task_steps", missing)
        self.assertIn("gk_task_events", missing)

    def test_detects_missing_column(self) -> None:
        actual = {
            "gk_tasks": [c for c in EXPECTED_SCHEMA_COLUMNS["gk_tasks"] if c != "status"],
            "gk_task_steps": list(EXPECTED_SCHEMA_COLUMNS["gk_task_steps"]),
            "gk_task_events": list(EXPECTED_SCHEMA_COLUMNS["gk_task_events"]),
        }
        diff = compute_schema_diff(actual)
        missing_cols = diff["missing_columns"]
        assert isinstance(missing_cols, dict)
        self.assertIn("gk_tasks", missing_cols)
        self.assertIn("status", missing_cols["gk_tasks"])

    def test_no_spurious_columns_reported(self) -> None:
        """Extra columns in actual schema do not appear in diff."""
        actual = {
            table: list(columns) + ["extra_col"]
            for table, columns in EXPECTED_SCHEMA_COLUMNS.items()
        }
        diff = compute_schema_diff(actual)
        self.assertEqual(diff["missing_tables"], [])
        self.assertEqual(diff["missing_columns"], {})

    def test_returns_sorted_missing_tables(self) -> None:
        diff = compute_schema_diff({})
        missing = diff["missing_tables"]
        assert isinstance(missing, list)
        self.assertEqual(missing, sorted(missing))

    def test_partial_table_coverage(self) -> None:
        actual = {
            "gk_tasks": list(EXPECTED_SCHEMA_COLUMNS["gk_tasks"]),
        }
        diff = compute_schema_diff(actual)
        missing = diff["missing_tables"]
        assert isinstance(missing, list)
        self.assertNotIn("gk_tasks", missing)
        self.assertIn("gk_task_steps", missing)


class DiscoverMigrationsTests(unittest.TestCase):
    def test_returns_list(self) -> None:
        migrations = discover_migrations()
        self.assertIsInstance(migrations, list)

    def test_non_empty(self) -> None:
        migrations = discover_migrations()
        self.assertGreater(len(migrations), 0)

    def test_contains_initial_migration(self) -> None:
        migrations = discover_migrations()
        self.assertIn(INITIAL_MIGRATION_NAME, migrations)

    def test_sorted(self) -> None:
        migrations = discover_migrations()
        self.assertEqual(migrations, sorted(migrations))

    def test_no_sql_extension(self) -> None:
        migrations = discover_migrations()
        self.assertTrue(all(not m.endswith(".sql") for m in migrations))


class LoadMigrationSqlTests(unittest.TestCase):
    def test_loads_initial_migration(self) -> None:
        sql = load_migration_sql()
        self.assertIsInstance(sql, str)
        self.assertGreater(len(sql), 0)

    def test_initial_migration_contains_create_table(self) -> None:
        sql = load_migration_sql()
        self.assertIn("CREATE TABLE", sql.upper())

    def test_loads_named_migration(self) -> None:
        sql = load_migration_sql(INITIAL_MIGRATION_NAME)
        self.assertIsInstance(sql, str)
        self.assertGreater(len(sql), 0)

    def test_initial_migration_creates_gk_tasks(self) -> None:
        sql = load_migration_sql()
        self.assertIn("gk_tasks", sql)


if __name__ == "__main__":
    unittest.main()
