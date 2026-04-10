from __future__ import annotations

import unittest
from typing import cast

from gracekelly.storage.schema import compute_schema_diff, split_sql_statements


class SplitSqlStatementsTests(unittest.TestCase):
    def test_single_statement_no_semicolon_returns_one(self) -> None:
        result = split_sql_statements("SELECT 1")
        self.assertEqual(result, ["SELECT 1"])

    def test_trailing_semicolon_returns_one(self) -> None:
        result = split_sql_statements("SELECT 1;")
        self.assertEqual(result, ["SELECT 1"])

    def test_two_statements_split_correctly(self) -> None:
        result = split_sql_statements("SELECT 1; SELECT 2")
        self.assertEqual(len(result), 2)
        self.assertIn("SELECT 1", result)
        self.assertIn("SELECT 2", result)

    def test_empty_string_returns_empty_list(self) -> None:
        self.assertEqual(split_sql_statements(""), [])

    def test_only_semicolons_returns_empty_list(self) -> None:
        self.assertEqual(split_sql_statements(";;;"), [])

    def test_whitespace_only_segments_filtered_out(self) -> None:
        result = split_sql_statements("SELECT 1;  ;SELECT 2")
        self.assertEqual(len(result), 2)

    def test_statements_are_stripped(self) -> None:
        result = split_sql_statements("  SELECT 1  ;  SELECT 2  ")
        self.assertEqual(result[0], "SELECT 1")
        self.assertEqual(result[1], "SELECT 2")

    def test_multiline_statement_stripped(self) -> None:
        sql = "CREATE TABLE foo (\n    id TEXT\n);"
        result = split_sql_statements(sql)
        self.assertEqual(len(result), 1)
        self.assertIn("CREATE TABLE", result[0])


class ComputeSchemaDiffTests(unittest.TestCase):
    def _all_ok_columns(self) -> dict[str, list[str]]:
        from gracekelly.storage.schema import EXPECTED_SCHEMA_COLUMNS
        return {table: list(cols) for table, cols in EXPECTED_SCHEMA_COLUMNS.items()}

    def test_exact_match_returns_no_missing(self) -> None:
        diff = compute_schema_diff(self._all_ok_columns())
        self.assertEqual(diff["missing_tables"], [])
        self.assertEqual(diff["missing_columns"], {})

    def test_missing_table_reported(self) -> None:
        actual = self._all_ok_columns()
        del actual["gk_task_steps"]
        diff = compute_schema_diff(actual)
        missing_tables = cast(list[str], diff["missing_tables"])
        self.assertIn("gk_task_steps", missing_tables)

    def test_extra_table_ignored(self) -> None:
        actual = self._all_ok_columns()
        actual["extra_table"] = ["id"]
        diff = compute_schema_diff(actual)
        missing_tables = cast(list[str], diff["missing_tables"])
        self.assertNotIn("extra_table", missing_tables)

    def test_missing_column_reported(self) -> None:
        actual = self._all_ok_columns()
        actual["gk_tasks"] = [c for c in actual["gk_tasks"] if c != "status"]
        diff = compute_schema_diff(actual)
        missing_columns = cast(dict[str, list[str]], diff["missing_columns"])
        self.assertIn("gk_tasks", missing_columns)
        self.assertIn("status", missing_columns["gk_tasks"])

    def test_extra_column_ignored(self) -> None:
        actual = self._all_ok_columns()
        actual["gk_tasks"].append("custom_column")
        diff = compute_schema_diff(actual)
        missing_columns = cast(dict[str, list[str]], diff["missing_columns"])
        self.assertNotIn("gk_tasks", missing_columns)

    def test_multiple_missing_tables_all_reported(self) -> None:
        actual: dict[str, list[str]] = {}
        diff = compute_schema_diff(actual)
        missing_tables = cast(list[str], diff["missing_tables"])
        self.assertEqual(len(missing_tables), 3)

    def test_missing_tables_sorted(self) -> None:
        actual: dict[str, list[str]] = {}
        diff = compute_schema_diff(actual)
        missing_tables = cast(list[str], diff["missing_tables"])
        self.assertEqual(missing_tables, sorted(missing_tables))

    def test_missing_column_in_events_table(self) -> None:
        actual = self._all_ok_columns()
        actual["gk_task_events"] = [c for c in actual["gk_task_events"] if c != "payload"]
        diff = compute_schema_diff(actual)
        missing_columns = cast(dict[str, list[str]], diff["missing_columns"])
        self.assertIn("gk_task_events", missing_columns)
        self.assertIn("payload", missing_columns["gk_task_events"])

    def test_empty_actual_columns_for_existing_table(self) -> None:
        actual = self._all_ok_columns()
        actual["gk_tasks"] = []
        diff = compute_schema_diff(actual)
        missing_columns = cast(dict[str, list[str]], diff["missing_columns"])
        self.assertIn("gk_tasks", missing_columns)
        from gracekelly.storage.schema import EXPECTED_SCHEMA_COLUMNS
        for col in EXPECTED_SCHEMA_COLUMNS["gk_tasks"]:
            self.assertIn(col, missing_columns["gk_tasks"])


if __name__ == "__main__":
    unittest.main()
