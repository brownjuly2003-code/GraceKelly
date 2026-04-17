from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from gracekelly.api.routes import health


class _TaskRepository:
    backend_name = "memory"


class HealthzLiveTests(unittest.TestCase):
    def test_liveness_returns_ok(self) -> None:
        app = FastAPI()
        app.include_router(health.router)
        app.state.task_repository = _TaskRepository()
        client = TestClient(app)

        response = client.get("/healthz/live")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_readiness_returns_ok_with_storage(self) -> None:
        app = FastAPI()
        app.include_router(health.router)
        app.state.task_repository = _TaskRepository()
        client = TestClient(app)

        response = client.get("/healthz/ready")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_readiness_returns_503_without_storage(self) -> None:
        app = FastAPI()
        app.include_router(health.router)
        app.state.task_repository = None
        client = TestClient(app)

        response = client.get("/healthz/ready")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "Storage unavailable")
