from __future__ import annotations

import unittest

from gracekelly.api.routes.health import (
    _emit_gauge,
    _emit_help,
    _emit_one_hot,
    _prometheus_labels,
    _prometheus_value,
)


class PrometheusValueTests(unittest.TestCase):
    def test_true_returns_one(self) -> None:
        self.assertEqual(_prometheus_value(True), "1")

    def test_false_returns_zero(self) -> None:
        self.assertEqual(_prometheus_value(False), "0")

    def test_integer_returns_string(self) -> None:
        self.assertEqual(_prometheus_value(42), "42")

    def test_zero_returns_string_zero(self) -> None:
        self.assertEqual(_prometheus_value(0), "0")

    def test_float_returns_string(self) -> None:
        self.assertEqual(_prometheus_value(3.14), "3.14")

    def test_string_returned_as_is(self) -> None:
        self.assertEqual(_prometheus_value("hello"), "hello")


class PrometheusLabelsTests(unittest.TestCase):
    def test_none_returns_empty_string(self) -> None:
        self.assertEqual(_prometheus_labels(None), "")

    def test_empty_dict_returns_empty_string(self) -> None:
        self.assertEqual(_prometheus_labels({}), "")

    def test_single_label(self) -> None:
        self.assertEqual(_prometheus_labels({"key": "val"}), '{key="val"}')

    def test_labels_sorted_by_key(self) -> None:
        result = _prometheus_labels({"z": "last", "a": "first"})
        self.assertTrue(result.index("a=") < result.index("z="))

    def test_multiple_labels_joined(self) -> None:
        result = _prometheus_labels({"a": "1", "b": "2"})
        self.assertIn('a="1"', result)
        self.assertIn('b="2"', result)

    def test_double_quote_escaped(self) -> None:
        result = _prometheus_labels({"k": 'say "hello"'})
        self.assertIn('\\"hello\\"', result)

    def test_backslash_escaped(self) -> None:
        result = _prometheus_labels({"k": "a\\b"})
        self.assertIn("a\\\\b", result)

    def test_newline_escaped(self) -> None:
        result = _prometheus_labels({"k": "line1\nline2"})
        self.assertIn("\\n", result)

    def test_non_string_value_converted(self) -> None:
        result = _prometheus_labels({"count": 5})
        self.assertIn('count="5"', result)


class EmitHelpTests(unittest.TestCase):
    def test_emits_help_line(self) -> None:
        lines: list[str] = []
        _emit_help(lines, "my_metric", "My help text")
        self.assertTrue(any("HELP my_metric My help text" in line for line in lines))

    def test_emits_type_line(self) -> None:
        lines: list[str] = []
        _emit_help(lines, "my_metric", "help")
        self.assertTrue(any("TYPE my_metric gauge" in line for line in lines))

    def test_custom_metric_type(self) -> None:
        lines: list[str] = []
        _emit_help(lines, "my_counter", "help", metric_type="counter")
        self.assertTrue(any("TYPE my_counter counter" in line for line in lines))

    def test_emits_two_lines(self) -> None:
        lines: list[str] = []
        _emit_help(lines, "x", "h")
        self.assertEqual(len(lines), 2)


class EmitGaugeTests(unittest.TestCase):
    def test_no_labels_format(self) -> None:
        lines: list[str] = []
        _emit_gauge(lines, "my_metric", 7)
        self.assertEqual(lines[0], "my_metric 7")

    def test_with_labels_format(self) -> None:
        lines: list[str] = []
        _emit_gauge(lines, "my_metric", 3, labels={"env": "prod"})
        self.assertIn('env="prod"', lines[0])
        self.assertIn("3", lines[0])

    def test_bool_value_rendered_as_0_or_1(self) -> None:
        lines: list[str] = []
        _emit_gauge(lines, "flag", True)
        self.assertEqual(lines[0], "flag 1")


class EmitOneHotTests(unittest.TestCase):
    def test_actual_candidate_gets_one(self) -> None:
        lines: list[str] = []
        _emit_one_hot(
            lines,
            "my_state",
            label_name="status",
            actual="ok",
            allowed=("ok", "failed"),
        )
        ok_line = next(ln for ln in lines if 'status="ok"' in ln)
        self.assertIn(" 1", ok_line)

    def test_non_actual_candidate_gets_zero(self) -> None:
        lines: list[str] = []
        _emit_one_hot(
            lines,
            "my_state",
            label_name="status",
            actual="ok",
            allowed=("ok", "failed"),
        )
        failed_line = next(ln for ln in lines if 'status="failed"' in ln)
        self.assertIn(" 0", failed_line)

    def test_emits_one_line_per_candidate(self) -> None:
        lines: list[str] = []
        _emit_one_hot(
            lines,
            "x",
            label_name="s",
            actual="a",
            allowed=("a", "b", "c"),
        )
        self.assertEqual(len(lines), 3)

    def test_extra_labels_included(self) -> None:
        lines: list[str] = []
        _emit_one_hot(
            lines,
            "x",
            label_name="s",
            actual="a",
            allowed=("a", "b"),
            labels={"env": "prod"},
        )
        self.assertTrue(all('env="prod"' in ln for ln in lines))

    def test_unknown_actual_all_zeros(self) -> None:
        lines: list[str] = []
        _emit_one_hot(
            lines,
            "x",
            label_name="s",
            actual="missing",
            allowed=("a", "b"),
        )
        self.assertTrue(all(ln.endswith(" 0") for ln in lines))


if __name__ == "__main__":
    unittest.main()
