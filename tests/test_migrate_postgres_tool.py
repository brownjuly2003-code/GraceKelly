from __future__ import annotations

import unittest
from datetime import UTC, datetime

from gracekelly.tools.migrate_postgres import _json_default


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
