from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gracekelly.api.routes.analytics import router


def _create_test_app(*, has_repository: bool = True, tasks_data: list[object] | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    if has_repository:
        repo = MagicMock()
        mock_tasks = tasks_data or []
        repo.list_recent.return_value = mock_tasks
        repo.list_steps_batch.return_value = {}
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
        app.state.task_repository.list_steps_batch.return_value = {
            "task-1": [
                MagicMock(model_id="model-a", status="completed", duration_ms=100),
                MagicMock(model_id="model-b", status="failed", duration_ms=200),
            ]
        }
        client = TestClient(app)

        response = client.get("/api/v1/analytics")
        payload = response.json()

        self.assertEqual(len(payload["models"]), payload["total_models"])

    def test_model_stats_view_fields(self) -> None:
        task = MagicMock()
        task.task_id = "task-1"
        app = _create_test_app(tasks_data=[task])
        app.state.task_repository.list_steps_batch.return_value = {
            "task-1": [
                MagicMock(model_id="model-a", status="completed", duration_ms=100),
            ]
        }
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

    def test_analytics_returns_503_when_storage_raises(self) -> None:
        app = _create_test_app()
        app.state.task_repository.list_recent.side_effect = RuntimeError("DB connection lost")
        client = TestClient(app)

        response = client.get("/api/v1/analytics")

        self.assertEqual(503, response.status_code)
        self.assertIn("Storage unavailable", response.json()["detail"])

    def test_analytics_uses_batch_loading(self) -> None:
        task = MagicMock()
        task.task_id = "task-42"
        app = _create_test_app(tasks_data=[task])
        app.state.task_repository.list_steps_batch.return_value = {
            "task-42": [
                MagicMock(model_id="model-x", status="completed", duration_ms=75),
            ]
        }
        client = TestClient(app)

        response = client.get("/api/v1/analytics")

        self.assertEqual(200, response.status_code)
        repo = app.state.task_repository
        repo.list_steps_batch.assert_called_once_with(["task-42"])
        repo.list_steps.assert_not_called()

    def test_analytics_uses_execution_history_when_no_repository(self) -> None:
        app = _create_test_app(has_repository=False)
        history = MagicMock()
        history.list_recent.return_value = [
            MagicMock(model_id="model-z", status="completed", duration_ms=50),
        ]
        app.state.execution_history = history
        client = TestClient(app)

        response = client.get("/api/v1/analytics")
        payload = response.json()

        self.assertEqual(200, response.status_code)
        self.assertEqual(1, payload["total_models"])
        model_ids = [m["model_id"] for m in payload["models"]]
        self.assertIn("model-z", model_ids)


if __name__ == "__main__":
    unittest.main()
