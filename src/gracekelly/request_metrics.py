from __future__ import annotations

from threading import Lock

# Prometheus-standard latency histogram bucket upper bounds (seconds).
LATENCY_BUCKETS: tuple[float, ...] = (
    0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0,
)

# Snapshot type: (per-bound cumulative counts, total sum, total count)
LatencySnapshot = tuple[tuple[int, ...], float, int]


class RequestMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._requests_total: dict[tuple[str, int], int] = {}
        self._adapter_errors_total: dict[tuple[str, str], int] = {}
        # Histogram state per endpoint
        self._latency_buckets: dict[str, list[int]] = {}
        self._latency_sum: dict[str, float] = {}
        self._latency_count: dict[str, int] = {}

    def record_request(self, endpoint: str, status_code: int) -> None:
        key = (endpoint, status_code)
        with self._lock:
            self._requests_total[key] = self._requests_total.get(key, 0) + 1

    def record_adapter_error(self, adapter: str, failure_code: str) -> None:
        key = (adapter, failure_code)
        with self._lock:
            self._adapter_errors_total[key] = self._adapter_errors_total.get(key, 0) + 1

    def record_request_latency(self, endpoint: str, duration_seconds: float) -> None:
        """Record a single request latency observation into histogram buckets."""
        with self._lock:
            if endpoint not in self._latency_buckets:
                self._latency_buckets[endpoint] = [0] * len(LATENCY_BUCKETS)
                self._latency_sum[endpoint] = 0.0
                self._latency_count[endpoint] = 0
            buckets = self._latency_buckets[endpoint]
            for i, bound in enumerate(LATENCY_BUCKETS):
                if duration_seconds <= bound:
                    buckets[i] += 1
            self._latency_sum[endpoint] += duration_seconds
            self._latency_count[endpoint] += 1

    def requests_total(self) -> dict[tuple[str, int], int]:
        with self._lock:
            return dict(self._requests_total)

    def adapter_errors_total(self) -> dict[tuple[str, str], int]:
        with self._lock:
            return dict(self._adapter_errors_total)

    def request_duration_seconds(self) -> dict[str, LatencySnapshot]:
        """Return per-endpoint histogram snapshot: (bucket_counts, sum, count)."""
        with self._lock:
            return {
                ep: (tuple(self._latency_buckets[ep]), self._latency_sum[ep], self._latency_count[ep])
                for ep in sorted(self._latency_buckets)
            }
