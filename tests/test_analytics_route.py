from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gracekelly.api.routes.analytics import router


def _create_test_app(*, has_repository: bool = True, tasks_data: list | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    if has_repository:
        repo = MagicMock()
        mock_tasks = tasks_data or []
        repo.list_recent.return_value = mock_tasks
        repo.list_steps.return_value = []
        app.state.task_repository = repo
    else:
        app.state.task_repository = None

    return app


class AnalyticsRouteTests(unittest.TestCase):
    def test_analytics_returns_200(self) -> None:
        app = _create_test_app()
        client = TestClient(app)

        response = client.get("/api/v1/analytics")

        self.assertEqual(200, response.status_code)

    def test_analytics_empty_no_tasks(self) -> None:
        app = _create_test_app()
        client = TestClient(app)

        response = client.get("/api/v1/analytics")
        payload = response.json()

        self.assertEqual(0, payload["total_models"])
        self.assertEqual(0, payload["total_executions"])

    def test_analytics_response_fields(self) -> None:
        app = _create_test_app()
        client = TestClient(app)

        response = client.get("/api/v1/analytics")
        payload = response.json()

        self.assertIn("total_models", payload)
        self.assertIn("total_executions", payload)
        self.assertIn("models", payload)
        self.assertIn("top_models", payload)

    def test_analytics_no_repository_returns_200(self) -> None:
        app = _create_test_app(has_repository=False)
        client = TestClient(app)

        response = client.get("/api/v1/analytics")
        payload = response.json()

        self.assertEqual(200, response.status_code)
        self.assertEqual(0, payload["total_models"])
        self.assertEqual(0, payload["total_executions"])

    def test_models_list_type(self) -> None:
        app = _create_test_app()
        client = TestClient(app)

        response = client.get("/api/v1/analytics")
        payload = response.json()

        self.assertIsInstance(payload["models"], list)

    def test_top_models_list_type(self) -> None:
        app = _create_test_app()
        client = TestClient(app)

        response = client.get("/api/v1/analytics")
        payload = response.json()

        self.assertIsInstance(payload["top_models"], list)

    def test_total_models_count(self) -> None:
        task = MagicMock()
        task.task_id = "task-1"
        app = _create_test_app(tasks_data=[task])
        app.state.task_repository.list_steps.return_value = [
            MagicMock(model_id="model-a", status="completed", duration_ms=100),
            MagicMock(model_id="model-b", status="failed", duration_ms=200),
        ]
        client = TestClient(app)

        response = client.get("/api/v1/analytics")
        payload = response.json()

        self.assertEqual(len(payload["models"]), payload["total_models"])

    def test_model_stats_view_fields(self) -> None:
        task = MagicMock()
        task.task_id = "task-1"
        app = _create_test_app(tasks_data=[task])
        app.state.task_repository.list_steps.return_value = [
            MagicMock(model_id="model-a", status="completed", duration_ms=100),
        ]
        client = TestClient(app)

        response = client.get("/api/v1/analytics")
        payload = response.json()
        model = payload["models"][0]

        self.assertIn("model_id", model)
        self.assertIn("total_executions", model)
        self.assertIn("successful", model)
        self.assertIn("failed", model)
        self.assertIn("success_rate", model)
        self.assertIn("avg_duration_ms", model)


if __name__ == "__main__":
    unittest.main()
