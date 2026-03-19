from __future__ import annotations

from threading import Lock


class RequestMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._requests_total: dict[tuple[str, int], int] = {}
        self._adapter_errors_total: dict[tuple[str, str], int] = {}

    def record_request(self, endpoint: str, status_code: int) -> None:
        key = (endpoint, status_code)
        with self._lock:
            self._requests_total[key] = self._requests_total.get(key, 0) + 1

    def record_adapter_error(self, adapter: str, failure_code: str) -> None:
        key = (adapter, failure_code)
        with self._lock:
            self._adapter_errors_total[key] = self._adapter_errors_total.get(key, 0) + 1

    def requests_total(self) -> dict[tuple[str, int], int]:
        with self._lock:
            return dict(self._requests_total)

    def adapter_errors_total(self) -> dict[tuple[str, str], int]:
        with self._lock:
            return dict(self._adapter_errors_total)
