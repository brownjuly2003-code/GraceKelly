from __future__ import annotations

import unittest
from enum import Enum

from gracekelly.logging_utils import format_log_kv, log_message, trace_id_from_metadata


class FormatLogKvTests(unittest.TestCase):
    def test_string_value_quoted(self) -> None:
        result = format_log_kv(name="hello")
        self.assertEqual(result, 'name="hello"')

    def test_int_value_unquoted(self) -> None:
        result = format_log_kv(count=42)
        self.assertEqual(result, "count=42")

    def test_bool_values(self) -> None:
        result = format_log_kv(flag=True)
        self.assertEqual(result, "flag=true")
        result = format_log_kv(flag=False)
        self.assertEqual(result, "flag=false")

    def test_none_values_skipped(self) -> None:
        result = format_log_kv(a="yes", b=None, c=1)
        self.assertNotIn("b=", result)
        self.assertIn('a="yes"', result)
        self.assertIn("c=1", result)

    def test_keys_sorted(self) -> None:
        result = format_log_kv(z=1, a=2)
        self.assertTrue(result.startswith("a="))

    def test_enum_value_used(self) -> None:
        class Color(Enum):
            RED = "red"

        result = format_log_kv(color=Color.RED)
        self.assertEqual(result, 'color="red"')

    def test_empty_context(self) -> None:
        self.assertEqual(format_log_kv(), "")


class LogMessageTests(unittest.TestCase):
    def test_event_only(self) -> None:
        self.assertEqual(log_message("test.event"), "test.event")

    def test_event_with_context(self) -> None:
        result = log_message("task.created", task_id="t1")
        self.assertEqual(result, 'task.created task_id="t1"')


class TraceIdFromMetadataTests(unittest.TestCase):
    def test_none_metadata(self) -> None:
        self.assertIsNone(trace_id_from_metadata(None))

    def test_missing_trace_id(self) -> None:
        self.assertIsNone(trace_id_from_metadata({"other": "value"}))

    def test_valid_trace_id(self) -> None:
        self.assertEqual(trace_id_from_metadata({"trace_id": "abc-123"}), "abc-123")

    def test_non_string_trace_id(self) -> None:
        self.assertIsNone(trace_id_from_metadata({"trace_id": 42}))

    def test_empty_string_trace_id(self) -> None:
        self.assertIsNone(trace_id_from_metadata({"trace_id": ""}))

    def test_whitespace_only_trace_id(self) -> None:
        self.assertIsNone(trace_id_from_metadata({"trace_id": "   "}))

    def test_trace_id_stripped(self) -> None:
        self.assertEqual(trace_id_from_metadata({"trace_id": "  abc  "}), "abc")
