from __future__ import annotations

import threading
import unittest

from gracekelly.request_metrics import RequestMetrics


class RequestMetricsTests(unittest.TestCase):
    def test_record_request_increments(self) -> None:
        m = RequestMetrics()
        m.record_request("/api/v1/tasks", 200)
        self.assertEqual(m.requests_total(), {("/api/v1/tasks", 200): 1})

    def test_record_request_accumulates(self) -> None:
        m = RequestMetrics()
        m.record_request("/api/v1/tasks", 200)
        m.record_request("/api/v1/tasks", 200)
        m.record_request("/api/v1/tasks", 200)
        self.assertEqual(m.requests_total()[("/api/v1/tasks", 200)], 3)

    def test_record_request_different_status_codes_are_separate(self) -> None:
        m = RequestMetrics()
        m.record_request("/health", 200)
        m.record_request("/health", 503)
        totals = m.requests_total()
        self.assertEqual(totals[("/health", 200)], 1)
        self.assertEqual(totals[("/health", 503)], 1)

    def test_record_adapter_error_increments(self) -> None:
        m = RequestMetrics()
        m.record_adapter_error("browser", "TIMEOUT")
        self.assertEqual(m.adapter_errors_total(), {("browser", "TIMEOUT"): 1})

    def test_record_adapter_error_accumulates(self) -> None:
        m = RequestMetrics()
        m.record_adapter_error("openai", "RATE_LIMITED")
        m.record_adapter_error("openai", "RATE_LIMITED")
        self.assertEqual(m.adapter_errors_total()[("openai", "RATE_LIMITED")], 2)

    def test_request_and_adapter_counters_are_independent(self) -> None:
        m = RequestMetrics()
        m.record_request("/smart", 200)
        m.record_adapter_error("mistral", "AUTH_FAILED")
        self.assertEqual(len(m.requests_total()), 1)
        self.assertEqual(len(m.adapter_errors_total()), 1)

    def test_requests_total_returns_copy(self) -> None:
        m = RequestMetrics()
        m.record_request("/metrics", 200)
        snapshot = m.requests_total()
        snapshot[("/metrics", 200)] = 999
        self.assertEqual(m.requests_total()[("/metrics", 200)], 1)

    def test_adapter_errors_total_returns_copy(self) -> None:
        m = RequestMetrics()
        m.record_adapter_error("browser", "CLOSED")
        snapshot = m.adapter_errors_total()
        snapshot[("browser", "CLOSED")] = 999
        self.assertEqual(m.adapter_errors_total()[("browser", "CLOSED")], 1)

    def test_empty_metrics_return_empty_dicts(self) -> None:
        m = RequestMetrics()
        self.assertEqual(m.requests_total(), {})
        self.assertEqual(m.adapter_errors_total(), {})

    def test_thread_safety_record_request(self) -> None:
        m = RequestMetrics()
        threads = [threading.Thread(target=m.record_request, args=("/x", 200)) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(m.requests_total()[("/x", 200)], 100)

    def test_thread_safety_record_adapter_error(self) -> None:
        m = RequestMetrics()
        threads = [threading.Thread(target=m.record_adapter_error, args=("svc", "ERR")) for _ in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(m.adapter_errors_total()[("svc", "ERR")], 100)


if __name__ == "__main__":
    unittest.main()
