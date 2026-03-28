from __future__ import annotations

import threading
import unittest

from gracekelly.request_metrics import LATENCY_BUCKETS, RequestMetrics


class RequestMetricsLatencyTests(unittest.TestCase):
    def test_record_latency_populates_duration(self) -> None:
        m = RequestMetrics()
        m.record_request_latency("/api/v1/orchestrate", 0.05)
        snap = m.request_duration_seconds()
        self.assertIn("/api/v1/orchestrate", snap)

    def test_bucket_count_increments_for_bound(self) -> None:
        m = RequestMetrics()
        m.record_request_latency("/x", 0.05)  # falls in ≤0.05 bucket (index 3)
        snap = m.request_duration_seconds()
        bucket_counts, _, _ = snap["/x"]
        # buckets at index 3 (0.05) and above should be 1; below should be 0
        idx_005 = LATENCY_BUCKETS.index(0.05)
        for i in range(idx_005):
            self.assertEqual(bucket_counts[i], 0, f"bucket {LATENCY_BUCKETS[i]} should be 0")
        self.assertEqual(bucket_counts[idx_005], 1)

    def test_sum_and_count_updated(self) -> None:
        m = RequestMetrics()
        m.record_request_latency("/y", 0.1)
        m.record_request_latency("/y", 0.2)
        _, total_sum, count = m.request_duration_seconds()["/y"]
        self.assertAlmostEqual(total_sum, 0.3, places=9)
        self.assertEqual(count, 2)

    def test_empty_metrics_returns_empty_duration(self) -> None:
        m = RequestMetrics()
        self.assertEqual(m.request_duration_seconds(), {})

    def test_multiple_endpoints_tracked_separately(self) -> None:
        m = RequestMetrics()
        m.record_request_latency("/a", 0.01)
        m.record_request_latency("/b", 0.5)
        snap = m.request_duration_seconds()
        self.assertIn("/a", snap)
        self.assertIn("/b", snap)
        self.assertEqual(snap["/a"][2], 1)
        self.assertEqual(snap["/b"][2], 1)

    def test_bucket_counts_tuple_length_matches_latency_buckets(self) -> None:
        m = RequestMetrics()
        m.record_request_latency("/z", 1.0)
        bucket_counts, _, _ = m.request_duration_seconds()["/z"]
        self.assertEqual(len(bucket_counts), len(LATENCY_BUCKETS))

    def test_very_fast_request_lands_in_first_bucket(self) -> None:
        m = RequestMetrics()
        m.record_request_latency("/fast", 0.001)  # ≤0.005
        bucket_counts, _, _ = m.request_duration_seconds()["/fast"]
        self.assertEqual(bucket_counts[0], 1)

    def test_very_slow_request_lands_in_no_bucket(self) -> None:
        m = RequestMetrics()
        m.record_request_latency("/slow", 100.0)  # > all bounds
        bucket_counts, _, count = m.request_duration_seconds()["/slow"]
        # No bucket should be incremented since 100s > max bound
        self.assertEqual(sum(bucket_counts), 0)
        self.assertEqual(count, 1)

    def test_snapshot_returns_copy(self) -> None:
        m = RequestMetrics()
        m.record_request_latency("/copy", 0.05)
        snap1 = m.request_duration_seconds()
        snap1["/copy"] = (tuple([0] * len(LATENCY_BUCKETS)), 0.0, 0)
        snap2 = m.request_duration_seconds()
        self.assertEqual(snap2["/copy"][2], 1)  # original count unchanged


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
