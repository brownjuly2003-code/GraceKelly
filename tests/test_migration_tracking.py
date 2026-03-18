from __future__ import annotations

import unittest

from gracekelly.storage.schema import (
    MIGRATION_TRACKING_DDL,
    discover_migrations,
    load_migration_sql,
    split_sql_statements,
)


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
