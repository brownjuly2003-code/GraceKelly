from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import MagicMock, patch

from gracekelly.api.routes.health import (
    _build_metrics_payload,
    _emit_gauge,
    _emit_help,
    _emit_one_hot,
    _prometheus_labels,
    _prometheus_value,
)
from gracekelly.request_metrics import RequestMetrics


def _mock_readiness() -> dict[str, Any]:
    return {
        "status": "ok",
        "environment": "test",
        "execution_profile": "dry-run",
        "components": [
            {
                "name": "memory",
                "kind": "storage",
                "status": "ok",
                "required": True,
                "details": {},
            },
            {
                "name": "execution",
                "kind": "execution",
                "status": "ok",
                "required": True,
                "details": {
                    "active_model_executions": 0,
                    "active_by_model": {},
                    "model_limits": {},
                    "saturated_models": [],
                },
            },
        ],
    }


def _call_metrics(readiness: dict[str, Any], request_metrics: RequestMetrics | None = None) -> str:
    profile = MagicMock()
    profile.name = "dry-run"
    with patch(
        "gracekelly.api.routes.health._build_readiness_payload",
        return_value=readiness,
    ):
        return _build_metrics_payload(
            environment="test",
            storage_backend="memory",
            profile=profile,
            repository=None,
            adapters={},
            execution_router=None,
            request_metrics=request_metrics,
        )


class BuildMetricsPayloadRequestMetricsTests(unittest.TestCase):
    def _call(self, request_metrics: RequestMetrics) -> str:
        return _call_metrics(_mock_readiness(), request_metrics)

    def test_recorded_requests_emit_http_requests_total(self) -> None:
        rm = RequestMetrics()
        rm.record_request("/api/v1/smart", 200)
        output = self._call(rm)
        self.assertIn("gracekelly_http_requests_total", output)
        self.assertIn("/api/v1/smart", output)

    def test_recorded_adapter_errors_emit_adapter_errors_total(self) -> None:
        rm = RequestMetrics()
        rm.record_adapter_error("api.mistral", "rate_limited")
        output = self._call(rm)
        self.assertIn("gracekelly_adapter_errors_total", output)
        self.assertIn("rate_limited", output)

    def test_empty_request_metrics_emits_no_http_requests_total(self) -> None:
        rm = RequestMetrics()
        output = self._call(rm)
        self.assertNotIn("gracekelly_http_requests_total", output)

    def test_empty_adapter_errors_emits_no_adapter_errors_total(self) -> None:
        rm = RequestMetrics()
        output = self._call(rm)
        self.assertNotIn("gracekelly_adapter_errors_total", output)

    def test_latency_recorded_emits_histogram(self) -> None:
        rm = RequestMetrics()
        rm.record_request_latency("/api/v1/orchestrate", 0.05)
        output = self._call(rm)
        self.assertIn("gracekelly_http_request_duration_seconds", output)
        self.assertIn("+Inf", output)
        self.assertIn("/api/v1/orchestrate", output)

    def test_latency_histogram_emits_sum_and_count(self) -> None:
        rm = RequestMetrics()
        rm.record_request_latency("/x", 0.1)
        rm.record_request_latency("/x", 0.2)
        output = self._call(rm)
        self.assertIn("gracekelly_http_request_duration_seconds_sum", output)
        self.assertIn("gracekelly_http_request_duration_seconds_count", output)

    def test_no_latency_emits_no_histogram(self) -> None:
        rm = RequestMetrics()
        output = self._call(rm)
        self.assertNotIn("gracekelly_http_request_duration_seconds", output)

    def test_latency_histogram_type_is_histogram(self) -> None:
        rm = RequestMetrics()
        rm.record_request_latency("/api/v1/smart", 0.25)
        output = self._call(rm)
        self.assertIn("# TYPE gracekelly_http_request_duration_seconds histogram", output)


class BuildMetricsPayloadStorageCountsTests(unittest.TestCase):
    def _readiness_with_storage_details(self, details: dict[str, Any]) -> dict[str, Any]:
        r = _mock_readiness()
        for c in r["components"]:
            if c["kind"] == "storage":
                c["details"] = details
        return r

    def test_task_count_in_storage_emits_metric(self) -> None:
        readiness = self._readiness_with_storage_details({"task_count": 42, "step_count": 10, "event_count": 5})
        output = _call_metrics(readiness)
        self.assertIn("gracekelly_storage_task_count", output)
        self.assertIn("gracekelly_storage_step_count", output)
        self.assertIn("gracekelly_storage_event_count", output)

    def test_only_task_count_emits_only_task_metric(self) -> None:
        readiness = self._readiness_with_storage_details({"task_count": 7})
        output = _call_metrics(readiness)
        self.assertIn("gracekelly_storage_task_count", output)
        self.assertNotIn("gracekelly_storage_step_count", output)
        self.assertNotIn("gracekelly_storage_event_count", output)

    def test_empty_storage_details_emits_no_count_metrics(self) -> None:
        output = _call_metrics(_mock_readiness())
        self.assertNotIn("gracekelly_storage_task_count", output)
        self.assertNotIn("gracekelly_storage_step_count", output)
        self.assertNotIn("gracekelly_storage_event_count", output)


class BuildMetricsPayloadCircuitBreakerTests(unittest.TestCase):
    def _readiness_with_adapter(self, breaker_details: object) -> dict[str, Any]:
        r = _mock_readiness()
        r["components"].append({
            "name": "browser.perplexity",
            "kind": "adapter",
            "status": "ok",
            "required": False,
            "details": {"circuit_breaker": breaker_details},
        })
        return r

    def test_adapter_with_circuit_breaker_emits_state_metric(self) -> None:
        breaker = {"state": "closed", "consecutive_failures": 0, "open_count": 0, "fail_fast_rejections": 0}
        output = _call_metrics(self._readiness_with_adapter(breaker))
        self.assertIn("gracekelly_browser_circuit_breaker_state", output)
        self.assertIn('"closed"', output)

    def test_adapter_with_circuit_breaker_emits_consecutive_failures(self) -> None:
        breaker = {"state": "open", "consecutive_failures": 3, "open_count": 1, "fail_fast_rejections": 5}
        output = _call_metrics(self._readiness_with_adapter(breaker))
        self.assertIn("gracekelly_browser_circuit_breaker_consecutive_failures", output)

    def test_adapter_non_dict_circuit_breaker_skipped(self) -> None:
        # circuit_breaker is not a dict → the adapter block is skipped → fallback "disabled" state emitted
        output = _call_metrics(self._readiness_with_adapter("not_a_dict"))
        self.assertIn('"disabled"', output)

    def test_no_adapter_component_emits_disabled_fallback(self) -> None:
        output = _call_metrics(_mock_readiness())
        self.assertIn('"disabled"', output)


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
