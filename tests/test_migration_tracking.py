from __future__ import annotations

import unittest

from gracekelly.storage.schema import (
    EXPECTED_SCHEMA_COLUMNS,
    MIGRATION_TRACKING_DDL,
    compute_schema_diff,
    discover_migrations,
    load_migration_sql,
    split_sql_statements,
)


class SplitSqlStatementsTests(unittest.TestCase):
    def test_single_statement_returned(self) -> None:
        self.assertEqual(split_sql_statements("SELECT 1"), ["SELECT 1"])

    def test_two_statements_split_on_semicolon(self) -> None:
        result = split_sql_statements("SELECT 1; SELECT 2")
        self.assertEqual(result, ["SELECT 1", "SELECT 2"])

    def test_trailing_semicolon_not_extra_element(self) -> None:
        result = split_sql_statements("SELECT 1;")
        self.assertEqual(result, ["SELECT 1"])

    def test_empty_string_returns_empty_list(self) -> None:
        self.assertEqual(split_sql_statements(""), [])

    def test_whitespace_only_between_semicolons_skipped(self) -> None:
        result = split_sql_statements("SELECT 1;   ; SELECT 2")
        self.assertEqual(result, ["SELECT 1", "SELECT 2"])

    def test_leading_whitespace_stripped_from_statements(self) -> None:
        result = split_sql_statements("  SELECT 1  ;  SELECT 2  ")
        self.assertEqual(result, ["SELECT 1", "SELECT 2"])


class ComputeSchemaDiffTests(unittest.TestCase):
    def test_full_match_returns_empty_diffs(self) -> None:
        """When actual columns match expected exactly, no diff is reported."""
        actual = {
            table: list(cols)
            for table, cols in EXPECTED_SCHEMA_COLUMNS.items()
        }
        diff = compute_schema_diff(actual)
        self.assertEqual(diff["missing_tables"], [])
        self.assertEqual(diff["missing_columns"], {})

    def test_missing_table_reported(self) -> None:
        diff = compute_schema_diff({})
        self.assertIn("gk_tasks", diff["missing_tables"])
        self.assertIn("gk_task_steps", diff["missing_tables"])
        self.assertIn("gk_task_events", diff["missing_tables"])

    def test_extra_table_not_reported(self) -> None:
        actual = {
            table: list(cols)
            for table, cols in EXPECTED_SCHEMA_COLUMNS.items()
        }
        actual["gk_extra_table"] = ["col1"]
        diff = compute_schema_diff(actual)
        self.assertEqual(diff["missing_tables"], [])
        self.assertNotIn("gk_extra_table", diff["missing_columns"])

    def test_missing_column_reported(self) -> None:
        actual = {
            "gk_tasks": [c for c in EXPECTED_SCHEMA_COLUMNS["gk_tasks"] if c != "prompt"],
            "gk_task_steps": list(EXPECTED_SCHEMA_COLUMNS["gk_task_steps"]),
            "gk_task_events": list(EXPECTED_SCHEMA_COLUMNS["gk_task_events"]),
        }
        diff = compute_schema_diff(actual)
        self.assertIn("gk_tasks", diff["missing_columns"])
        self.assertIn("prompt", diff["missing_columns"]["gk_tasks"])

    def test_table_with_all_columns_not_in_missing_columns(self) -> None:
        actual = {
            table: list(cols)
            for table, cols in EXPECTED_SCHEMA_COLUMNS.items()
        }
        diff = compute_schema_diff(actual)
        self.assertNotIn("gk_tasks", diff["missing_columns"])

    def test_missing_tables_sorted(self) -> None:
        diff = compute_schema_diff({})
        self.assertEqual(diff["missing_tables"], sorted(diff["missing_tables"]))


class MigrationDiscoveryTests(unittest.TestCase):
    def test_discovers_initial_migration(self) -> None:
        migrations = discover_migrations()
        self.assertIn("0001_initial", migrations)

    def test_migrations_are_sorted(self) -> None:
        migrations = discover_migrations()
        self.assertEqual(migrations, sorted(migrations))

    def test_all_discovered_migrations_are_loadable(self) -> None:
        for name in discover_migrations():
            sql = load_migration_sql(name)
            self.assertTrue(sql.strip())
            statements = split_sql_statements(sql)
            self.assertGreater(len(statements), 0)

    def test_tracking_ddl_is_valid_sql(self) -> None:
        self.assertIn("gk_schema_migrations", MIGRATION_TRACKING_DDL)
        self.assertIn("CREATE TABLE", MIGRATION_TRACKING_DDL)
        self.assertIn("IF NOT EXISTS", MIGRATION_TRACKING_DDL)

    def test_tracking_ddl_has_name_and_applied_at(self) -> None:
        self.assertIn("name", MIGRATION_TRACKING_DDL)
        self.assertIn("applied_at", MIGRATION_TRACKING_DDL)


if __name__ == "__main__":
    unittest.main()
