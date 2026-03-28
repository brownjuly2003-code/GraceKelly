from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gracekelly.middleware import _is_protected, _normalize_endpoint, setup_request_metrics
from gracekelly.request_metrics import RequestMetrics


def _app_with_metrics() -> tuple[FastAPI, RequestMetrics]:
    app = FastAPI()
    metrics = RequestMetrics()
    app.state.request_metrics = metrics

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/models")
    def models() -> list[object]:
        return []

    setup_request_metrics(app)
    return app, metrics


class SetupRequestMetricsTests(unittest.TestCase):
    def test_successful_request_recorded(self) -> None:
        app, metrics = _app_with_metrics()
        TestClient(app).get("/health")
        self.assertEqual(metrics.requests_total()[("/health", 200)], 1)

    def test_multiple_requests_accumulated(self) -> None:
        app, metrics = _app_with_metrics()
        client = TestClient(app)
        for _ in range(3):
            client.get("/health")
        self.assertEqual(metrics.requests_total()[("/health", 200)], 3)

    def test_different_endpoints_tracked_separately(self) -> None:
        app, metrics = _app_with_metrics()
        client = TestClient(app)
        client.get("/health")
        client.get("/api/v1/models")
        totals = metrics.requests_total()
        self.assertIn(("/health", 200), totals)
        self.assertIn(("/api/v1/models", 200), totals)

    def test_uuid_in_path_normalized_before_recording(self) -> None:
        app, metrics = _app_with_metrics()

        @app.get("/api/v1/tasks/{task_id}")
        def get_task(task_id: str) -> dict[str, str]:
            return {"task_id": task_id}

        client = TestClient(app)
        uuid = "550e8400-e29b-41d4-a716-446655440000"
        client.get(f"/api/v1/tasks/{uuid}")
        totals = metrics.requests_total()
        self.assertIn(("/api/v1/tasks/{id}", 200), totals)
        self.assertNotIn((f"/api/v1/tasks/{uuid}", 200), totals)

    def test_no_metrics_state_does_not_crash(self) -> None:
        app = FastAPI()

        @app.get("/health")
        def health() -> dict[str, str]:
            return {"status": "ok"}

        setup_request_metrics(app)
        response = TestClient(app).get("/health")
        self.assertEqual(response.status_code, 200)

    def test_latency_recorded_after_request(self) -> None:
        app, metrics = _app_with_metrics()
        TestClient(app).get("/health")
        snap = metrics.request_duration_seconds()
        self.assertIn("/health", snap)
        _, _, count = snap["/health"]
        self.assertEqual(count, 1)

    def test_latency_sum_is_positive(self) -> None:
        app, metrics = _app_with_metrics()
        TestClient(app).get("/health")
        _, total_sum, _ = metrics.request_duration_seconds()["/health"]
        self.assertGreater(total_sum, 0.0)


class IsProtectedTests(unittest.TestCase):
    def test_health_is_not_protected(self) -> None:
        self.assertFalse(_is_protected("/health"))

    def test_docs_is_not_protected(self) -> None:
        self.assertFalse(_is_protected("/docs"))

    def test_openapi_json_is_not_protected(self) -> None:
        self.assertFalse(_is_protected("/openapi.json"))

    def test_redoc_is_not_protected(self) -> None:
        self.assertFalse(_is_protected("/redoc"))

    def test_api_endpoint_is_protected(self) -> None:
        self.assertTrue(_is_protected("/api/v1/orchestrate"))

    def test_root_is_protected(self) -> None:
        self.assertTrue(_is_protected("/"))

    def test_unknown_path_is_protected(self) -> None:
        self.assertTrue(_is_protected("/tasks"))

    def test_health_prefix_is_protected(self) -> None:
        """A path that starts with /health but isn't exactly /health is protected."""
        self.assertTrue(_is_protected("/health/detailed"))

    def test_docs_prefix_is_protected(self) -> None:
        self.assertTrue(_is_protected("/docs/extra"))


class NormalizeEndpointTests(unittest.TestCase):
    _UUID = "123e4567-e89b-12d3-a456-426614174000"

    def test_uuid_in_path_replaced_with_id(self) -> None:
        path = f"/tasks/{self._UUID}"
        self.assertEqual(_normalize_endpoint(path), "/tasks/{id}")

    def test_multiple_uuids_all_replaced(self) -> None:
        other = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        path = f"/tasks/{self._UUID}/steps/{other}"
        self.assertEqual(_normalize_endpoint(path), "/tasks/{id}/steps/{id}")

    def test_non_uuid_path_unchanged(self) -> None:
        self.assertEqual(_normalize_endpoint("/tasks"), "/tasks")

    def test_empty_path_unchanged(self) -> None:
        self.assertEqual(_normalize_endpoint(""), "")

    def test_no_uuid_with_similar_pattern_unchanged(self) -> None:
        """Partial hex strings that don't match UUID format are not replaced."""
        self.assertEqual(_normalize_endpoint("/tasks/123e4567"), "/tasks/123e4567")

    def test_uuid_at_root_replaced(self) -> None:
        self.assertEqual(_normalize_endpoint(f"/{self._UUID}"), "/{id}")

    def test_non_uuid_segment_preserved(self) -> None:
        path = f"/tasks/{self._UUID}/status"
        self.assertEqual(_normalize_endpoint(path), "/tasks/{id}/status")

    def test_uppercase_hex_not_replaced(self) -> None:
        """_UUID_RE only matches lowercase hex — uppercase should not be replaced."""
        upper_uuid = self._UUID.upper()
        path = f"/tasks/{upper_uuid}"
        self.assertEqual(_normalize_endpoint(path), path)

    def test_path_without_uuid_returned_as_is(self) -> None:
        self.assertEqual(_normalize_endpoint("/api/v1/models"), "/api/v1/models")


if __name__ == "__main__":
    unittest.main()
