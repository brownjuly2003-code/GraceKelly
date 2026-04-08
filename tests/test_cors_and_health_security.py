from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from gracekelly.config import Settings
from gracekelly.main import create_app


class HealthSecurityTests(unittest.TestCase):
    def test_health_minimal_when_expose_details_false(self) -> None:
        app = create_app(Settings(health_expose_details=False))
        client = TestClient(app, raise_server_exceptions=True)
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        # Sensitive fields must NOT be present
        self.assertNotIn("version", data)
        self.assertNotIn("environment", data)
        self.assertNotIn("storage_backend", data)
        self.assertNotIn("active_model_executions", data)
        self.assertNotIn("saturated_models", data)
        # Only "status" key
        self.assertEqual(list(data.keys()), ["status"])

    def test_health_full_when_expose_details_true(self) -> None:
        app = create_app(Settings(health_expose_details=True))
        client = TestClient(app, raise_server_exceptions=True)
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertIn("version", data)
        self.assertIn("environment", data)
        self.assertIn("storage_backend", data)
        self.assertIn("active_model_executions", data)
        self.assertIn("saturated_models", data)

    def test_health_status_value_is_string(self) -> None:
        for expose in (True, False):
            with self.subTest(expose_details=expose):
                app = create_app(Settings(health_expose_details=expose))
                client = TestClient(app, raise_server_exceptions=True)
                response = client.get("/health")
                self.assertIsInstance(response.json()["status"], str)
