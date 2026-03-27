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
    def test_bool_true_returns_one(self) -> None:
        self.assertEqual(_prometheus_value(True), "1")

    def test_bool_false_returns_zero(self) -> None:
        self.assertEqual(_prometheus_value(False), "0")

    def test_integer(self) -> None:
        self.assertEqual(_prometheus_value(42), "42")

    def test_float(self) -> None:
        self.assertEqual(_prometheus_value(3.14), "3.14")

    def test_string(self) -> None:
        self.assertEqual(_prometheus_value("ok"), "ok")

    def test_zero(self) -> None:
        self.assertEqual(_prometheus_value(0), "0")


class PrometheusLabelsTests(unittest.TestCase):
    def test_empty_returns_empty_string(self) -> None:
        self.assertEqual(_prometheus_labels({}), "")

    def test_none_returns_empty_string(self) -> None:
        self.assertEqual(_prometheus_labels(None), "")

    def test_single_label(self) -> None:
        result = _prometheus_labels({"env": "prod"})
        self.assertEqual(result, '{env="prod"}')

    def test_multiple_labels_sorted(self) -> None:
        result = _prometheus_labels({"z": "last", "a": "first"})
        self.assertIn('a="first"', result)
        self.assertIn('z="last"', result)
        self.assertLess(result.index('a='), result.index('z='))

    def test_escapes_double_quote(self) -> None:
        result = _prometheus_labels({"msg": 'say "hi"'})
        self.assertIn('\\"hi\\"', result)

    def test_escapes_backslash(self) -> None:
        result = _prometheus_labels({"path": "C:\\foo"})
        self.assertIn("\\\\", result)

    def test_escapes_newline(self) -> None:
        result = _prometheus_labels({"msg": "line1\nline2"})
        self.assertIn("\\n", result)

    def test_wraps_in_braces(self) -> None:
        result = _prometheus_labels({"k": "v"})
        self.assertTrue(result.startswith("{"))
        self.assertTrue(result.endswith("}"))


class EmitHelpTests(unittest.TestCase):
    def test_emits_help_line(self) -> None:
        lines: list[str] = []
        _emit_help(lines, "my_metric", "Help text here.")
        self.assertIn("# HELP my_metric Help text here.", lines)

    def test_emits_type_line(self) -> None:
        lines: list[str] = []
        _emit_help(lines, "my_metric", "Help text here.")
        self.assertIn("# TYPE my_metric gauge", lines)

    def test_custom_metric_type(self) -> None:
        lines: list[str] = []
        _emit_help(lines, "my_counter", "A counter.", metric_type="counter")
        self.assertIn("# TYPE my_counter counter", lines)

    def test_two_lines_emitted(self) -> None:
        lines: list[str] = []
        _emit_help(lines, "x", "desc")
        self.assertEqual(len(lines), 2)


class EmitGaugeTests(unittest.TestCase):
    def test_emits_metric_line(self) -> None:
        lines: list[str] = []
        _emit_gauge(lines, "my_gauge", 5)
        self.assertIn("my_gauge 5", lines)

    def test_emits_with_labels(self) -> None:
        lines: list[str] = []
        _emit_gauge(lines, "my_gauge", 1, labels={"model_id": "gpt-4o"})
        self.assertEqual(len(lines), 1)
        self.assertIn('model_id="gpt-4o"', lines[0])
        self.assertIn(" 1", lines[0])

    def test_bool_value_encoded(self) -> None:
        lines: list[str] = []
        _emit_gauge(lines, "flag", True)
        self.assertIn("flag 1", lines)

    def test_no_labels_no_braces(self) -> None:
        lines: list[str] = []
        _emit_gauge(lines, "m", 0)
        self.assertEqual(lines[0], "m 0")


class EmitOneHotTests(unittest.TestCase):
    def test_active_value_emits_one(self) -> None:
        lines: list[str] = []
        _emit_one_hot(lines, "state", label_name="status", actual="ok", allowed=("ok", "degraded", "failed"))
        ok_line = next(line for line in lines if '"ok"' in line)
        self.assertIn(" 1", ok_line)

    def test_inactive_values_emit_zero(self) -> None:
        lines: list[str] = []
        _emit_one_hot(lines, "state", label_name="status", actual="ok", allowed=("ok", "degraded", "failed"))
        degraded_line = next(line for line in lines if '"degraded"' in line)
        self.assertIn(" 0", degraded_line)

    def test_emits_all_allowed_values(self) -> None:
        lines: list[str] = []
        allowed = ("a", "b", "c")
        _emit_one_hot(lines, "m", label_name="k", actual="a", allowed=allowed)
        self.assertEqual(len(lines), len(allowed))

    def test_extra_labels_included(self) -> None:
        lines: list[str] = []
        _emit_one_hot(lines, "m", label_name="status", actual="ok", allowed=("ok",), labels={"env": "prod"})
        self.assertTrue(any('env="prod"' in line for line in lines))


if __name__ == "__main__":
    unittest.main()
